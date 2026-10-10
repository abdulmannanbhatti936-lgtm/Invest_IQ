"""
The Phase 4 experiment (Workflow.md Step 4.6), declared on 2026-10-10 before any run and
run once (Memory.md §3):

- next-day horizon: the LSTM and Random Forest with and without the news inputs, on the
  same price dataset, cut dates, seeds, RF grid, baselines and walk-forward as Phase 3;
- 5-day horizon (the one extra experiment): the same pair with 5-day targets, RF labels at
  ±2.24%, a 5-row embargo at each boundary and a Newey-West Diebold-Mariano test.
  Evaluation only, never served.

The next-day news model is promoted only if it beats the price-only model on BOTH validation
measures (LSTM RMSE and RF balanced accuracy); the test period never takes part in that
choice and is reported whatever it shows. Both next-day models are saved as candidates.

    python -m ml.sentiment_experiment <price dataset> <news dataset>
"""

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from core.config import settings
from ml import metrics
from ml.dataset import dataset_reference, find_dataset, load_dataset
from ml.features import CLASS_ORDER, SENTIMENT_COLUMNS
from ml.inference import latest_version
from ml.news_dataset import load_news_dataset, news_reference
from ml.training import (
    Candidate,
    _by_ticker_order,
    _windows,
    fit_candidate,
    lstm_outputs,
    save_artifacts,
)

logger = logging.getLogger(__name__)

FIVE_DAY_THRESHOLD = 0.0224  # √5 × the ±1% next-day band (decided 2026-10-10)
VARIANTS = (
    ("price_1d", 1, False),
    ("news_1d", 1, True),
    ("price_5d", 5, False),
    ("news_5d", 5, True),
)


def _headline_metrics(candidate: Candidate) -> dict:
    ev, wf = candidate.metadata["evaluation"], candidate.metadata["walk_forward"]
    lstm, base, rf = ev["lstm"], ev["baselines"], ev["random_forest"]
    return {
        "lstm_rmse_pct": lstm["rmse_pct"],
        "naive_rmse_pct": base["naive"]["rmse_pct"],
        "theil_u": lstm["theil_u"],
        "dm_statistic": lstm["diebold_mariano_vs_naive"]["statistic"],
        "dm_p_value": lstm["diebold_mariano_vs_naive"]["p_value"],
        "dm_lag": lstm["diebold_mariano_vs_naive"]["lag"],
        "directional_accuracy": lstm["direction"]["directional_accuracy"],
        "directional_accuracy_ci95": [
            lstm["direction"]["ci95_low"],
            lstm["direction"]["ci95_high"],
        ],
        "majority_direction_accuracy": base["majority_direction"]["directional_accuracy"],
        "rf_accuracy": rf["accuracy"],
        "rf_balanced_accuracy": rf["balanced_accuracy"],
        "rf_f1_macro": rf["f1_macro"],
        "majority_class_accuracy": base["majority_class"]["accuracy"],
        "majority_class_label": base["majority_class"]["label"],
        "test_rows": candidate.metadata["data"]["periods"]["test"]["lstm_windows"],
        "walk_forward_mean": wf["mean"] if wf else None,
        "walk_forward_std": wf["std"] if wf else None,
        "validation": candidate.models.training["validation"],
    }


def _subset_metrics(rows: pd.DataFrame) -> dict:
    """LSTM and RF metrics on a subset of test rows (e.g. the days with news)."""
    if rows.empty:
        return {"rows": 0}
    forecast = rows["close"].to_numpy() * (1 + rows["forecast_return"].to_numpy())
    hits, n = metrics.direction_hits(
        rows["forecast_return"].to_numpy(), rows["target_return"].to_numpy()
    )
    rf = metrics.classification_summary(
        rows["target_signal"].astype(int).to_numpy(),
        rows["rf_signal"].to_numpy(),
        CLASS_ORDER,
        None,
    )
    return {
        "rows": int(len(rows)),
        "lstm_rmse_pct": metrics.price_error_summary(forecast, rows["next_close"].to_numpy())[
            "rmse_pct"
        ],
        "naive_rmse_pct": metrics.price_error_summary(
            rows["close"].to_numpy(), rows["next_close"].to_numpy()
        )["rmse_pct"],
        "directional_accuracy": hits / n if n else None,
        "directional_accuracy_ci95": list(metrics.wilson_interval(hits, n)) if n else None,
        "rf_balanced_accuracy": rf["balanced_accuracy"],
        "rf_accuracy": rf["accuracy"],
    }


