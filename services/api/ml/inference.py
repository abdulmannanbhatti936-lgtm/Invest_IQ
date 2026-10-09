"""
Inference from saved model artifacts (Workflow.md Step 3.7).
Deterministic for a fixed artifact: models are always in eval mode.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

from ml import lstm_model
from ml.features import SIGNAL_LABELS, SIGNAL_THRESHOLD


class ModelNotFoundError(FileNotFoundError):
    pass


@dataclass
class ModelBundle:
    ticker: str
    version: str
    lstm: lstm_model.LSTMForecaster
    scaler: object
    y_std: float
    seq_length: int
    features: list[str]
    classifier: object
    metadata: dict


_cache: dict[tuple[str, str], ModelBundle] = {}


def latest_version(model_dir: str | Path, ticker: str) -> str:
    pointer = Path(model_dir) / ticker.upper() / "latest.json"
    if not pointer.exists():
        raise ModelNotFoundError(f"No trained model for {ticker.upper()}")
    return json.loads(pointer.read_text())["model_version"]


def load_bundle(model_dir: str | Path, ticker: str, version: str | None = None) -> ModelBundle:
    ticker = ticker.upper()
    version = version or latest_version(model_dir, ticker)
    key = (str(model_dir), ticker + "/" + version)
    if key in _cache:
        return _cache[key]

    path = Path(model_dir) / ticker / version
    if not path.exists():
        raise ModelNotFoundError(f"Model artifact {path} is missing")
    pre = joblib.load(path / "preprocess.joblib")
    lstm = lstm_model.LSTMForecaster(n_features=len(pre["features"]))
    lstm.load_state_dict(torch.load(path / "lstm.pt", weights_only=True))
    lstm.eval()
    classifier = joblib.load(path / "random_forest.joblib")
    # Parallel tree averaging sums in a non-fixed order; single-threaded is bit-for-bit stable
    classifier.set_params(n_jobs=1)
    bundle = ModelBundle(
        ticker=ticker,
        version=version,
        lstm=lstm,
        scaler=pre["scaler"],
        y_std=pre["y_std"],
        seq_length=pre["seq_length"],
        features=pre["features"],
        classifier=classifier,
        metadata=json.loads((path / "metadata.json").read_text()),
    )
    _cache[key] = bundle
    return bundle


def predict_next_day(bundle: ModelBundle, feature_frame: pd.DataFrame) -> dict:
    """
    Forecast the next trading day's close from the most recent window of a
    `build_feature_frame` output, plus the RF buy/sell/hold signal.
    """
    if len(feature_frame) < bundle.seq_length:
        raise ValueError(f"Need {bundle.seq_length} feature rows, got {len(feature_frame)}")

    window = feature_frame[bundle.features].iloc[-bundle.seq_length :]
    scaled = bundle.scaler.transform(window).astype(np.float32)
    pred_return = float(lstm_model.predict(bundle.lstm, scaled[np.newaxis])[0] * bundle.y_std)

    last = feature_frame.iloc[-1]
    last_close = float(last["close"])
    forecast_price = last_close * (1 + pred_return)

    probabilities = bundle.classifier.predict_proba(window.iloc[[-1]].to_numpy())[0]
    classes = [int(c) for c in bundle.classifier.classes_]
    best = int(np.argmax(probabilities))
    signal = SIGNAL_LABELS[classes[best]]

    return {
        "model_version": bundle.version,
        "as_of": pd.Timestamp(last["date"]).date().isoformat(),
        "last_close": last_close,
        "forecast_price": forecast_price,
        "forecast_return": pred_return,
        "signal": signal,
        "confidence": float(probabilities[best]),
        "class_probabilities": {
            SIGNAL_LABELS[c]: float(p) for c, p in zip(classes, probabilities, strict=True)
        },
        "lstm_direction": lstm_direction(pred_return),
        "models_agree": models_agree(signal, pred_return),
    }


def lstm_direction(forecast_return: float) -> str:
    if forecast_return > SIGNAL_THRESHOLD:
        return "BUY"
    if forecast_return < -SIGNAL_THRESHOLD:
        return "SELL"
    return "HOLD"


def models_agree(signal: str, forecast_return: float) -> bool:
    """Whether the classifier signal and the LSTM forecast point the same way."""
    if signal == "BUY":
        return forecast_return > 0
    if signal == "SELL":
        return forecast_return < 0
    return lstm_direction(forecast_return) == "HOLD"
