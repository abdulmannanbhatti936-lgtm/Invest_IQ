"""
Step 6.3: the backtest engine and metrics against the hand-worked fixture (Phase 6 proposal,
section F; re-run independently by the team). MOCK_A and MOCK_B are invented prices, never PSX
data. Rs 100,000 split 60/40, filer, PSX floor commission, rates psx-costs-2026-10-11.2, one
point on the 1st of each month from Jan 2025 to Jan 2026, a constant 12% risk-free rate, and a
Rs 5 MOCK_A dividend with ex-date 1 Jul 2025. Every figure below was calculated by hand.
"""

import datetime
from decimal import Decimal as D

import pandas as pd
import pytest
import quantstats as qs

from core.portfolio_rules import RISK_RULES, VOLATILITY_WINDOW
from services import backtest, backtest_metrics, cost_engine
from services.backtest import (
    Bar,
    History,
    InsufficientHistory,
    Period,
    UnsupportedSplit,
    WeightTooSmall,
)
from services.cost_engine import FilerStatus
from services.portfolio_service import Close, volatility

RATES = cost_engine.load_rates()
FLOOR = RATES.commission_rate
CAPITAL = D("100000.00")
DATES = [datetime.date(2025, m, 1) for m in range(1, 13)] + [datetime.date(2026, 1, 1)]
PRICES = {
    "MOCK_A": "100 104 101 108 112 109 115 118 113 120 125 122 130",
    "MOCK_B": "50 51 53 52 49 50 54 55 57 56 58 60 59",
}
DIVIDENDS = {"MOCK_A": [(datetime.date(2025, 7, 1), D("5"))], "MOCK_B": []}

# Hand calculation: month-end values after buying (V0 = capital), returns and risk-free
VALUES = """103009.18 102811.18 106199.18 106197.18 105201.18 114522.68 117114.68
            115720.68 119108.68 123694.68 123496.68 127482.68"""
RETURNS = """0.030092 -0.001922 0.032954 -0.000019 -0.009379 0.088606 0.022633
             -0.011903 0.029277 0.038503 -0.001601 0.032276"""
RISK_FREE = """0.010192 0.009205 0.010192 0.009863 0.010192 0.009863 0.010192
               0.010192 0.009863 0.010192 0.009863 0.010192"""


class ConstantRate:
    """12% a year, simple interest on a 365-day year, as the SBP series accrues."""

    def interval_return(self, previous, current):
        return D("0.12") * (current - previous).days / 365


def _histories() -> dict[str, History]:
    return {
        ticker: History(
            ticker,
            [Bar(d, D(p), D(1)) for d, p in zip(DATES, prices.split(), strict=True)],
            DIVIDENDS[ticker],
        )
        for ticker, prices in PRICES.items()
    }


def _run():
    histories = _histories()
    period = Period(DATES[0], DATES[-1], DATES)
    bars = backtest.start_bars(list(histories.values()), period, DATES)
    weights = {"MOCK_A": D("0.60"), "MOCK_B": D("0.40")}
    purchases = backtest.purchases_from_weights(weights, CAPITAL, bars, RATES, FLOOR)
    return backtest.simulate(
        purchases, bars, histories, CAPITAL, period, FilerStatus.filer, RATES, FLOOR
    )


def q6(value: D) -> D:
    return value.quantize(D("0.000001"))


def test_purchases_match_the_hand_calculation():
    sim = _run()
    a, b = sim.holdings
    assert (a.purchase.shares, a.purchase.gross, a.purchase.charges.total) == (
        598,
        D("59800.00"),
        D("108.45"),
    )
    assert (a.purchase.charges.commission, a.purchase.charges.sales_tax) == (D("89.70"), D("13.46"))
    assert dict(a.purchase.charges.fees) == {
        "cdc_fee": D("2.15"),
        "psx_trading_fee": D("2.09"),
        "psx_regulatory_fee": D("0.00"),
        "secp_levy": D("0.39"),
        "nccpl_trade_fee": D("0.48"),
        "nccpl_secp_fee": D("0.18"),
    }
    assert a.purchase.total_cost == D("59908.45")
    assert (b.purchase.shares, b.purchase.charges.total, b.purchase.total_cost) == (
        798,
        D("72.37"),
        D("39972.37"),
    )
    assert sim.idle_cash == D("119.18")


