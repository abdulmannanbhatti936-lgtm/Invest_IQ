"""
Training and evaluation of the pooled LSTM forecaster and Random Forest signal classifier
(Workflow.md Steps 3.4-3.5, Architecture.md §15). Training never runs inside an HTTP
request (Rules.md §3.5): it runs from the `ml.train` CLI or the weekly Celery job, and it
only ever produces a candidate; ml/promote.py makes a candidate live.

One model of each kind is trained on all tickers together ("pooled"): the inputs are
scale-free, and pooling gives ~15,000 training rows instead of ~820 per stock. Evaluation:
- chronological 70/15/15 split with the same cut dates for every ticker; the row at each
  boundary is purged (ml/splits.py); the scaler and the target scale are fitted on the
  training period only;
- the LSTM is compared with "tomorrow = today" (naive) and a 5-day moving average, and its
  direction with the training-period majority direction and a 20-day trend rule;
- the Random Forest's min_samples_leaf comes from a grid declared in advance (RF_GRID),
  chosen on the validation period only; it is compared with the majority class and the
  same trend rule;
- the LSTM settings are the Architecture.md §15.1 starting point, not tuned; only the
  stopping epoch is chosen, by validation loss;
- a 3-fold expanding walk-forward repeats the whole fit to show how stable the result is.
The SVM classifier was dropped (decision 2026-10-10): one well-evaluated classifier.

Phase 4 adds two options with the defaults unchanged: `features` (the price inputs, or the
price inputs plus the news inputs of ml/features.py) and `horizon` (next day, or the
pre-declared 5-day experiment with +/-2.24% labels, a 5-row embargo at each boundary and a
Newey-West Diebold-Mariano test).
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import torch
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from core.config import settings
from ml import lstm_model, metrics
from ml.confidence import MC_PASSES, MC_SEED, DirectionCalibrator, certainty
from ml.dataset import dividend_adjusted
from ml.features import (
    CLASS_ORDER,
    FEATURE_COLUMNS,
    SENTIMENT_COLUMNS,
    SIGNAL_LABELS,
    SIGNAL_THRESHOLD,
    build_feature_frame,
)
from ml.report import REPORT_FILE, write_report
from ml.splits import CutDates, assign_periods, shared_cut_dates, walk_forward_folds

logger = logging.getLogger(__name__)

SEED = 42
SEQ_LENGTH = 60
TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
WALK_FORWARD_FOLDS = 3
WALK_FORWARD_TEST_FRAC = 0.30
MIN_TRAINING_ROWS = 400  # per ticker, ~1.6 trading years after indicator warm-up
CONFIDENCE_BANDS = (0.50, 0.55, 0.60, 0.65)

LSTM_HYPERPARAMS = {
    "seq_length": SEQ_LENGTH,
    "layers": "LSTM(64) -> LSTM(32) -> Dropout(0.2) -> Dense(1)",
    "target": "return of the dividend-adjusted close over the horizon, / its training std",
    "optimizer": "Adam",
    "lr": 1e-3,
    "batch_size": 64,
    "max_epochs": 60,
    "early_stopping_patience": 8,
    "mc_dropout_passes": MC_PASSES,
    "mc_dropout_seed": MC_SEED,
}
RF_PARAMS = {
    "n_estimators": 300,
    "max_depth": 6,
    "class_weight": "balanced_subsample",
    "random_state": SEED,
}
# Declared before training (decision 2026-10-10). Each value is fitted on the training period
# and scored on the validation period only; the test period never takes part in the choice.
RF_GRID = {"min_samples_leaf": (5, 10, 20, 40)}
RF_SELECTION_METRIC = "balanced_accuracy"


class InsufficientDataError(ValueError):
    pass


def new_model_version() -> str:
    return "lstm-rf-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def prepare_frames(
    raw: dict[str, pd.DataFrame],
    headlines: dict[str, pd.DataFrame] | None = None,
    horizon: int = 1,
    threshold: float = SIGNAL_THRESHOLD,
) -> dict[str, pd.DataFrame]:
    """
    Served bars with dividend factors -> the model's feature frame per ticker. With
    `headlines` (scored news per ticker; a ticker without any gets an empty frame) the news
    inputs are added.
    """
    frames = {}
    for ticker, frame in raw.items():
        news = None
        if headlines is not None:
            news = headlines.get(ticker, pd.DataFrame({"published_at": [], "score": []}))
        features = build_feature_frame(
            dividend_adjusted(frame), news, horizon=horizon, threshold=threshold
        )
        if features["target_return"].notna().sum() < MIN_TRAINING_ROWS:
            raise InsufficientDataError(
                f"{ticker}: {len(features)} usable rows, need at least {MIN_TRAINING_ROWS}"
            )
        # Baseline input only (5-day moving-average forecast); never a model feature
        features["sma_5"] = features["close"].rolling(5).mean()
        frames[ticker] = features
    return frames


def _samples(frames: dict[str, pd.DataFrame], cuts: CutDates, horizon: int = 1) -> pd.DataFrame:
    """Every labelled row of every ticker with its period, ticker and row position."""
    parts = []
    for ticker, frame in frames.items():
        labelled = frame[frame["target_return"].notna()].copy()
        labelled["period"] = assign_periods(labelled["date"], cuts, horizon)
        labelled["ticker"] = ticker
        labelled["row"] = labelled.index
        parts.append(labelled)
    samples = pd.concat(parts, ignore_index=True)
    return samples[samples["period"].notna()].reset_index(drop=True)


def _windows(scaled: dict[str, np.ndarray], rows: pd.DataFrame) -> np.ndarray:
    return np.concatenate(
        [
            lstm_model.make_sequences(scaled[ticker], SEQ_LENGTH, group["row"].to_numpy())
            for ticker, group in rows.groupby("ticker", sort=False)
        ]
    )


def _by_ticker_order(rows: pd.DataFrame) -> pd.DataFrame:
    """Rows reordered the way `_windows` emits them (grouped by ticker, original order)."""
    return pd.concat([group for _, group in rows.groupby("ticker", sort=False)])


@dataclass
class FittedModels:
    scaler: StandardScaler
    y_std: float
    lstm: lstm_model.LSTMForecaster
    calibrator: DirectionCalibrator
    forest: RandomForestClassifier
    training: dict


def lstm_outputs(
    lstm: lstm_model.LSTMForecaster, y_std: float, windows: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Forecast return and its MC-dropout spread, in return units."""
    forecast = lstm_model.predict(lstm, windows) * y_std
    spread = lstm_model.mc_dropout_std(lstm, windows, MC_PASSES, MC_SEED) * y_std
    return forecast, spread


