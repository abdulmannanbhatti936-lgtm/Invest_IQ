"""
Training CLI.

    python -m ml.train --download              # refresh the CSV dataset, then train
    python -m ml.train --tickers SYS HUBC      # train selected tickers from the CSVs

Writes model artifacts to settings.MODEL_DIR and an evaluation report to
ml/reports/ (committed, so results are documented for the FYP report).
"""

import argparse
import json
import logging
from pathlib import Path

from core.config import settings
from ml.dataset import download_dataset, load_ticker_csv
from ml.training import InsufficientDataError, new_model_version, train_ticker

REPORTS_DIR = Path(__file__).resolve().parent / "reports"


COLUMNS = [
    ("Test days", lambda lstm, rf, svm: f"{lstm['test_samples']:.0f}"),
    ("LSTM RMSE %", lambda lstm, rf, svm: f"{lstm['rmse_pct_of_price']:.2f}%"),
    ("Naive RMSE %", lambda lstm, rf, svm: f"{lstm['baseline_naive_rmse_pct_of_price']:.2f}%"),
    ("LSTM dir. acc.", lambda lstm, rf, svm: _pct(lstm["directional_accuracy"])),
    ("Majority dir.", lambda lstm, rf, svm: _pct(lstm["baseline_majority_direction_accuracy"])),
    ("RF acc.", lambda lstm, rf, svm: _pct(rf["accuracy"])),
    ("RF macro-F1", lambda lstm, rf, svm: f"{rf['f1_macro']:.3f}"),
    ("SVM acc.", lambda lstm, rf, svm: _pct(svm["accuracy"])),
    ("Majority class", lambda lstm, rf, svm: _pct(rf["baseline_majority_class_accuracy"])),
]


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _metrics(m: dict) -> tuple[dict, dict, dict]:
    return (
        m["lstm"]["test_metrics"],
        m["random_forest"]["test_metrics"],
        m["svm"]["test_metrics"],
    )


def _mean(dicts: list[dict]) -> dict:
    return {k: sum(d[k] for d in dicts) / len(dicts) for k in dicts[0]}


def write_report(results: list[dict], version: str) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / f"evaluation_{version}.json").write_text(json.dumps(results, indent=2))

    header = ["Ticker"] + [name for name, _ in COLUMNS]
    lines = [
        f"# Model evaluation — {version}",
        "",
        "Held-out test set = the most recent 15% of each ticker's history "
        "(chronological 70/15/15 split).",
        "Baselines: *naive* = tomorrow's close equals today's; "
        "*majority* = always predict the most common outcome.",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    for m in results:
        cells = [fmt(*_metrics(m)) for _, fmt in COLUMNS]
        lines.append(f"| {m['ticker']} | " + " | ".join(cells) + " |")
    if results:
        per_model = list(zip(*(_metrics(m) for m in results), strict=True))
        means = [_mean(list(dicts)) for dicts in per_model]
        cells = [fmt(*means) for _, fmt in COLUMNS]
        lines.append("| **Mean** | " + " | ".join(cells) + " |")
    path = REPORTS_DIR / f"evaluation_{version}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train InvestIQ prediction models")
    parser.add_argument("--tickers", nargs="*", default=settings.tracked_tickers)
    parser.add_argument("--download", action="store_true", help="re-download the CSV dataset first")
    parser.add_argument("--epochs", type=int, default=60)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    tickers = [t.upper() for t in args.tickers]
    if args.download:
        manifest = download_dataset(tickers, settings.DATASET_DIR)
        print(json.dumps(manifest["tickers"], indent=2))

    version = new_model_version()
    results = []
    for ticker in tickers:
        try:
            df = load_ticker_csv(ticker, settings.DATASET_DIR)
            results.append(
                train_ticker(
                    ticker, df, settings.MODEL_DIR, version=version, lstm_epochs=args.epochs
                )
            )
        except (InsufficientDataError, FileNotFoundError) as e:
            logging.warning(f"Skipping {ticker}: {e}")
    report = write_report(results, version)
    print(f"\nTrained {len(results)}/{len(tickers)} tickers as {version}. Report: {report}")


if __name__ == "__main__":
    main()