def test_dividend_is_credited_on_the_ex_date_net_of_wht():
    a = _run().holdings[0]
    (ex_date, income), = a.dividends  # fmt: skip
    assert ex_date == datetime.date(2025, 7, 1)
    assert (income.gross, income.wht, income.net) == (D("2990.00"), D("448.50"), D("2541.50"))


def test_monthly_values_match_the_hand_calculation():
    sim = _run()
    assert sim.values == [CAPITAL] + [D(v) for v in VALUES.split()]
    assert [q6(r) for r in backtest_metrics.period_returns(sim.values)] == [
        D(r) for r in RETURNS.split()
    ]
    rf = ConstantRate()
    assert [q6(rf.interval_return(p, c)) for p, c in zip(DATES, DATES[1:], strict=False)] == [
        D(r) for r in RISK_FREE.split()
    ]


def test_sale_charges_cgt_and_net_end_value_match_the_hand_calculation():
    sim = _run()
    a, b = sim.holdings
    assert (a.sale.gross, a.sale.charges.total, a.sale.gain, a.sale.cgt, a.sale.net_proceeds) == (
        D("77740.00"),
        D("140.99"),
        D("17690.56"),
        D("2653.58"),
        D("74945.43"),
    )
    assert (b.sale.gross, b.sale.charges.total, b.sale.gain, b.sale.cgt, b.sale.net_proceeds) == (
        D("47082.00"),
        D("85.38"),
        D("7024.25"),
        D("1053.64"),
        D("45942.98"),
    )
    assert sim.end_value_net == D("123549.09")
    assert (sim.buy_charges, sim.sell_charges, sim.cgt) == (D("180.82"), D("226.37"), D("3707.22"))


def test_metrics_match_the_hand_calculation():
    sim = _run()
    m = backtest_metrics.compute(sim.dates, sim.values, ConstantRate(), sim.end_value_net)
    assert q6(m.total_return) == D("0.235491")
    assert q6(m.total_return_before_sale) == D("0.274827")
    # 365 calendar days: (1.235491)^(365.25/365) - 1
    assert q6(m.annualised_return) == D("0.235670")
    # mean excess 0.010793 / sd 0.028223 x sqrt(12 / (365 / 365.25))
    assert m.sharpe_ratio.quantize(D("0.0001")) == D("1.3252")
    assert q6(m.max_drawdown.depth) == D("-0.011903")
    assert (m.max_drawdown.peak_date, m.max_drawdown.trough_date) == (
        datetime.date(2025, 8, 1),
        datetime.date(2025, 9, 1),
    )
    assert (m.months_won, m.months_total) == (7, 12)
    assert m.win_rate.quantize(D("0.0001")) == D("0.5833")


def test_quantstats_agrees_on_sharpe_drawdown_and_win_rate():
    """Independent cross-check (test-only dependency). Our risk-free series is subtracted first."""
    sim = _run()
    index = pd.to_datetime(sim.dates)
    values = pd.Series([float(v) for v in sim.values], index=index)
    rf = ConstantRate()
    excess = pd.Series(
        [
            float(r - rf.interval_return(p, c))
            for r, p, c in zip(
                backtest_metrics.period_returns(sim.values), DATES, DATES[1:], strict=False
            )
        ],
        index=index[1:],
    )
    ours = backtest_metrics.compute(sim.dates, sim.values, rf, sim.end_value_net)
    periods = float(backtest_metrics.periods_per_year(sim.dates))

    assert qs.stats.sharpe(excess, rf=0.0, periods=periods) == pytest.approx(
        float(ours.sharpe_ratio), abs=1e-9
    )
    assert qs.stats.max_drawdown(values) == pytest.approx(float(ours.max_drawdown.depth), abs=1e-9)
    returns = values.pct_change().dropna()
    assert qs.stats.win_rate(returns, prepare_returns=False) == pytest.approx(
        float(ours.win_rate), abs=1e-9
    )