def select_rf_params(
    train: pd.DataFrame,
    val: pd.DataFrame,
    rf_base: dict,
    rf_grid: dict,
    features: list[str] = FEATURE_COLUMNS,
) -> tuple[dict, list[dict]]:
    """
    Fit one forest per grid value on `train`, score each on `val` by balanced accuracy and
    return the winner plus every score. A tie goes to the larger min_samples_leaf (the
    simpler forest). `rf_grid` holds a single parameter.
    """
    ((name, values),) = rf_grid.items()
    X_train, y_train = train[features].to_numpy(), train["target_signal"].astype(int)
    X_val, y_val = val[features].to_numpy(), val["target_signal"].astype(int)
    scores = []
    for value in values:
        forest = RandomForestClassifier(**rf_base, **{name: value}, n_jobs=-1).fit(
            X_train, y_train.to_numpy()
        )
        summary = metrics.classification_summary(
            y_val.to_numpy(), forest.predict(X_val), CLASS_ORDER, probabilities=None
        )
        scores.append({name: value, f"val_{RF_SELECTION_METRIC}": summary[RF_SELECTION_METRIC]})
    best = max(scores, key=lambda s: (s[f"val_{RF_SELECTION_METRIC}"], s[name]))
    return {**rf_base, name: best[name]}, scores


