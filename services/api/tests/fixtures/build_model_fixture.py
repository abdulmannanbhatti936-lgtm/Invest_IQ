"""
Rebuild the frozen MOCK model the tests load (Workflow.md Step 3.9: tests never retrain the
real model). It uses the real pipeline and architecture on MOCK synthetic prices, so it is
only good for checking shapes, determinism and API behaviour, never for results.

    python -m tests.fixtures.build_model_fixture
"""

from pathlib import Path

from ml.training import RF_PARAMS, train_and_save
from tests.synthetic import make_ohlcv

FIXTURE_DIR = Path(__file__).resolve().parent / "model"
FIXTURE_VERSION = "MOCK-fixture-v1"
MOCK_TICKERS = ["MOCKA", "MOCKB", "MOCKC"]


def mock_prices() -> dict:
    return {
        ticker: make_ohlcv(700, seed=seed).assign(dividend_factor=1.0)
        for seed, ticker in enumerate(MOCK_TICKERS, start=1)
    }


def main() -> None:
    train_and_save(
        mock_prices(),
        {"version": "MOCK synthetic random walk (tests/synthetic.py)", "sha256": {}},
        FIXTURE_DIR,
        version=FIXTURE_VERSION,
        run_walk_forward=False,
        lstm_epochs=2,
        rf_params={**RF_PARAMS, "n_estimators": 10, "max_depth": 4},
    )
    print(f"Wrote {FIXTURE_DIR / FIXTURE_VERSION}")


if __name__ == "__main__":
    main()