def test_a_split_keeps_the_value_continuous_and_sells_the_new_share_count():
    days = DATES[:3]
    # 2-for-1 after the first bar: the stored first close is 200, served 100 (factor 2)
    history = History(
        "MOCK_S", [Bar(days[0], D("200"), D(2)), Bar(days[1], D("101"), D(1)),
                   Bar(days[2], D("102"), D(1))], [(days[2], D("1"))])  # fmt: skip
    period = Period(days[0], days[-1], days)
    bars = backtest.start_bars([history], period, days)
    purchase = cost_engine.buy(10, D("200"), RATES, FLOOR)
    sim = backtest.simulate(
        {"MOCK_S": purchase}, bars, {"MOCK_S": history}, purchase.total_cost, period,
        FilerStatus.filer, RATES, FLOOR,
    )  # fmt: skip
    (holding,) = sim.holdings
    # 10 shares bought at Rs 200 are 20 of today's shares
    assert holding.units == 20
    assert sim.values[1] == D("2020.00")
    assert holding.dividends[0][1].gross == D("20.00")
    assert (holding.sale.shares, holding.sale.price) == (20, D("102"))


def test_a_reverse_split_leaving_half_a_share_is_refused():
    days = DATES[:2]
    history = History("MOCK_R", [Bar(days[0], D("10"), D("0.5")), Bar(days[1], D("20"), D(1))], [])
    period = Period(days[0], days[-1], days)
    bars = backtest.start_bars([history], period, days)
    purchase = cost_engine.buy(3, D("10"), RATES, FLOOR)
    with pytest.raises(UnsupportedSplit):
        backtest.simulate(
            {"MOCK_R": purchase}, bars, {"MOCK_R": history}, D("1000"), period,
            FilerStatus.filer, RATES, FLOOR,
        )  # fmt: skip


def test_a_stock_without_a_close_near_the_start_is_reported_with_its_first_date():
    histories = _histories()
    late = History("MOCK_L", [Bar(d, D("10"), D(1)) for d in DATES[6:]], [])
    period = Period(DATES[0], DATES[-1], DATES)
    with pytest.raises(InsufficientHistory) as exc:
        backtest.start_bars([*histories.values(), late], period, DATES)
    assert exc.value.first_dates == {"MOCK_L": datetime.date(2025, 7, 1)}


def test_a_close_up_to_five_trading_days_before_the_start_is_used_and_no_older():
    days = [datetime.date(2025, 1, d) for d in (1, 2, 3, 6, 7, 8, 9)]
    stale = History("MOCK_G", [Bar(days[0], D("10"), D(1))], [])
    assert backtest.start_bars([stale], Period(days[5], days[6], days[5:]), days)
    with pytest.raises(InsufficientHistory):
        backtest.start_bars([stale], Period(days[6], days[6], days[6:]), days)


def test_a_weight_too_small_for_one_share_is_refused():
    histories = _histories()
    period = Period(DATES[0], DATES[-1], DATES)
    bars = backtest.start_bars(list(histories.values()), period, DATES)
    with pytest.raises(WeightTooSmall) as exc:
        backtest.purchases_from_weights(
            {"MOCK_A": D("0.9996"), "MOCK_B": D("0.0004")}, CAPITAL, bars, RATES, FLOOR
        )
    assert exc.value.tickers == ["MOCK_B"]