def fit_and_evaluate(
    frames: dict[str, pd.DataFrame],
    cuts: CutDates,
    *,
    lstm_epochs: int = LSTM_HYPERPARAMS["max_epochs"],
    rf_base: dict = RF_PARAMS,
    rf_grid: dict = RF_GRID,
    features: list[str] = FEATURE_COLUMNS,
    horizon: int = 1,
) -> tuple[FittedModels, dict, pd.DataFrame]:
    """Fit everything for one set of cut dates; return the models, metrics, test rows."""
    samples = _samples(frames, cuts, horizon)
    train = samples[samples["period"] == "train"]

    scaler = StandardScaler().fit(train[features])
    y_std = float(train["target_return"].std())
    scaled = {
        ticker: scaler.transform(frame[features]).astype(np.float32)
        for ticker, frame in frames.items()
    }

    # A window needs SEQ_LENGTH rows of history; earlier rows only feed the classifier
    windowed = _by_ticker_order(samples[samples["row"] >= SEQ_LENGTH - 1])
    lstm_rows = {p: windowed[windowed["period"] == p] for p in ("train", "val", "test")}
    X = {p: _windows(scaled, rows) for p, rows in lstm_rows.items()}
    y = {
        p: (rows["target_return"].to_numpy() / y_std).astype(np.float32)
        for p, rows in lstm_rows.items()
    }

    started = time.perf_counter()
    lstm, fit_info = lstm_model.train_lstm(
        X["train"],
        y["train"],
        X["val"],
        y["val"],
        epochs=lstm_epochs,
        batch_size=LSTM_HYPERPARAMS["batch_size"],
        lr=LSTM_HYPERPARAMS["lr"],
        patience=LSTM_HYPERPARAMS["early_stopping_patience"],
        seed=SEED,
    )
    lstm_seconds = time.perf_counter() - started

    val_forecast, val_spread = lstm_outputs(lstm, y_std, X["val"])
    val_actual = lstm_rows["val"]["target_return"].to_numpy()
    moved = (np.sign(val_forecast) != 0) & (np.sign(val_actual) != 0)
    calibrator = DirectionCalibrator().fit(
        certainty(val_forecast[moved], val_spread[moved]),
        np.sign(val_forecast[moved]) == np.sign(val_actual[moved]),
    )

    started = time.perf_counter()
    rf_params, rf_scores = select_rf_params(
        train, samples[samples["period"] == "val"], rf_base, rf_grid, features
    )
    # The chosen settings are refitted on train + validation, so the forest sees every
    # pre-test row; the test period is scored once, below
    fit_rows = samples[samples["period"].isin(["train", "val"])]
    forest = RandomForestClassifier(**rf_params, n_jobs=-1).fit(
        fit_rows[features].to_numpy(), fit_rows["target_signal"].astype(int).to_numpy()
    )
    forest_seconds = time.perf_counter() - started

    test = lstm_rows["test"].copy()
    test["forecast_return"], test["spread"] = lstm_outputs(lstm, y_std, X["test"])
    test["confidence"] = calibrator.predict(certainty(test["forecast_return"], test["spread"]))
    probabilities = forest.predict_proba(test[features].to_numpy())
    classes = [int(c) for c in forest.classes_]
    for label in CLASS_ORDER:
        test[f"p_{label}"] = probabilities[:, classes.index(label)] if label in classes else 0.0
    test["rf_signal"] = np.array(classes)[np.argmax(probabilities, axis=1)]

    period_summary = {
        p: {
            "rows": int((samples["period"] == p).sum()),
            "lstm_windows": int(len(lstm_rows[p])),
            "first_date": samples.loc[samples["period"] == p, "date"].min().date().isoformat(),
            "last_date": samples.loc[samples["period"] == p, "date"].max().date().isoformat(),
        }
        for p in ("train", "val", "test")
    }
    training = {
        **fit_info,
        "lstm_seconds": round(lstm_seconds, 1),
        "random_forest_seconds": round(forest_seconds, 1),
        "y_std": y_std,
        "rf_params": rf_params,
        "rf_selection": {
            "metric": f"{RF_SELECTION_METRIC} on the validation period",
            "grid": rf_scores,
        },
        "val_direction_hit_rate": float(
            np.mean(np.sign(val_forecast[moved]) == np.sign(val_actual[moved]))
        ),
        # All a with/without-sentiment choice may look at: validation only, never test
        "validation": {
            "lstm_rmse_pct": metrics.price_error_summary(
                lstm_rows["val"]["close"].to_numpy() * (1 + val_forecast),
                lstm_rows["val"]["next_close"].to_numpy(),
            )["rmse_pct"],
            "rf_balanced_accuracy": max(score[f"val_{RF_SELECTION_METRIC}"] for score in rf_scores),
        },
    }
    models = FittedModels(scaler, y_std, lstm, calibrator, forest, training)
    evaluation = evaluate(test, train, training["val_direction_hit_rate"], horizon)
    evaluation["periods"] = period_summary
    return models, evaluation, test


def _majority_direction(train: pd.DataFrame) -> int:
    moved = train.loc[train["target_return"] != 0, "target_return"]
    return 1 if (moved > 0).mean() >= 0.5 else -1


