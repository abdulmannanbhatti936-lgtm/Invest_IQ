import json
import shutil
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
import pytest

from ml.features import (
    FEATURE_COLUMNS,
    NEWS_HALF_LIFE_DAYS,
    WARMUP_ROWS,
    add_news_features,
    add_targets,
    build_feature_frame,
    headline_trading_days,
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


def test_targets_at_a_longer_horizon():
    df = pd.DataFrame({"close": [100.0, 101.0, 99.0, 103.0]})
    t = add_targets(df, threshold=0.0224, horizon=2)
    assert t["next_close"].iloc[0] == 99.0
    assert t["target_return"].iloc[1] == pytest.approx(103 / 101 - 1)
    assert t["target_signal"].iloc[1] == 0  # +1.98% is inside the ±2.24% band
    assert t[["target_return", "target_signal"]].iloc[2:].isna().all().all()


# ---- News inputs (Workflow.md Step 4.6, decided 2026-10-11)

TRADING_DAYS = pd.to_datetime(
    ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12"]
)


def _headlines(*rows):
    return pd.DataFrame(
        {
            "published_at": pd.to_datetime([r[0] for r in rows], utc=True),
            "score": [r[1] for r in rows],
        }
    )


def test_headline_after_the_close_counts_for_the_next_trading_day():
    # 10:00 and 10:31 UTC are 15:00 and 15:31 PKT; Saturday news waits for Monday
    published = _headlines(
        ("2026-01-05 10:00", 0.0), ("2026-01-05 10:31", 0.0), ("2026-01-10 06:00", 0.0)
    )["published_at"]
    days = headline_trading_days(published, pd.Series(TRADING_DAYS))
    assert list(days) == list(pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-12"]))


def test_news_after_the_last_stored_close_is_not_used():
    published = _headlines(("2026-01-12 11:00", 0.5))["published_at"]
    assert headline_trading_days(published, pd.Series(TRADING_DAYS)).isna().all()


def test_news_features_decay_and_mark_days_without_news():
    frame = pd.DataFrame({"date": TRADING_DAYS})
    out = add_news_features(
        frame, _headlines(("2026-01-06 05:00", 0.8), ("2026-01-06 06:00", -0.2))
    )
    # No news yet on the first day: weight 0 and sentiment 0, never a guessed value
    assert out["news_weight"].iloc[0] == 0 and out["sentiment"].iloc[0] == 0
    assert out["news_weight"].iloc[1] == pytest.approx(2.0)
    assert out["sentiment"].iloc[1] == pytest.approx(0.3)
    # Three trading days later each headline counts half
    assert out["news_weight"].iloc[1 + NEWS_HALF_LIFE_DAYS] == pytest.approx(1.0)
    assert out["sentiment"].iloc[1 + NEWS_HALF_LIFE_DAYS] == pytest.approx(0.3)


def test_news_older_than_the_window_is_dropped():
    days = pd.Series(pd.bdate_range("2026-01-05", periods=12))
    out = add_news_features(pd.DataFrame({"date": days}), _headlines(("2026-01-05 05:00", 1.0)))
    assert out["news_weight"].iloc[9] > 0
    assert out["news_weight"].iloc[10] == 0 and out["sentiment"].iloc[10] == 0


def test_feature_frame_adds_news_inputs_only_when_asked():
    raw = make_ohlcv(120)
    assert "news_weight" not in build_feature_frame(raw)
    with_news = build_feature_frame(raw, _headlines())
    assert (with_news["news_weight"] == 0).all() and (with_news["sentiment"] == 0).all()


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

SMALL_RF = {**RF_PARAMS, "n_estimators": 5, "max_depth": 3}
SMALL_GRID = {"min_samples_leaf": (5, 20)}


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
        rf_base=SMALL_RF,
        rf_grid=SMALL_GRID,
    )
    return SimpleNamespace(dir=model_dir, meta=meta, raw=raw)


def test_every_artifact_carries_the_model_version(trained):
    root = trained.dir / "MOCK-run-v1"
    for name in ("preprocess.joblib", "random_forest.joblib", "calibrator.joblib"):
        assert joblib.load(root / name)["model_version"] == "MOCK-run-v1"
    assert (root / "lstm.pt").exists()
    assert json.loads((root / "metadata.json").read_text())["model_version"] == "MOCK-run-v1"
    assert (root / "report.md").read_text().startswith("# Model evaluation: MOCK-run-v1")
    # Training makes a candidate only; it never sets the active model (ml/promote.py)
    assert not (trained.dir / "latest.json").exists()


def test_metadata_logs_data_range_hyperparameters_metrics_and_timing(trained):
    meta = trained.meta
    assert meta["seed"] == 42 and meta["tickers"] == ["MOCKA", "MOCKB"]
    cuts = meta["data"]["cut_dates"]
    periods = meta["data"]["periods"]
    assert periods["train"]["last_date"] < cuts["val_start"] <= periods["val"]["first_date"]
    assert periods["val"]["last_date"] < cuts["test_start"] <= periods["test"]["first_date"]
    assert meta["lstm"]["hyperparameters"]["mc_dropout_passes"] == 30
    assert meta["random_forest"]["hyperparameters"]["n_estimators"] == 5
    assert meta["random_forest"]["grid"] == {"min_samples_leaf": [5, 20]}
    grid = meta["lstm"]["training"]["rf_selection"]["grid"]
    assert [g["min_samples_leaf"] for g in grid] == [5, 20]
    best = max(grid, key=lambda g: (g["val_balanced_accuracy"], g["min_samples_leaf"]))
    assert meta["random_forest"]["hyperparameters"]["min_samples_leaf"] == best["min_samples_leaf"]
    assert all("rf_params" in fold for fold in meta["walk_forward"]["folds"])
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
