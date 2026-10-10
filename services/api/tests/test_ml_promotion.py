"""
Candidates and promotion (Workflow.md Appendix E, decision 2026-10-10): training never
replaces the live model, and a candidate without a complete evaluation report is refused.
"""

import hashlib
import json
import shutil
from functools import partial
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from core.config import settings
from ml import promote as promotion
from ml.dataset import CSV_COLUMNS, MANIFEST
from ml.features import FEATURE_COLUMNS
from ml.training import RF_PARAMS, select_rf_params, train_and_save
from tests.synthetic import make_ohlcv
from worker import tasks

SMALL_RF = {**RF_PARAMS, "n_estimators": 5, "max_depth": 3}
SMALL_GRID = {"min_samples_leaf": (5, 20)}
MOCK_PRICES = {
    "MOCKA": make_ohlcv(600, seed=1).assign(dividend_factor=1.0),
    "MOCKB": make_ohlcv(600, seed=2).assign(dividend_factor=1.0),
}
tiny_training = partial(train_and_save, lstm_epochs=1, rf_base=SMALL_RF, rf_grid=SMALL_GRID)


@pytest.fixture(scope="module")
def candidates(tmp_path_factory):
    """A complete candidate (with walk-forward) and an incomplete one (without)."""
    root = tmp_path_factory.mktemp("candidates")
    dataset = {"version": "MOCK", "sha256": {}}
    tiny_training(MOCK_PRICES, dataset, root, version="MOCK-complete")
    tiny_training(MOCK_PRICES, dataset, root, version="MOCK-partial", run_walk_forward=False)
    return root


@pytest.fixture
def dirs(tmp_path, candidates):
    """Fresh copies per test: candidates, a live model folder with an active model, reports."""
    cand = tmp_path / "candidates"
    shutil.copytree(candidates, cand)
    models = tmp_path / "models"
    models.mkdir()
    promotion.set_active(models, "MOCK-active")
    return cand, models, tmp_path / "reports"


def test_promotion_switches_the_active_model_and_logs_it(dirs):
    cand, models, reports = dirs
    entry = promotion.promote("MOCK-complete", cand, models, reports)

    assert promotion.active_version(models) == "MOCK-complete"
    assert (models / "MOCK-complete" / "lstm.pt").exists()
    assert (reports / "evaluation_MOCK-complete.md").exists()
    assert (reports / "evaluation_MOCK-complete.json").exists()
    log = [json.loads(line) for line in (models / promotion.PROMOTION_LOG).read_text().splitlines()]
    assert log == [entry]
    assert entry["model_version"] == "MOCK-complete" and entry["previous_version"] == "MOCK-active"


def test_a_news_model_needs_its_price_only_fallback_promoted_first(dirs):
    cand, models, reports = dirs
    shutil.copytree(cand / "MOCK-complete", cand / "MOCK-news")
    meta_path = cand / "MOCK-news" / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(model_version="MOCK-news", fallback_model_version="MOCK-complete")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    promotion.write_report(meta, cand / "MOCK-news" / promotion.REPORT_FILE)

    with pytest.raises(promotion.PromotionRefused, match="fallback MOCK-complete"):
        promotion.promote("MOCK-news", cand, models, reports)
    promotion.promote("MOCK-complete", cand, models, reports)
    promotion.promote("MOCK-news", cand, models, reports)
    assert promotion.active_version(models) == "MOCK-news"


def test_promotion_without_walk_forward_is_refused(dirs):
    cand, models, reports = dirs
    with pytest.raises(promotion.PromotionRefused, match="walk-forward"):
        promotion.promote("MOCK-partial", cand, models, reports)
    assert promotion.active_version(models) == "MOCK-active"
    assert not (models / promotion.PROMOTION_LOG).exists()


def test_promotion_without_a_report_is_refused(dirs):
    cand, models, reports = dirs
    (cand / "MOCK-complete" / "report.md").unlink()
    with pytest.raises(promotion.PromotionRefused, match="report.md"):
        promotion.promote("MOCK-complete", cand, models, reports)
    assert promotion.active_version(models) == "MOCK-active"


def test_a_report_that_does_not_match_its_metadata_is_refused(dirs):
    cand, models, reports = dirs
    report = cand / "MOCK-complete" / "report.md"
    report.write_text(report.read_text().replace("Theil's U", "Theil U"))
    with pytest.raises(promotion.PromotionRefused, match="does not match"):
        promotion.promote("MOCK-complete", cand, models, reports)


def test_unknown_candidate_and_second_promotion_are_refused(dirs):
    cand, models, reports = dirs
    with pytest.raises(promotion.PromotionRefused, match="No candidate"):
        promotion.promote("MOCK-missing", cand, models, reports)
    promotion.promote("MOCK-complete", cand, models, reports)
    with pytest.raises(promotion.PromotionRefused, match="never overwritten"):
        promotion.promote("MOCK-complete", cand, models, reports)


def _write_mock_dataset(root, *_args):
    """Stands in for build_dataset (no database here): MOCK CSVs plus a manifest."""
    out = root / "MOCK-dataset"
    out.mkdir(parents=True)
    entries = {}
    for ticker, frame in MOCK_PRICES.items():
        path = out / f"{ticker}.csv"
        frame.assign(date=pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d"))[
            CSV_COLUMNS
        ].to_csv(path, index=False, lineterminator="\n")
        entries[ticker] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (out / MANIFEST).write_text(json.dumps({"version": "MOCK-dataset", "tickers": entries}))
    return out


def test_weekly_retrain_leaves_the_live_model_and_tracked_data_alone(tmp_path, monkeypatch):
    models, committed = tmp_path / "models", tmp_path / "data"
    models.mkdir()
    committed.mkdir()
    promotion.set_active(models, "MOCK-active")
    monkeypatch.setattr(settings, "MODEL_DIR", str(models))
    monkeypatch.setattr(settings, "DATASET_DIR", str(committed))
    monkeypatch.setattr(settings, "CANDIDATE_DIR", str(tmp_path / "candidates"))
    used_dirs = []
    monkeypatch.setattr(
        tasks,
        "build_dataset",
        lambda db, tickers, root: used_dirs.append(root) or _write_mock_dataset(root),
    )
    monkeypatch.setattr(tasks, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(tasks, "train_and_save", tiny_training)

    result = tasks.train_models(["MOCKA", "MOCKB"])

    assert result["status"] == "candidate"
    assert promotion.active_version(models) == "MOCK-active"
    assert sorted(p.name for p in models.iterdir()) == ["latest.json"]
    assert list(committed.iterdir()) == []
    assert used_dirs == [settings.candidate_dataset_dir]
    candidate = settings.candidate_model_dir / result["model_version"]
    assert promotion.report_problems(candidate, result["model_version"]) == []


@pytest.mark.filterwarnings("ignore:A single label was found")
def test_rf_selection_breaks_ties_toward_the_simpler_forest():
    # One class only: every grid value scores the same, so the largest leaf must win
    rows = pd.DataFrame(np.random.default_rng(0).normal(size=(200, len(FEATURE_COLUMNS))))
    rows.columns = FEATURE_COLUMNS
    rows["target_signal"] = 0
    params, scores = select_rf_params(
        rows[:150], rows[150:], SMALL_RF, {"min_samples_leaf": (5, 10, 20, 40)}
    )
    assert params["min_samples_leaf"] == 40
    assert [s["min_samples_leaf"] for s in scores] == [5, 10, 20, 40]