def _ticker_lstm_summary(rows: pd.DataFrame, majority_direction: int) -> dict:
    actual = rows["next_close"].to_numpy()
    close = rows["close"].to_numpy()
    model = metrics.price_error_summary(close * (1 + rows["forecast_return"].to_numpy()), actual)
    naive = metrics.price_error_summary(close, actual)
    hits, n = metrics.direction_hits(
        rows["forecast_return"].to_numpy(), rows["target_return"].to_numpy()
    )
    base_hits, base_n = metrics.direction_hits(
        np.full(len(rows), majority_direction), rows["target_return"].to_numpy()
    )
    theil_u = model["rmse_pct"] / naive["rmse_pct"]
    return {
        "test_rows": int(len(rows)),
        **{f"lstm_{k}": v for k, v in model.items()},
        "naive_rmse_pct": naive["rmse_pct"],
        "theil_u": theil_u,
        "beats_naive": bool(theil_u < 1),
        "directional_accuracy": hits / n if n else None,
        "majority_direction_accuracy": base_hits / base_n if base_n else None,
        "rf_accuracy": float(np.mean(rows["rf_signal"] == rows["target_signal"])),
    }


def evaluate(
    test: pd.DataFrame, train: pd.DataFrame, val_hit_rate: float, horizon: int = 1
) -> dict:
    """Test-period metrics for both models and every baseline."""
    actual = test["next_close"].to_numpy()
    close = test["close"].to_numpy()
    target = test["target_return"].to_numpy()
    forecast = close * (1 + test["forecast_return"].to_numpy())

    lstm_err = metrics.price_error_summary(forecast, actual)
    naive_err = metrics.price_error_summary(close, actual)
    sma_err = metrics.price_error_summary(test["sma_5"].to_numpy(), actual)

    daily = (
        pd.DataFrame(
            {
                "date": test["date"].to_numpy(),
                "model": metrics.relative_errors(forecast, actual) ** 2,
                "naive": metrics.relative_errors(close, actual) ** 2,
            }
        )
        .groupby("date")[["model", "naive"]]
        .mean()
    )

    majority_direction = _majority_direction(train)
    base_hits, base_n = metrics.direction_hits(np.full(len(test), majority_direction), target)
    majority_rate = base_hits / base_n
    trend = np.where(close > test["SMA_20"].to_numpy(), 1, -1)
    sma_direction = np.sign(test["sma_5"].to_numpy() - close)

    hit = (np.sign(test["forecast_return"]) == np.sign(target)).to_numpy()
    moved = (np.sign(test["forecast_return"]) != 0).to_numpy() & (np.sign(target) != 0)
    confidence = test["confidence"].to_numpy()
    threshold = settings.LOW_CONFIDENCE_THRESHOLD
    confident = moved & (confidence >= threshold)
    confident_hits = int(hit[confident].sum())
    confident_ci = metrics.wilson_interval(confident_hits, int(confident.sum()))

    y_true = test["target_signal"].astype(int).to_numpy()
    probabilities = test[[f"p_{label}" for label in CLASS_ORDER]].to_numpy()
    class_freq = train["target_signal"].astype(int).value_counts(normalize=True)
    majority_class = int(class_freq.idxmax())
    majority_probs = np.tile([class_freq.get(label, 0.0) for label in CLASS_ORDER], (len(test), 1))

    per_ticker = {
        ticker: _ticker_lstm_summary(rows, majority_direction)
        for ticker, rows in test.groupby("ticker", sort=True)
    }
    for ticker, rows in test.groupby("ticker"):
        per_ticker[ticker]["rf_majority_class_accuracy"] = float(
            np.mean(rows["target_signal"].astype(int) == majority_class)
        )

    return {
        "lstm": {
            **lstm_err,
            "theil_u": lstm_err["rmse_pct"] / naive_err["rmse_pct"],
            "diebold_mariano_vs_naive": metrics.diebold_mariano(
                daily["model"].to_numpy(), daily["naive"].to_numpy(), lag=horizon - 1
            ),
            "direction": metrics.direction_summary(
                test["forecast_return"].to_numpy(), target, majority_rate
            ),
        },
        "baselines": {
            "naive": {**naive_err, "theil_u": 1.0},
            "sma_5": {
                **sma_err,
                "theil_u": sma_err["rmse_pct"] / naive_err["rmse_pct"],
                "direction": metrics.direction_summary(sma_direction, target, majority_rate),
            },
            "majority_direction": {
                "direction": "up" if majority_direction > 0 else "down",
                "directional_accuracy": majority_rate,
                "rows": base_n,
            },
            "sma_20_trend": {
                "direction": metrics.direction_summary(trend, target, majority_rate),
                "classifier": metrics.classification_summary(
                    y_true, trend, CLASS_ORDER, probabilities=None
                ),
            },
            "majority_class": {
                "label": SIGNAL_LABELS[majority_class],
                **metrics.classification_summary(
                    y_true, np.full(len(test), majority_class), CLASS_ORDER, majority_probs
                ),
            },
        },
        "confidence": {
            "threshold": threshold,
            "brier": metrics.brier(confidence[moved], hit[moved]),
            "brier_constant_baseline": metrics.brier(
                np.full(int(moved.sum()), val_hit_rate), hit[moved]
            ),
            "reliability": metrics.reliability_table(
                confidence[moved], hit[moved].astype(float), CONFIDENCE_BANDS
            ),
            "share_at_or_above_threshold": float(confident.sum() / max(moved.sum(), 1)),
            "directional_accuracy_at_or_above_threshold": (
                confident_hits / int(confident.sum()) if confident.sum() else None
            ),
            "ci95_at_or_above_threshold": list(confident_ci) if confident.sum() else None,
        },
        "random_forest": metrics.classification_summary(
            y_true, test["rf_signal"].to_numpy(), CLASS_ORDER, probabilities
        ),
        "per_ticker": per_ticker,
    }


