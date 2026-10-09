"""
MOCK synthetic price data for tests. Never used for training a served model or in a demo
(CLAUDE.md: mock data is labelled and never reaches a demo).
"""

import numpy as np
import pandas as pd


def make_ohlcv(days: int = 700, seed: int = 7, start_price: float = 100.0) -> pd.DataFrame:
    """Deterministic synthetic daily OHLCV (geometric random walk)."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0004, 0.015, days)
    close = start_price * np.cumprod(1 + returns)
    open_ = close * (1 + rng.normal(0, 0.003, days))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.005, days)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.005, days)))
    dates = pd.bdate_range("2022-01-03", periods=days)
    return pd.DataFrame(
        {
            "date": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.integers(100_000, 1_000_000, days),
        }
    )
