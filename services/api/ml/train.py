"""
Training CLI (never run inside the API).

    python -m ml.dataset                                   # new dataset (candidate folder)
    python -m ml.train --dataset psx18-2026-10-07          # train and evaluate a candidate
    python -m ml.promote <model_version>                   # make it the live model

Training only ever creates a candidate under CANDIDATE_DIR/models/<model_version>/ (not in
git), with its evaluation report (`report.md`). The live model changes only through
`ml.promote`, which also copies the report to ml/reports/ to be committed as evidence.
"""

import argparse
import logging

from core.config import settings
from ml.dataset import dataset_reference, find_dataset, load_dataset
from ml.report import REPORT_FILE
from ml.training import LSTM_HYPERPARAMS, train_and_save


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate an InvestIQ candidate model")
    parser.add_argument("--dataset", required=True, help="dataset version (committed or candidate)")
    parser.add_argument("--epochs", type=int, default=LSTM_HYPERPARAMS["max_epochs"])
    parser.add_argument("--no-walk-forward", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    manifest, raw = load_dataset(find_dataset(args.dataset))
    meta = train_and_save(
        raw,
        dataset_reference(manifest),
        settings.candidate_model_dir,
        run_walk_forward=not args.no_walk_forward,
        lstm_epochs=args.epochs,
    )
    version = meta["model_version"]
    print(f"Candidate {version}: {settings.candidate_model_dir / version / REPORT_FILE}")
    print(f"Promote it with: python -m ml.promote {version}")


if __name__ == "__main__":
    main()