def _fold_summary(evaluation: dict) -> dict:
    return {
        "test_first_date": evaluation["periods"]["test"]["first_date"],
        "test_last_date": evaluation["periods"]["test"]["last_date"],
        "test_rows": evaluation["periods"]["test"]["lstm_windows"],
        "lstm_theil_u": evaluation["lstm"]["theil_u"],
        "lstm_directional_accuracy": evaluation["lstm"]["direction"]["directional_accuracy"],
        "majority_direction_accuracy": evaluation["baselines"]["majority_direction"][
            "directional_accuracy"
        ],
        "dm_p_value": evaluation["lstm"]["diebold_mariano_vs_naive"]["p_value"],
        "confidence_brier": evaluation["confidence"]["brier"],
        "confidence_brier_baseline": evaluation["confidence"]["brier_constant_baseline"],
        "share_at_or_above_threshold": evaluation["confidence"]["share_at_or_above_threshold"],
        "rf_accuracy": evaluation["random_forest"]["accuracy"],
        "rf_balanced_accuracy": evaluation["random_forest"]["balanced_accuracy"],
        "majority_class_accuracy": evaluation["baselines"]["majority_class"]["accuracy"],
    }


def walk_forward(frames: dict[str, pd.DataFrame], **fit_kwargs) -> dict:
    dates = pd.concat([f["date"] for f in frames.values()])
    folds = []
    for cuts in walk_forward_folds(dates, WALK_FORWARD_FOLDS, WALK_FORWARD_TEST_FRAC):
        models, evaluation, _ = fit_and_evaluate(frames, cuts, **fit_kwargs)
        folds.append(
            {
                **_fold_summary(evaluation),
                "rf_params": models.training["rf_params"],
                "lstm_seconds": models.training["lstm_seconds"],
                "random_forest_seconds": models.training["random_forest_seconds"],
            }
        )
    keys = [k for k, v in folds[0].items() if isinstance(v, float)]
    return {
        "folds": folds,
        "mean": {k: float(np.mean([f[k] for f in folds])) for k in keys},
        "std": {k: float(np.std([f[k] for f in folds])) for k in keys},
    }


@dataclass
class Candidate:
    models: FittedModels
    metadata: dict
    frames: dict[str, pd.DataFrame]
    test: pd.DataFrame