def _news_days(price: Candidate, news: Candidate) -> dict:
    """Both models on the test days where the stock had news (news_weight > 0)."""
    keys = ["ticker", "date"]
    with_news = news.test.loc[news.test["news_weight"] > 0, keys]
    return {
        "price_only": _subset_metrics(price.test.merge(with_news, on=keys)),
        "with_news": _subset_metrics(news.test.merge(with_news, on=keys)),
    }


def _ablation(news: Candidate) -> dict:
    """
    How much the news inputs move the news model's own test forecasts: the same model on the
    same days, once with the real news inputs and once with them set to 'no news'.
    """
    models, features = news.models, news.metadata["features"]
    rows = _by_ticker_order(news.test[news.test["news_weight"] > 0])
    if rows.empty:
        return {"rows": 0}
    silent = {t: f.assign(**{c: 0.0 for c in SENTIMENT_COLUMNS}) for t, f in news.frames.items()}
    scaled = {t: models.scaler.transform(f[features]).astype(np.float32) for t, f in silent.items()}
    forecast, _ = lstm_outputs(models.lstm, models.y_std, _windows(scaled, rows))
    rf = models.forest.predict(
        rows[features].assign(**{c: 0.0 for c in SENTIMENT_COLUMNS}).to_numpy()
    )
    actual = rows["forecast_return"].to_numpy()
    return {
        "rows": int(len(rows)),
        "rf_signal_changed": int(np.sum(rf != rows["rf_signal"].to_numpy())),
        "lstm_direction_flipped": int(np.sum(np.sign(forecast) != np.sign(actual))),
        "lstm_mean_abs_change_pct_points": float(np.mean(np.abs(actual - forecast)) * 100),
        "lstm_max_abs_change_pct_points": float(np.max(np.abs(actual - forecast)) * 100),
    }


def _coverage(news: Candidate) -> dict:
    out = {}
    for period, info in news.metadata["data"]["periods"].items():
        frames = pd.concat(news.frames.values())
        mask = (frames["date"] >= info["first_date"]) & (frames["date"] <= info["last_date"])
        out[period] = float((frames.loc[mask, "news_weight"] > 0).mean())
    return out


def _decision(price: dict, news: dict) -> dict:
    better_lstm = news["validation"]["lstm_rmse_pct"] < price["validation"]["lstm_rmse_pct"]
    better_rf = (
        news["validation"]["rf_balanced_accuracy"] > price["validation"]["rf_balanced_accuracy"]
    )
    return {
        "rule": "promote the news model only if it beats the price-only model on BOTH "
        "validation LSTM RMSE and validation RF balanced accuracy",
        "news_better_on_validation_lstm_rmse": bool(better_lstm),
        "news_better_on_validation_rf_balanced_accuracy": bool(better_rf),
        "promote_news_model": bool(better_lstm and better_rf),
    }


def run(dataset_version: str, news_version: str) -> dict:
    manifest, raw = load_dataset(find_dataset(dataset_version))
    news_manifest, headlines = load_news_dataset(find_dataset(news_version))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    live = latest_version(settings.MODEL_DIR)
    live_meta = json.loads(
        (Path(settings.MODEL_DIR) / live / "metadata.json").read_text(encoding="utf-8")
    )

    fitted: dict[str, Candidate] = {}
    for name, horizon, with_news in VARIANTS:
        logger.info(f"Fitting {name}")
        fitted[name] = fit_candidate(
            raw,
            dataset_reference(manifest),
            version=f"lstm-rf-{'news-' if with_news else ''}{stamp}" if horizon == 1 else name,
            headlines=headlines if with_news else None,
            news=news_reference(news_manifest) if with_news else None,
            horizon=horizon,
            threshold=FIVE_DAY_THRESHOLD if horizon == 5 else 0.01,
        )

    results = {name: _headline_metrics(c) for name, c in fitted.items()}
    price_1d = fitted["price_1d"].metadata["evaluation"]
    reproduces_live = bool(
        np.isclose(price_1d["lstm"]["rmse_pct"], live_meta["evaluation"]["lstm"]["rmse_pct"])
        and np.isclose(
            price_1d["random_forest"]["balanced_accuracy"],
            live_meta["evaluation"]["random_forest"]["balanced_accuracy"],
        )
    )
    # The news model's fallback: the live model when this run reproduces it, else the new
    # price-only candidate (which then has to be promoted first, ml/promote.py)
    fallback = live if reproduces_live else fitted["price_1d"].metadata["model_version"]
    fitted["news_1d"].metadata["fallback_model_version"] = fallback
    for name in ("price_1d", "news_1d"):
        c = fitted[name]
        save_artifacts(
            c.models, c.metadata, settings.candidate_model_dir, c.metadata["model_version"]
        )

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "price_dataset": manifest["version"],
        "news_dataset": news_reference(news_manifest),
        "news_rows_per_ticker": news_manifest["rows_per_ticker"],
        "live_model": live,
        "price_1d_reproduces_live_model": reproduces_live,
        "candidates": {
            "price_1d": fitted["price_1d"].metadata["model_version"],
            "news_1d": fitted["news_1d"].metadata["model_version"],
            "news_1d_fallback": fallback,
        },
        "variants": results,
        "coverage_share_of_rows_with_news": _coverage(fitted["news_1d"]),
        "decision_1d": _decision(results["price_1d"], results["news_1d"]),
        "validation_5d": _decision(results["price_5d"], results["news_5d"]),
        "news_days_1d": _news_days(fitted["price_1d"], fitted["news_1d"]),
        "news_days_5d": _news_days(fitted["price_5d"], fitted["news_5d"]),
        "ablation_1d": _ablation(fitted["news_1d"]),
        "ablation_5d": _ablation(fitted["news_5d"]),
        "feature_importance_news_1d": fitted["news_1d"].metadata["random_forest"][
            "feature_importance"
        ],
    }


