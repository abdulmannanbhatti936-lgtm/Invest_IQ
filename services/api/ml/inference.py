"""
Inference from saved model artifacts (Workflow.md Step 3.7). Deterministic for a fixed
artifact: the models run in eval mode and the MC-dropout masks come from a fixed seed.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

from ml import lstm_model
from ml.confidence import MC_PASSES, MC_SEED, DirectionCalibrator, certainty
from ml.features import SIGNAL_LABELS, SIGNAL_THRESHOLD


class ModelNotFoundError(FileNotFoundError):
    pass


@dataclass
class ModelBundle:
    version: str
    lstm: lstm_model.LSTMForecaster
    scaler: object
    y_std: float
    seq_length: int
    features: list[str]
    forest: object
    calibrator: DirectionCalibrator
    metadata: dict

    def covers(self, ticker: str) -> bool:
        """Forecasts are served only for the stocks the model was trained and tested on."""
        return ticker.upper() in self.metadata["tickers"]

    def ticker_evaluation(self, ticker: str) -> dict | None:
        return self.metadata["evaluation"]["per_ticker"].get(ticker.upper())


_cache: dict[tuple[str, str], ModelBundle] = {}


def latest_version(model_dir: str | Path) -> str:
    pointer = Path(model_dir) / "latest.json"
    if not pointer.exists():
        raise ModelNotFoundError(f"No trained model in {model_dir}")
    return json.loads(pointer.read_text())["model_version"]


def _versioned(path: Path, version: str) -> object:
    """Load a joblib artifact and check it belongs to `version`."""
    payload = joblib.load(path)
    if payload.get("model_version") != version:
        raise ModelNotFoundError(f"{path} belongs to {payload.get('model_version')}, not {version}")
    return payload


def load_bundle(model_dir: str | Path, version: str | None = None) -> ModelBundle:
    version = version or latest_version(model_dir)
    key = (str(model_dir), version)
    if key in _cache:
        return _cache[key]

    path = Path(model_dir) / version
    if not (path / "metadata.json").exists():
        raise ModelNotFoundError(f"Model artifact {path} is missing")
    pre = _versioned(path / "preprocess.joblib", version)
    lstm = lstm_model.LSTMForecaster(n_features=len(pre["features"]))
    lstm.load_state_dict(torch.load(path / "lstm.pt", weights_only=True))
    lstm.eval()
    forest = _versioned(path / "random_forest.joblib", version)["model"]
    # Parallel tree averaging sums in a non-fixed order; single-threaded is bit-for-bit stable
    forest.set_params(n_jobs=1)
    bundle = ModelBundle(
        version=version,
        lstm=lstm,
        scaler=pre["scaler"],
        y_std=pre["y_std"],
        seq_length=pre["seq_length"],
        features=pre["features"],
        forest=forest,
        calibrator=_versioned(path / "calibrator.joblib", version)["model"],
        metadata=json.loads((path / "metadata.json").read_text(encoding="utf-8")),
    )
    _cache[key] = bundle
    return bundle


def predict_next_day(bundle: ModelBundle, feature_frame: pd.DataFrame) -> dict:
    """
    Next trading day's forecast from the most recent window of a `build_feature_frame`
    output (dividend-adjusted series), plus the calibrated confidence and the RF signal.
    The newest bar's dividend factor is 1, so its close is the served close.
    """
    if len(feature_frame) < bundle.seq_length:
        raise ValueError(f"Need {bundle.seq_length} feature rows, got {len(feature_frame)}")

    window = feature_frame[bundle.features].iloc[-bundle.seq_length :]
    scaled = bundle.scaler.transform(window).astype(np.float32)[np.newaxis]
    forecast_return = float(lstm_model.predict(bundle.lstm, scaled)[0] * bundle.y_std)
    spread = float(
        lstm_model.mc_dropout_std(bundle.lstm, scaled, MC_PASSES, MC_SEED)[0] * bundle.y_std
    )
    confidence = float(
        bundle.calibrator.predict(certainty(np.array([forecast_return]), np.array([spread])))[0]
    )

    last = feature_frame.iloc[-1]
    probabilities = bundle.forest.predict_proba(window.iloc[[-1]].to_numpy())[0]
    classes = [int(c) for c in bundle.forest.classes_]
    best = int(np.argmax(probabilities))

    return {
        "model_version": bundle.version,
        "as_of": pd.Timestamp(last["date"]).date(),
        "last_close": float(last["close"]),
        "forecast_price": float(last["close"]) * (1 + forecast_return),
        "forecast_return": forecast_return,
        "spread": spread,
        "confidence": confidence,
        "signal": SIGNAL_LABELS[classes[best]],
        "signal_probability": float(probabilities[best]),
        "class_probabilities": {
            SIGNAL_LABELS[c]: float(p) for c, p in zip(classes, probabilities, strict=True)
        },
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