def fit_candidate(
    raw: dict[str, pd.DataFrame],
    dataset: dict,
    *,
    version: str | None = None,
    run_walk_forward: bool = True,
    lstm_epochs: int = LSTM_HYPERPARAMS["max_epochs"],
    rf_base: dict = RF_PARAMS,
    rf_grid: dict = RF_GRID,
    headlines: dict[str, pd.DataFrame] | None = None,
    news: dict | None = None,
    fallback_model_version: str | None = None,
    horizon: int = 1,
    threshold: float = SIGNAL_THRESHOLD,
) -> Candidate:
    """
    Fit the final 70/15/15 models and, optionally, the walk-forward folds; return the models,
    their metadata, the feature frames and the scored test rows (nothing is written).
    `dataset` describes the input (name and per-file hashes) and is stored with the model.
    With `headlines` the model also reads the news inputs; `news` then describes the news
    dataset, and `fallback_model_version` names the price-only model served when the news
    sources are stale (PRD.md FR22).
    """
    version = version or new_model_version()
    started = time.perf_counter()
    features = FEATURE_COLUMNS + (SENTIMENT_COLUMNS if headlines is not None else [])
    frames = prepare_frames(raw, headlines, horizon, threshold)
    cuts = shared_cut_dates(pd.concat([f["date"] for f in frames.values()]), TRAIN_FRAC, VAL_FRAC)
    fit_kwargs = {
        "lstm_epochs": lstm_epochs,
        "rf_base": rf_base,
        "rf_grid": rf_grid,
        "features": features,
        "horizon": horizon,
    }
    models, evaluation, test = fit_and_evaluate(frames, cuts, **fit_kwargs)
    folds = walk_forward(frames, **fit_kwargs) if run_walk_forward else None

    importances = sorted(
        zip(features, models.forest.feature_importances_, strict=True), key=lambda kv: -kv[1]
    )
    metadata = {
        "model_version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "tickers": sorted(frames),
        "dataset": dataset,
        "data": {
            "split": {
                "train": TRAIN_FRAC,
                "val": VAL_FRAC,
                "test": round(1 - TRAIN_FRAC - VAL_FRAC, 2),
            },
            "cut_dates": {
                "val_start": cuts.val_start.date().isoformat(),
                "test_start": cuts.test_start.date().isoformat(),
                "test_end": cuts.test_end.date().isoformat(),
            },
            "periods": evaluation.pop("periods"),
            "horizon_trading_days": horizon,
            "label_threshold": threshold,
        },
        "features": features,
        "news": news,
        "fallback_model_version": fallback_model_version,
        "seed": SEED,
        "lstm": {
            "hyperparameters": {**LSTM_HYPERPARAMS, "max_epochs": lstm_epochs},
            "training": models.training,
        },
        "random_forest": {
            "hyperparameters": models.training["rf_params"],
            "grid": {name: list(values) for name, values in rf_grid.items()},
            "feature_importance": [{"feature": f, "importance": float(i)} for f, i in importances],
        },
        "evaluation": evaluation,
        "walk_forward": folds,
        "training_seconds_total": round(time.perf_counter() - started, 1),
        "library_versions": {
            "torch": torch.__version__,
            "sklearn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
    }
    lstm_eval = evaluation["lstm"]
    logger.info(
        f"{version}: LSTM Theil U {lstm_eval['theil_u']:.3f}, direction "
        f"{lstm_eval['direction']['directional_accuracy']:.3f}; "
        f"RF accuracy {evaluation['random_forest']['accuracy']:.3f}"
    )
    return Candidate(models, metadata, frames, test)


def train_and_save(
    raw: dict[str, pd.DataFrame], dataset: dict, model_dir: str | Path, **kwargs
) -> dict:
    """
    `fit_candidate` and save the artifacts and evaluation report under
    <model_dir>/<version>/. This only ever creates a candidate: it never touches the active
    pointer (ml/promote.py, Workflow.md Appendix E).
    """
    candidate = fit_candidate(raw, dataset, **kwargs)
    version = candidate.metadata["model_version"]
    save_artifacts(candidate.models, candidate.metadata, Path(model_dir), version)
    return candidate.metadata


def save_artifacts(models: FittedModels, metadata: dict, model_dir: Path, version: str) -> None:
    out = model_dir / version
    out.mkdir(parents=True, exist_ok=True)
    torch.save(models.lstm.state_dict(), out / "lstm.pt")
    joblib.dump(
        {
            "model_version": version,
            "scaler": models.scaler,
            "y_std": models.y_std,
            "seq_length": SEQ_LENGTH,
            "features": metadata["features"],
        },
        out / "preprocess.joblib",
    )
    joblib.dump({"model_version": version, "model": models.forest}, out / "random_forest.joblib")
    joblib.dump({"model_version": version, "model": models.calibrator}, out / "calibrator.joblib")
    (out / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    write_report(metadata, out / REPORT_FILE)
