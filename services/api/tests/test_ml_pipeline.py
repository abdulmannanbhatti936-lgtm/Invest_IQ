import json
import shutil
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
import pytest

from ml.features import (
    FEATURE_COLUMNS,
    WARMUP_ROWS,
    add_sentiment_feature,
    add_targets,
    build_feature_frame,
    training_rows,
)
from ml.inference import ModelNotFoundError, load_bundle, models_agree, predict_next_day
from ml.lstm_model import make_sequences, mc_dropout_std
from ml.splits import assign_periods, chronological_split, shared_cut_dates
from ml.training import (
    RF_PARAMS,
    SEQ_LENGTH,
    InsufficientDataError,
    prepare_frames,
    train_and_save,
)
from tests.fixtures.build_model_fixture import FIXTURE_DIR, FIXTURE_VERSION, MOCK_TICKERS
from tests.synthetic import make_ohlcv

# ---- Feature frame (Workflow.md Step 3.2; indicator values: tests/test_indicators.py)


def test_feature_frame_drops_only_warmup_and_keeps_latest_row():
    raw = make_ohlcv(200)
    feat = build_feature_frame(raw)
    assert feat[FEATURE_COLUMNS].isna().sum().sum() == 0
    assert len(feat) == 200 - (WARMUP_ROWS - 1)
    # The most recent day must survive: it is what we predict from
    assert feat["date"].iloc[-1] == pd.Timestamp(raw["date"].iloc[-1]).normalize()
    assert pd.isna(feat["target_return"].iloc[-1])
    assert len(training_rows(feat)) == len(feat) - 1


def test_targets_are_next_day():
    df = pd.DataFrame({"close": [100.0, 102.0, 100.0, 100.5]})
    t = add_targets(df)
    assert t["target_return"].iloc[0] == pytest.approx(0.02)
    assert t["target_signal"].iloc[0] == 1  # +2% -> BUY
    assert t["target_signal"].iloc[1] == -1  # -1.96% -> SELL
    assert t["target_signal"].iloc[2] == 0  # +0.5% -> HOLD
    assert pd.isna(t["target_signal"].iloc[3])  # no tomorrow yet


def test_sentiment_merge_ignores_unscored():
    df = pd.DataFrame({"date": pd.to_datetime(["2026-01-01", "2026-01-02"])})
    s = [
        SimpleNamespace(timestamp=pd.Timestamp("2026-01-01 10:00"), sentiment_score=0.5),
        SimpleNamespace(timestamp=pd.Timestamp("2026-01-01 12:00"), sentiment_score=None),
    ]
    out = add_sentiment_feature(df, s)
    assert out["sentiment_score"].tolist() == [0.5, 0.0]


def test_chronological_split_never_leaks_future_dates():
    df = make_ohlcv(300).sample(frac=1, random_state=1)  # deliberately shuffled input
    split = chronological_split(df)
    assert len(split.train) == 210 and len(split.val) == 45 and len(split.test) == 45
    assert split.train["date"].max() < split.val["date"].min()
    assert split.val["date"].max() < split.test["date"].min()


def test_sequences_only_look_backwards():
    data = np.arange(10, dtype=float).reshape(-1, 1)
    seqs = make_sequences(data, seq_length=3, end_indices=np.array([2, 9]))
    assert seqs[0].ravel().tolist() == [0, 1, 2]
    assert seqs[1].ravel().tolist() == [7, 8, 9]


def test_prepare_refuses_short_history():
    with pytest.raises(InsufficientDataError):
        prepare_frames({"MOCKSHORT": make_ohlcv(200).assign(dividend_factor=1.0)})


# ---- Training run (tiny, on MOCK data) (Workflow.md Steps 3.4-3.5)


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    raw = {
        "MOCKA": make_ohlcv(600, seed=1).assign(dividend_factor=1.0),
        "MOCKB": make_ohlcv(600, seed=2).assign(dividend_factor=1.0),
    }
    model_dir = tmp_path_factory.mktemp("models")
    meta = train_and_save(
        raw,
        {"version": "MOCK", "sha256": {}},
        model_dir,
        version="MOCK-run-v1",
        lstm_epochs=1,
        rf_params={**RF_PARAMS, "n_estimators": 5, "max_depth": 3},
    )
    return SimpleNamespace(dir=model_dir, meta=meta, raw=raw)


def test_every_artifact_carries_the_model_version(trained):
    root = trained.dir / "MOCK-run-v1"
    for name in ("preprocess.joblib", "random_forest.joblib", "calibrator.joblib"):
        assert joblib.load(root / name)["model_version"] == "MOCK-run-v1"
    assert (root / "lstm.pt").exists()
    assert json.loads((root / "metadata.json").read_text())["model_version"] == "MOCK-run-v1"
    assert json.loads((trained.dir / "latest.json").read_text())["model_version"] == "MOCK-run-v1"


