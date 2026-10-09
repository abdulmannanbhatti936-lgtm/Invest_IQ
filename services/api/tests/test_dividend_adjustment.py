import datetime

import pytest

from integrations.market_data import MarketDataClient, MarketDataUnavailable
from models.stock import StockDividend
from services.dividend_adjustment import (
    MISMATCH_FLAG,
    NO_BAR_FLAG,
    Dividend,
    assess,
    cumulative_factors,
)
from tests.test_stocks import bar, store
from worker.tasks import refresh_dividends

D = datetime.date
DATES = [D(2026, 3, 2), D(2026, 3, 3), D(2026, 3, 5), D(2026, 3, 6)]


def test_plausible_dividend_gets_the_backward_factor():
    # Rs.10 dividend, close falls 200 -> 191 on the ex-date (drop 9, within 0.5x-2x)
    [decision] = assess(DATES, [198.0, 200.0, 191.0, 192.0], [Dividend(D(2026, 3, 5), 10.0)])
    assert decision.flag is None
    assert decision.previous_close == 200.0 and decision.ex_close == 191.0
    assert decision.factor == pytest.approx(1 - 10 / 200)
    assert decision.yield_pct == pytest.approx(5.0)


def test_ex_date_without_a_bar_uses_the_next_bar():
    # 2026-03-04 has no bar: the previous close is 03-03, the ex-date bar is 03-05
    [decision] = assess(DATES, [198.0, 200.0, 191.0, 192.0], [Dividend(D(2026, 3, 4), 10.0)])
    assert decision.previous_close == 200.0 and decision.ex_close == 191.0
    assert decision.factor is not None


@pytest.mark.parametrize(
    "ex_close",
    [
        210.0,  # price rose: no drop at all
        196.0,  # drop 4 < half of 10
        170.0,  # drop 30 > twice 10
    ],
)
def test_drop_far_from_the_dividend_is_held_back(ex_close):
    [decision] = assess(DATES, [198.0, 200.0, ex_close, 192.0], [Dividend(D(2026, 3, 5), 10.0)])
    assert decision.flag == MISMATCH_FLAG
    assert decision.factor is None


@pytest.mark.parametrize("day", [D(2026, 3, 1), D(2026, 3, 9)])
def test_dividend_outside_the_history_is_flagged(day):
    [decision] = assess(DATES, [198.0, 200.0, 191.0, 192.0], [Dividend(day, 10.0)])
    assert decision.flag == NO_BAR_FLAG and decision.factor is None


def test_cumulative_factors_apply_only_to_earlier_bars():
    factors = cumulative_factors(DATES, [(D(2026, 3, 3), 0.9), (D(2026, 3, 6), 0.5)])
    # bar 03-02 is before both ex-dates; 03-03 and 03-05 only before 03-06; the newest is 1
    assert factors == pytest.approx([0.45, 0.5, 0.5, 1.0])


def test_adjusted_series_has_no_ex_date_loss():
    closes = [198.0, 200.0, 191.0, 192.0]
    [decision] = assess(DATES, closes, [Dividend(D(2026, 3, 5), 10.0)])
    factors = cumulative_factors(DATES, [(decision.day, decision.factor)])
    adjusted = [c * f for c, f in zip(closes, factors, strict=True)]
    # Backward multiplicative convention (Yahoo/CRSP): the ex-date return is measured from the
    # previous close minus the dividend, 191 / (200 - 10) - 1 = +0.53%, instead of -4.5% raw
    assert adjusted[2] / adjusted[1] - 1 == pytest.approx(191 / (200 - 10) - 1)
    assert closes[2] / closes[1] - 1 == pytest.approx(-0.045)
    assert adjusted[-1] == closes[-1]


def test_refresh_dividends_stores_decisions(db, fake_redis, monkeypatch):
    stock = store(
        db,
        "HUBC",
        [bar(D(2022, 10, 7), 79.03), bar(D(2022, 10, 11), 64.18), bar(D(2022, 10, 12), 63.70)],
    )

    def dividends(ticker):
        if ticker == "SYS":
            raise MarketDataUnavailable("timeout")
        return [(D(2022, 10, 11), 15.5), (D(2023, 1, 2), 1.0)]

    monkeypatch.setattr(MarketDataClient, "get_dividends", staticmethod(dividends))
    result = refresh_dividends.run(tickers=["HUBC", "SYS"])
    assert result["assessed"] == 1 and result["failed"] == ["SYS"]

    db.expire_all()
    rows = (
        db.query(StockDividend)
        .filter(StockDividend.stock_id == stock.id)
        .order_by(StockDividend.ex_date)
        .all()
    )
    assert [r.ex_date for r in rows] == [D(2022, 10, 11), D(2023, 1, 2)]
    # The real HUBC 2022 case: Rs.15.5 dividend, close fell Rs.14.85
    assert float(rows[0].adjustment_factor) == pytest.approx(1 - 15.5 / 79.03)
    assert rows[0].review_flag is None and rows[0].method_version == "div-v1"
    assert rows[1].review_flag == NO_BAR_FLAG and rows[1].adjustment_factor is None

    # A re-fetch with a corrected amount updates the row instead of duplicating it
    monkeypatch.setattr(
        MarketDataClient, "get_dividends", staticmethod(lambda t: [(D(2022, 10, 11), 15.0)])
    )
    refresh_dividends.run(tickers=["HUBC"])
    db.expire_all()
    assert db.query(StockDividend).filter(StockDividend.stock_id == stock.id).count() == 2
