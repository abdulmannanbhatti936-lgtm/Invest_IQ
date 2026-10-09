from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from ml.features import (
    FEATURE_COLUMNS,
    WARMUP_ROWS,
    add_sentiment_feature,
    add_targets,
    bollinger,
    build_feature_frame,
    macd,
    rsi,
    training_rows,
)
from ml.inference import load_bundle, models_agree, predict_next_day
from ml.lstm_model import make_sequences
from ml.splits import chronological_split
from ml.training import InsufficientDataError, train_ticker
from tests.conftest import make_ohlcv

# ---- Indicators (Workflow.md Step 3.2)


def test_rsi_extremes():
    up = pd.Series(np.arange(1, 40, dtype=float))
    down = up[::-1].reset_index(drop=True)
    assert rsi(up).iloc[-1] == pytest.approx(100.0)
    assert rsi(down).iloc[-1] == pytest.approx(0.0)
    assert rsi(up).iloc[:13].isna().all()


def test_rsi_matches_wilder_reference():
    # Classic Wilder example series; RSI(14) at row 14 ~= 70.53 (simple-average seed)
    closes = pd.Series(
        [
            44.34,
            44.09,
            44.15,
            43.61,
            44.33,
            44.83,
            45.10,
            45.42,
            45.84,
            46.08,
            45.89,
            46.03,
            45.61,
            46.28,
            46.28,
            46.00,
            46.03,
            46.41,
            46.22,
            45.64,
        ]
    )
    value = rsi(closes).iloc[-1]
    assert 40 < value < 80


def test_macd_and_bollinger_on_constant_series():
    flat = pd.Series([50.0] * 60)
    line, signal, hist = macd(flat)
    assert line.dropna().abs().max() == pytest.approx(0.0)
    assert hist.dropna().abs().max() == pytest.approx(0.0)
    upper, mid, lower = bollinger(flat)
    assert upper.iloc[-1] == mid.iloc[-1] == lower.iloc[-1] == 50.0


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


# ---- Split utility (Workflow.md Step 3.3)


def test_chronological_split_never_leaks_future_dates():
    df = make_ohlcv(300).sample(frac=1, random_state=1)  # deliberately shuffled input
    split = chronological_split(df)
    assert len(split.train) == 210 and len(split.val) == 45 and len(split.test) == 45
    assert split.train["date"].max() < split.val["date"].min()
    assert split.val["date"].max() < split.test["date"].min()


def test_chronological_split_rejects_bad_fractions():
    with pytest.raises(ValueError):
        chronological_split(make_ohlcv(100), train_frac=0.9, val_frac=0.2)


def test_sequences_only_look_backwards():
    data = np.arange(10, dtype=float).reshape(-1, 1)
    seqs = make_sequences(data, seq_length=3, end_indices=np.array([2, 9]))
    assert seqs[0].ravel().tolist() == [0, 1, 2]
    assert seqs[1].ravel().tolist() == [7, 8, 9]


# ---- Training + inference against a frozen synthetic artifact (Step 3.9)


def test_training_writes_versioned_artifacts(trained_model_dir):
    root = Path(trained_model_dir.path) / "SYNTH"
    assert (root / "latest.json").exists()
    for name in (
        "lstm.pt",
        "preprocess.joblib",
        "random_forest.joblib",
        "svm.joblib",
        "metadata.json",
    ):
        assert (root / "test-v1" / name).exists()
    meta = trained_model_dir.metadata
    assert meta["model_version"] == "test-v1"
    for key in ("rmse_pct_of_price", "directional_accuracy", "baseline_naive_rmse_pct_of_price"):
        assert key in meta["lstm"]["test_metrics"]
    assert 0 <= meta["random_forest"]["test_metrics"]["accuracy"] <= 1
    assert meta["data"]["train_end_date"] < meta["data"]["val_end_date"] < meta["data"]["date_end"]


def test_training_refuses_short_history(tmp_path):
    with pytest.raises(InsufficientDataError):
        train_ticker("TINY", make_ohlcv(200), tmp_path, lstm_epochs=1)


def test_inference_is_valid_and_deterministic(trained_model_dir):
    bundle = load_bundle(trained_model_dir.path, "SYNTH")
    frame = build_feature_frame(make_ohlcv(700))
    first = predict_next_day(bundle, frame)
    second = predict_next_day(bundle, frame)
    assert first == second
    assert first["signal"] in {"BUY", "SELL", "HOLD"}
    assert 0 <= first["confidence"] <= 1
    assert sum(first["class_probabilities"].values()) == pytest.approx(1.0)
    assert first["forecast_price"] > 0
    assert first["last_close"] == pytest.approx(frame["close"].iloc[-1])


def test_models_agree():
    assert models_agree("BUY", 0.004)
    assert not models_agree("BUY", -0.004)
    assert models_agree("SELL", -0.02)
    assert models_agree("HOLD", 0.005)
    assert not models_agree("HOLD", 0.03)