def _pct(value, digits: int = 1) -> str:
    return "n/a" if value is None else f"{100 * value:.{digits}f}%"


def _variant_rows(variants: dict, names: tuple[str, str]) -> list[str]:
    rows = [
        "| | " + " | ".join(names) + " |",
        "| --- | " + " | ".join("---" for _ in names) + " |",
    ]
    v = [variants[n] for n in names]

    def line(title, render):
        rows.append(f"| {title} | " + " | ".join(render(x) for x in v) + " |")

    line("LSTM RMSE (% of price)", lambda x: f"{x['lstm_rmse_pct']:.3f}%")
    line("Naive 'no change' RMSE", lambda x: f"{x['naive_rmse_pct']:.3f}%")
    line("Theil's U (below 1 beats naive)", lambda x: f"{x['theil_u']:.3f}")
    line(
        "Diebold-Mariano vs naive",
        lambda x: f"{x['dm_statistic']:.2f} (p = {x['dm_p_value']:.3f}, lag {x['dm_lag']})",
    )
    line(
        "LSTM direction right (95% CI)",
        lambda x: f"{_pct(x['directional_accuracy'])} ({_pct(x['directional_accuracy_ci95'][0])}"
        f"-{_pct(x['directional_accuracy_ci95'][1])})",
    )
    line("Always the majority direction", lambda x: _pct(x["majority_direction_accuracy"]))
    line("RF accuracy", lambda x: _pct(x["rf_accuracy"]))
    line("RF balanced accuracy", lambda x: _pct(x["rf_balanced_accuracy"]))
    line("RF macro-F1", lambda x: f"{x['rf_f1_macro']:.3f}")
    line(
        "Always the majority class",
        lambda x: f"{_pct(x['majority_class_accuracy'])} ({x['majority_class_label']})",
    )
    line(
        "Walk-forward Theil's U (mean ± sd)",
        lambda x: f"{x['walk_forward_mean']['lstm_theil_u']:.3f} ± "
        f"{x['walk_forward_std']['lstm_theil_u']:.3f}",
    )
    line(
        "Walk-forward RF balanced accuracy",
        lambda x: f"{_pct(x['walk_forward_mean']['rf_balanced_accuracy'])} ± "
        f"{_pct(x['walk_forward_std']['rf_balanced_accuracy'])}",
    )
    line("Validation LSTM RMSE", lambda x: f"{x['validation']['lstm_rmse_pct']:.3f}%")
    line(
        "Validation RF balanced accuracy",
        lambda x: _pct(x["validation"]["rf_balanced_accuracy"]),
    )
    line("Test forecasts", lambda x: str(x["test_rows"]))
    return rows


def _subset_rows(block: dict) -> list[str]:
    rows = [
        "| | Price only | With news |",
        "| --- | --- | --- |",
    ]
    p, n = block["price_only"], block["with_news"]
    if not p.get("rows"):
        return ["No test day had news."]
    rows.append(f"| Test forecasts on days with news | {p['rows']} | {n['rows']} |")
    rows.append(
        f"| LSTM RMSE | {p['lstm_rmse_pct']:.3f}% | {n['lstm_rmse_pct']:.3f}% "
        f"(naive {n['naive_rmse_pct']:.3f}%) |"
    )
    rows.append(
        f"| LSTM direction right | {_pct(p['directional_accuracy'])} "
        f"({_pct(p['directional_accuracy_ci95'][0])}-{_pct(p['directional_accuracy_ci95'][1])})"
        f" | {_pct(n['directional_accuracy'])} ({_pct(n['directional_accuracy_ci95'][0])}-"
        f"{_pct(n['directional_accuracy_ci95'][1])}) |"
    )
    rows.append(
        f"| RF balanced accuracy | {_pct(p['rf_balanced_accuracy'])} | "
        f"{_pct(n['rf_balanced_accuracy'])} |"
    )
    return rows


