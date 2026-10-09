"""
Calibrated confidence for the LSTM forecast (PRD.md FR14/FR16, approved 2026-10-10).

The score answers one question: "how likely is the forecast direction (up or down) to be
right?" It is built in two steps:
1. Certainty z = |forecast return| / spread, where the spread is the standard deviation of
   the forecast over 30 Monte-Carlo dropout passes (ml/lstm_model.py). A forecast far from
   zero relative to its own wobble is a more certain one.
2. z is mapped to a probability by isotonic regression fitted on the validation period: the
   share of validation forecasts at that certainty whose direction turned out right. The
   mapping can only rise with z and is checked on the test period (reliability table,
   Brier score). A model with no real skill gets scores near 50% for every forecast.
"""

import numpy as np
from sklearn.isotonic import IsotonicRegression

MC_PASSES = 30
MC_SEED = 42
MIN_SPREAD = 1e-8  # a spread of exactly 0 would make z infinite


def certainty(forecast_return: np.ndarray, spread: np.ndarray) -> np.ndarray:
    return np.abs(forecast_return) / np.maximum(spread, MIN_SPREAD)


class DirectionCalibrator:
    """Isotonic map from certainty z to the probability that the direction is right."""

    def __init__(self) -> None:
        self.isotonic = IsotonicRegression(
            y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip"
        )

    def fit(self, z: np.ndarray, hit: np.ndarray) -> "DirectionCalibrator":
        self.isotonic.fit(np.asarray(z, dtype=float), np.asarray(hit, dtype=float))
        return self

    def predict(self, z: np.ndarray) -> np.ndarray:
        return self.isotonic.predict(np.asarray(z, dtype=float))
