"""
Rebuild the frozen MOCK model the tests load (Workflow.md Step 3.9: tests never retrain the
real model). It uses the real pipeline and architecture on MOCK synthetic prices, so it is
only good for checking shapes, determinism and API behaviour, never for results.

    python -m tests.fixtures.build_model_fixture
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ml.promote import set_active
from ml.training import RF_PARAMS, train_and_save
from tests.synthetic import make_ohlcv

FIXTURE_DIR = Path(__file__).resolve().parent / "model"
FIXTURE_VERSION = "MOCK-fixture-v1"
# Reads the news inputs too; MOCK-fixture-v1 is its price-only fallback (PRD.md FR22)
NEWS_FIXTURE_VERSION = "MOCK-fixture-news-v1"
MOCK_TICKERS = ["MOCKA", "MOCKB", "MOCKC"]


def mock_prices() -> dict:
    return {
        ticker: make_ohlcv(700, seed=seed).assign(dividend_factor=1.0)
        for seed, ticker in enumerate(MOCK_TICKERS, start=1)
    }


def mock_headlines(prices: dict) -> dict:
    """MOCK scored headlines on every fifth trading day, random scores."""
    rng = np.random.default_rng(11)
    out = {}
    for ticker, frame in prices.items():
        days = frame["date"].iloc[::5]
        out[ticker] = pd.DataFrame(
            {
                "published_at": (days + pd.Timedelta(hours=5)).dt.tz_localize("UTC"),
                "score": rng.uniform(-1, 1, len(days)),
            }
        )
    return out


def main() -> None:
    small = {
        "run_walk_forward": False,
        "lstm_epochs": 2,
        "rf_base": {**RF_PARAMS, "n_estimators": 10, "max_depth": 4},
        "rf_grid": {"min_samples_leaf": (5, 20)},
    }
    prices = mock_prices()
    train_and_save(
        prices,
        {"version": "MOCK synthetic random walk (tests/synthetic.py)", "sha256": {}},
        FIXTURE_DIR,
        version=FIXTURE_VERSION,
        **small,
    )
    train_and_save(
        prices,
        {"version": "MOCK synthetic random walk (tests/synthetic.py)", "sha256": {}},
        FIXTURE_DIR,
        version=NEWS_FIXTURE_VERSION,
        headlines=mock_headlines(prices),
        news={"version": "MOCK synthetic headlines", "sources": ["profit", "mettis"]},
        fallback_model_version=FIXTURE_VERSION,
        **small,
    )
    # Test-only shortcut: this MOCK model has no walk-forward report, so it could never pass
    # ml.promote; the tests point their own fixture folder at it directly
    set_active(FIXTURE_DIR, FIXTURE_VERSION)
    print(f"Wrote {FIXTURE_DIR / FIXTURE_VERSION}")


if __name__ == "__main__":
    main()