def _ablation_line(block: dict) -> str:
    if not block.get("rows"):
        return "No test day had news."
    return (
        f"On the {block['rows']} test forecasts made on days with news, setting the news inputs "
        f"to 'no news' changed the Random Forest signal on {block['rf_signal_changed']} and "
        f"flipped the LSTM direction on {block['lstm_direction_flipped']}; the LSTM forecast "
        f"moved by {block['lstm_mean_abs_change_pct_points']:.3f} percentage points on average "
        f"(at most {block['lstm_max_abs_change_pct_points']:.3f})."
    )


def write_experiment_report(result: dict, path: Path) -> Path:
    d1, cov = result["decision_1d"], result["coverage_share_of_rows_with_news"]
    news = result["news_dataset"]
    importance = {f["feature"]: f["importance"] for f in result["feature_importance_news_1d"]}
    rank = [f["feature"] for f in result["feature_importance_news_1d"]]
    lines = [
        "# With vs without news sentiment (Phase 4 experiment)",
        "",
        "Declared on 2026-10-10 before any run (Memory.md §3) and run once. Generated by "
        "`python -m ml.sentiment_experiment`.",
        "",
        f"Price dataset `{result['price_dataset']}`; news dataset `{news['version']}` "
        f"({', '.join(news['sources'])}; scored by {', '.join(news['scorer_versions'])}). "
        "Same cut dates, seeds, Random Forest grid, baselines and walk-forward folds in every "
        "variant; only the inputs (and, for the 5-day pair, the horizon) differ.",
        "",
        "Share of stock-days with any news in the 10-trading-day window: "
        + ", ".join(f"{period} {_pct(share)}" for period, share in cov.items())
        + ".",
        "",
        "## Next trading day",
        "",
        *_variant_rows(result["variants"], ("price_1d", "news_1d")),
        "",
        f"The price-only run reproduces the live model `{result['live_model']}`: "
        f"{'yes' if result['price_1d_reproduces_live_model'] else 'no'}.",
        "",
        "### Promotion decision (validation only)",
        "",
        f"Rule: {d1['rule']}. News model better on validation LSTM RMSE: "
        f"{'yes' if d1['news_better_on_validation_lstm_rmse'] else 'no'}; on validation RF "
        f"balanced accuracy: "
        f"{'yes' if d1['news_better_on_validation_rf_balanced_accuracy'] else 'no'}. "
        f"**{'Promote' if d1['promote_news_model'] else 'Do not promote'} the news model.**",
        "",
        "### Test days with news",
        "",
        *_subset_rows(result["news_days_1d"]),
        "",
        "### Does sentiment change a prediction?",
        "",
        _ablation_line(result["ablation_1d"]),
        "",
        f"Random Forest importance of the news inputs: news_weight "
        f"{importance['news_weight']:.4f} (rank {rank.index('news_weight') + 1} of "
        f"{len(rank)}), sentiment {importance['sentiment']:.4f} (rank "
        f"{rank.index('sentiment') + 1}).",
        "",
        "## Five trading days (pre-declared extra experiment, evaluation only)",
        "",
        "Labels: BUY above +2.24%, SELL below -2.24% over five trading days; a 5-row embargo at "
        "each split boundary; Diebold-Mariano with a Newey-West variance (lag 4). Never served.",
        "",
        *_variant_rows(result["variants"], ("price_5d", "news_5d")),
        "",
        "### Test days with news",
        "",
        *_subset_rows(result["news_days_5d"]),
        "",
        _ablation_line(result["ablation_5d"]),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("dataset")
    parser.add_argument("news_dataset")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run(args.dataset, args.news_dataset)
    out = Path(settings.REPORTS_DIR)
    day = result["created_at"][:10]
    (out / f"sentiment_experiment_{day}.json").write_text(
        json.dumps(result, indent=2, default=float) + "\n", encoding="utf-8", newline="\n"
    )
    write_experiment_report(result, out / f"sentiment_experiment_{day}.md")
    print(json.dumps(result["decision_1d"], indent=2))


if __name__ == "__main__":
    main()