def test_metadata_logs_data_range_hyperparameters_metrics_and_timing(trained):
    meta = trained.meta
    assert meta["seed"] == 42 and meta["tickers"] == ["MOCKA", "MOCKB"]
    cuts = meta["data"]["cut_dates"]
    periods = meta["data"]["periods"]
    assert periods["train"]["last_date"] < cuts["val_start"] <= periods["val"]["first_date"]
    assert periods["val"]["last_date"] < cuts["test_start"] <= periods["test"]["first_date"]
    assert meta["lstm"]["hyperparameters"]["mc_dropout_passes"] == 30
    assert meta["random_forest"]["hyperparameters"]["n_estimators"] == 5
    assert meta["lstm"]["training"]["lstm_seconds"] >= 0
    assert meta["training_seconds_total"] > 0
    ev = meta["evaluation"]
    assert set(ev) >= {"lstm", "baselines", "confidence", "random_forest", "per_ticker"}
    assert ev["baselines"]["naive"]["theil_u"] == 1.0
    assert set(ev["per_ticker"]) == {"MOCKA", "MOCKB"}
    assert len(meta["walk_forward"]["folds"]) == 3


def test_scaler_is_fitted_on_the_training_period_only(trained):
    frames = prepare_frames(trained.raw)
    cuts = shared_cut_dates(pd.concat([f["date"] for f in frames.values()]))
    train_rows = []
    for frame in frames.values():
        labelled = frame[frame["target_return"].notna()]
        train_rows.append(labelled[assign_periods(labelled["date"], cuts) == "train"])
    expected = pd.concat(train_rows)[FEATURE_COLUMNS].mean().to_numpy()
    scaler = joblib.load(trained.dir / "MOCK-run-v1" / "preprocess.joblib")["scaler"]
    np.testing.assert_allclose(scaler.mean_, expected, rtol=1e-9)


# ---- Inference against the frozen MOCK fixture (Workflow.md Steps 3.7, 3.9)


@pytest.fixture(scope="module")
def bundle():
    return load_bundle(FIXTURE_DIR)


def test_fixture_matches_the_current_pipeline(bundle):
    # If this fails, rebuild it: python -m tests.fixtures.build_model_fixture
    assert bundle.version == FIXTURE_VERSION
    assert bundle.features == FEATURE_COLUMNS and bundle.seq_length == SEQ_LENGTH
    assert bundle.metadata["tickers"] == MOCK_TICKERS


def test_inference_is_valid_and_deterministic(bundle):
    frame = build_feature_frame(make_ohlcv(400, seed=9))
    first = predict_next_day(bundle, frame)
    second = predict_next_day(load_bundle(FIXTURE_DIR, FIXTURE_VERSION), frame)
    assert first == second
    assert first["model_version"] == FIXTURE_VERSION
    assert first["as_of"] == frame["date"].iloc[-1].date()
    assert first["forecast_price"] == pytest.approx(
        frame["close"].iloc[-1] * (1 + first["forecast_return"])
    )
    assert 0 <= first["confidence"] <= 1 and first["spread"] > 0
    assert first["signal"] in {"BUY", "SELL", "HOLD"}
    assert sum(first["class_probabilities"].values()) == pytest.approx(1.0)
    assert first["signal_probability"] == max(first["class_probabilities"].values())


def test_inference_needs_a_full_window(bundle):
    with pytest.raises(ValueError):
        predict_next_day(bundle, build_feature_frame(make_ohlcv(80)))


def test_mc_dropout_spread_is_fixed_and_independent_of_the_batch(bundle):
    windows = np.random.default_rng(0).normal(size=(5, SEQ_LENGTH, len(FEATURE_COLUMNS)))
    together = mc_dropout_std(bundle.lstm, windows, passes=30, seed=42)
    alone = np.array([mc_dropout_std(bundle.lstm, w[None], passes=30, seed=42)[0] for w in windows])
    np.testing.assert_allclose(together, alone, rtol=1e-5)
    np.testing.assert_array_equal(together, mc_dropout_std(bundle.lstm, windows, 30, 42))


def test_coverage_is_the_trained_tickers(bundle):
    assert bundle.covers("mocka") and not bundle.covers("HBL")


def test_artifact_from_another_version_is_refused(tmp_path):
    copy = tmp_path / FIXTURE_VERSION
    shutil.copytree(FIXTURE_DIR / FIXTURE_VERSION, copy)
    joblib.dump({"model_version": "MOCK-other", "model": None}, copy / "calibrator.joblib")
    with pytest.raises(ModelNotFoundError):
        load_bundle(tmp_path, FIXTURE_VERSION)


def test_missing_model_is_reported(tmp_path):
    with pytest.raises(ModelNotFoundError):
        load_bundle(tmp_path)


def test_models_agree():
    assert models_agree("BUY", 0.004)
    assert not models_agree("BUY", -0.004)
    assert models_agree("SELL", -0.02)
    assert models_agree("HOLD", 0.005)
    assert not models_agree("HOLD", 0.03)
