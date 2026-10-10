"""
Promotion: the only way a trained model becomes the one the API serves (Workflow.md
Appendix E, decision 2026-10-10). Training writes candidates; a person promotes one.

    python -m ml.promote <model_version>

A candidate is refused unless its artifacts and full evaluation report are present and the
report matches its metadata (including the walk-forward check and the RF grid), and a model
that reads news is refused until its price-only fallback has been promoted. On success
the candidate is copied next to the models already promoted (a version is never overwritten),
its report is copied to REPORTS_DIR to be committed, latest.json is switched, and a line is
appended to the promotion log. The admin panel button (Phase 9) will call `promote`.
"""

import argparse
import json
import logging
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from core.config import settings
from ml.report import REPORT_FILE, write_report

logger = logging.getLogger(__name__)

POINTER = "latest.json"
PROMOTION_LOG = "promotions.jsonl"
ARTIFACT_FILES = (
    "lstm.pt",
    "preprocess.joblib",
    "random_forest.joblib",
    "calibrator.joblib",
    "metadata.json",
)
EVALUATION_SECTIONS = ("lstm", "baselines", "confidence", "random_forest", "per_ticker")


class PromotionRefused(Exception):
    pass


def active_version(model_dir: Path) -> str | None:
    pointer = model_dir / POINTER
    return json.loads(pointer.read_text())["model_version"] if pointer.exists() else None


def set_active(model_dir: Path, version: str) -> None:
    (model_dir / POINTER).write_text(json.dumps({"model_version": version}) + "\n", newline="\n")


def report_problems(candidate: Path, version: str) -> list[str]:
    """Everything that stops `candidate` from counting as fully evaluated; empty if none."""
    missing = [name for name in (*ARTIFACT_FILES, REPORT_FILE) if not (candidate / name).exists()]
    if missing:
        return [f"missing {', '.join(missing)}"]
    meta = json.loads((candidate / "metadata.json").read_text(encoding="utf-8"))
    problems = []
    if meta.get("model_version") != version:
        problems.append(f"metadata belongs to {meta.get('model_version')}")
    absent = [s for s in EVALUATION_SECTIONS if s not in meta.get("evaluation", {})]
    if absent:
        problems.append(f"evaluation lacks {', '.join(absent)}")
    if not meta.get("walk_forward"):
        problems.append("no walk-forward check")
    if "rf_selection" not in meta.get("lstm", {}).get("training", {}):
        problems.append("no record of the Random Forest grid selection")
    if problems:
        return problems
    with tempfile.TemporaryDirectory() as tmp:
        expected = write_report(meta, Path(tmp) / REPORT_FILE).read_text(encoding="utf-8")
    if (candidate / REPORT_FILE).read_text(encoding="utf-8") != expected:
        problems.append(f"{REPORT_FILE} does not match the metadata")
    return problems


def _headline(meta: dict) -> dict:
    ev = meta["evaluation"]
    return {
        "lstm_theil_u": ev["lstm"]["theil_u"],
        "lstm_directional_accuracy": ev["lstm"]["direction"]["directional_accuracy"],
        "rf_balanced_accuracy": ev["random_forest"]["balanced_accuracy"],
        "confidence_brier": ev["confidence"]["brier"],
    }


def promote(
    version: str,
    candidate_dir: str | Path,
    model_dir: str | Path,
    reports_dir: str | Path,
) -> dict:
    """Make candidate `version` the active model; returns the promotion log entry."""
    candidate, models, reports = Path(candidate_dir) / version, Path(model_dir), Path(reports_dir)
    if not candidate.is_dir():
        raise PromotionRefused(f"No candidate {version} in {candidate_dir}")
    problems = report_problems(candidate, version)
    if problems:
        detail = "; ".join(problems)
        raise PromotionRefused(f"{version} has no complete evaluation report: {detail}")
    if (models / version).exists():
        raise PromotionRefused(
            f"{version} is already in {model_dir}; versions are never overwritten"
        )

    meta = json.loads((candidate / "metadata.json").read_text(encoding="utf-8"))
    fallback = meta.get("fallback_model_version")
    if fallback and not (models / fallback / "metadata.json").exists():
        raise PromotionRefused(
            f"{version} reads news; its price-only fallback {fallback} must be promoted "
            "first, so a forecast is still possible when the news sources are down (FR22)"
        )
    previous = active_version(models)
    models.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    shutil.copytree(candidate, models / version)
    shutil.copyfile(candidate / REPORT_FILE, reports / f"evaluation_{version}.md")
    shutil.copyfile(candidate / "metadata.json", reports / f"evaluation_{version}.json")
    set_active(models, version)

    entry = {
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "model_version": version,
        "previous_version": previous,
        "dataset": meta["dataset"]["version"],
        **_headline(meta),
    }
    with open(models / PROMOTION_LOG, "a", encoding="utf-8", newline="\n") as log:
        log.write(json.dumps(entry) + "\n")
    logger.info(f"Promoted {version} (previously {previous})")
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote a trained candidate to the live model")
    parser.add_argument("version", help="candidate model_version under CANDIDATE_DIR/models")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        entry = promote(
            args.version, settings.candidate_model_dir, settings.MODEL_DIR, settings.REPORTS_DIR
        )
    except PromotionRefused as e:
        print(f"Refused: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(entry, indent=2))
    print("Next: run_predictions, then commit the report in REPORTS_DIR.")


if __name__ == "__main__":
    main()