def test_period_is_whole_years_back_to_the_next_trading_day():
    days = [datetime.date(2023, 10, d) for d in (6, 9, 10)] + [datetime.date(2026, 10, 9)]
    period = backtest.period_for(3, datetime.date(2026, 10, 9), days)
    # 9 Oct 2023 is a Monday, the first trading day on or after 9 Oct 2023
    assert (period.start, period.end, len(period.calendar)) == (days[1], days[-1], 3)
    leap = backtest.period_for(1, datetime.date(2024, 2, 29), [datetime.date(2023, 2, 28)])
    assert leap.start == datetime.date(2023, 2, 28)


def test_equal_weight_benchmark_by_hand():
    histories = list(_histories().values())
    period = Period(DATES[0], DATES[-1], DATES)
    bars = backtest.start_bars(histories, period, DATES)
    run = backtest.equal_weight_benchmark(histories, bars, period)
    # Half in each at the start: A 100 -> 130 (+30%) plus Rs 5 dividend (5%), B 50 -> 59 (+18%)
    assert run.values[-1] == D("0.5") * (D("1.30") + D("0.05")) + D("0.5") * D("1.18")
    assert run.tickers == ["MOCK_A", "MOCK_B"]


def test_index_benchmark_rebases_to_the_start_and_needs_the_whole_period():
    period = Period(DATES[0], DATES[2], DATES[:3])
    closes = {DATES[0]: D("1000"), DATES[1]: D("1100"), DATES[2]: D("1210")}
    assert backtest.index_benchmark(closes, period).values == [D(1), D("1.1"), D("1.21")]
    assert backtest.index_benchmark({DATES[0]: D("1000"), DATES[1]: D("1")}, period) is None


def test_start_date_rules_use_only_closes_up_to_the_start_and_no_tilt():
    days = [datetime.date(2022, 1, 1) + datetime.timedelta(days=i) for i in range(400)]
    start = days[300]

    def history(ticker, step, after=None):
        prices = [D(100) + D(step) * (i % 2) for i in range(len(days))]
        if after is not None:
            prices[301:] = [D(after)] * 99
        return History(ticker, [Bar(d, p, D(1)) for d, p in zip(days, prices, strict=True)], [])

    def plan(histories):
        period = Period(start, days[-1], days[300:])
        bars = backtest.start_bars(list(histories.values()), period, days)
        return backtest.purchases_from_rules(
            histories, {t: f"S{t}" for t in histories}, CAPITAL, bars,
            RISK_RULES["conservative"], RATES, FLOOR, VOLATILITY_WINDOW,
            lambda b: volatility([Close(x.day, x.served) for x in b]),
        )  # fmt: skip

    tickers = [f"MOCK_{i}" for i in range(8)]
    calm = {t: history(t, 1 + i) for i, t in enumerate(tickers)}
    # Wild prices after the start date must not change the start-date plan
    wild = {t: history(t, 1 + i, after=1000 + i) for i, t in enumerate(tickers)}
    assert {t: p.shares for t, p in plan(calm).items()} == {
        t: p.shares for t, p in plan(wild).items()
    }
    shares = {t: p.shares for t, p in plan(calm).items()}
    # Conservative weights by 1/sigma^2: the calmest stock gets the most
    assert shares["MOCK_0"] > shares["MOCK_6"]


def test_a_period_is_never_shortened_to_fit_the_data():
    # Data from 1 Jan 2025 only; three years back from 1 Jan 2026 is 1 Jan 2023
    histories = list(_histories().values())
    period = backtest.period_for(3, DATES[-1], DATES)
    assert period.start == DATES[0] and period.requested_start == datetime.date(2023, 1, 1)
    with pytest.raises(InsufficientHistory) as exc:
        backtest.start_bars(histories, period, DATES)
    assert exc.value.required_start == datetime.date(2023, 1, 1)
    assert set(exc.value.first_dates) == {"MOCK_A", "MOCK_B"}
