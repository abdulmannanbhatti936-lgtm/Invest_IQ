"""Which stocks a portfolio may hold, read from the database with the frozen MOCK model."""

import datetime
from decimal import Decimal as D

import pytest

from models.prediction import Prediction
from services.portfolio_service import (
    Close,
    PredictionsUnavailable,
    load_universe,
    recent_closes,
    volatility,
)
from tests.fixtures.build_model_fixture import FIXTURE_VERSION
from tests.test_predictions import mock_model, mock_stock, store_history  # noqa: F401


def _predict(db, stock, as_of: datetime.date, forecast="101.00", close="100.00"):
    db.add(
        Prediction(
            stock_id=stock.id,
            model_version=FIXTURE_VERSION,
            forecast_price=D(forecast),
            last_close=D(close),
            confidence_score=D("0.55"),
            signal="BUY",
            signal_probability=D("0.40"),
            as_of_date=as_of,
        )
    )
    db.commit()


@pytest.fixture
def stocks(db, mock_model):  # noqa: F811
    result = {}
    for seed, ticker in enumerate(["MOCKA", "MOCKB", "MOCKC"], start=1):
        stock = mock_stock(db, ticker)
        history = store_history(db, stock, days=400, seed=seed)
        result[ticker] = (stock, history[-1]["timestamp"].date())
    return result


def test_only_current_forecasts_are_eligible(db, stocks):
    for ticker in ("MOCKA", "MOCKB"):
        stock, last_day = stocks[ticker]
        _predict(db, stock, last_day)
    stock, last_day = stocks["MOCKC"]
    _predict(db, stock, last_day - datetime.timedelta(days=3))

    universe = load_universe(db, shariah_only=False, excluded=["MOCKB"])
    assert list(universe.eligible) == ["MOCKA"]
    assert universe.skipped == {"MOCKB": "excluded", "MOCKC": "forecast_not_current"}
    assert universe.prices_as_of == stocks["MOCKA"][1]

    candidate = universe.eligible["MOCKA"].candidate
    assert candidate.expected_return == D("0.01")
    assert candidate.sentiment_score is None
    assert candidate.volatility == volatility(recent_closes(db, stocks["MOCKA"][0], 251))


def test_shariah_filter_drops_stocks_outside_the_psx_review(db, stocks):
    stock, last_day = stocks["MOCKA"]
    _predict(db, stock, last_day)
    universe = load_universe(db, shariah_only=True, excluded=[])
    assert universe.eligible == {}
    assert universe.skipped["MOCKA"] == "not_shariah_compliant"


def test_no_current_forecasts_is_reported(db, stocks):
    with pytest.raises(PredictionsUnavailable):
        load_universe(db, shariah_only=False, excluded=[])


def test_volatility_is_the_sample_deviation_of_log_returns():
    closes = [
        Close(datetime.date(2026, 1, d), D(c)) for d, c in [(3, "110"), (2, "100"), (1, "100")]
    ]
    # log returns ln(1.1) = 0.09531018 and 0; sample sd = 0.09531018 / sqrt(2) = 0.06739446
    assert volatility(closes) == D("0.067394")
