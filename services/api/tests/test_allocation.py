"""
Steps 5.3-5.5: allocation against the hand-worked example (DetailedReport.md Phase 5): the
dev DB's real inputs as of the 7 Oct 2026 close for the 18 forecast stocks, Rs 100,000,
Moderate. The shares and rupee figures must equal tests/test_cost_engine.py's fixtures.
"""

import random
from decimal import Decimal as D

import pytest

from core.portfolio_rules import RISK_RULES
from services.allocation import (
    Candidate,
    CapitalTooLow,
    TooFewEligibleStocks,
    allocate,
    cap_weights,
    minimum_capital,
)
from services.cost_engine import load_rates
from tests.test_cost_engine import WORKED_EXAMPLE

RATES = load_rates()
# ticker, sector, price, 250-day volatility, forecast, close it was made from, RF signal,
# RF probability, sentiment score (None: no counted headline)
INPUTS = """
MARI  OIL     642.42  0.017286  643.0368  642.4200  HOLD 0.4778  0.1445
EFERT FERT    193.00  0.018011  193.0976  193.0000  HOLD 0.5073  -
OGDC  OIL     315.91  0.020614  316.1220  315.9100  HOLD 0.6061  0.4193
FFC   FERT    539.51  0.021057  539.9405  539.5100  HOLD 0.6340  0.9266
HUBC  POWER   200.49  0.021965  200.5932  200.4900  HOLD 0.4846  -
MEBL  BANKS   550.10  0.022081  550.1543  550.1000  HOLD 0.5549  -
PSO   OMC     355.86  0.022268  357.1308  355.8600  BUY  0.3678  -0.5948
HBL   BANKS   302.02  0.023443  302.1723  302.0200  HOLD 0.4963  -
SYS   TECH    117.96  0.023996  118.3374  117.9600  BUY  0.3582  -
PPL   OIL     220.29  0.025069  220.2842  220.2900  HOLD 0.3920  -
LUCK  CEMENT  408.24  0.025419  407.8794  408.2400  HOLD 0.4760  0.2422
ATRL  REFINE 1218.69  0.025865 1224.1712 1218.6899  BUY  0.3621  0.0000
SAZEW AUTO   1626.80  0.026135 1626.1368 1626.8000  HOLD 0.3748  0.3772
UBL   BANKS   424.23  0.026382  425.3039  424.2300  HOLD 0.4951  -
DGKC  CEMENT  186.25  0.028972  186.3674  186.2500  SELL 0.3495  0.8493
PAEL  CABLE    34.06  0.029974   34.1782   34.0600  SELL 0.3655  -
MLCF  CEMENT   90.90  0.031751   90.9724   90.9000  HOLD 0.3582  -
NBP   BANKS   162.01  0.032031  162.6487  162.0100  BUY  0.3417  0.0527
"""


def _candidates() -> list[Candidate]:
    rows = []
    for line in INPUTS.strip().splitlines():
        ticker, sector, price, vol, forecast, close, signal, prob, sentiment = line.split()
        rows.append(
            Candidate(
                ticker=ticker,
                sector=sector,
                price=D(price),
                volatility=D(vol),
                expected_return=D(forecast) / D(close) - 1,
                signal=signal,
                signal_probability=D(prob),
                sentiment_score=None if sentiment == "-" else D(sentiment),
            )
        )
    return rows


def test_worked_example_selects_the_eight_lowest_risk_weights():
    result = allocate(_candidates(), D("100000"), RISK_RULES["moderate"], RATES)
    assert [h.scored.ticker for h in result.holdings] == list(WORKED_EXAMPLE)
    # SYS is ninth, just behind HBL (raw weight 42.62 vs 42.73 by hand)
    assert result.ranked[8].ticker == "SYS"
    assert result.unaffordable == []


def test_worked_example_weights_match_hand_calculation():
    result = allocate(_candidates(), D("100000"), RISK_RULES["moderate"], RATES)
    by_hand = {
        "MARI": "14.9",
        "EFERT": "14.2",
        "OGDC": "12.6",
        "FFC": "12.6",
        "HUBC": "11.7",
        "MEBL": "11.6",
        "PSO": "11.5",
        "HBL": "10.9",
    }
    for holding in result.holdings:
        assert round(holding.target_weight * 100, 1) == D(by_hand[holding.scored.ticker])
    ffc = next(h for h in result.holdings if h.scored.ticker == "FFC")
    assert round(ffc.tilt_effect_pp, 2) == D("0.30")


def test_worked_example_shares_and_costs_equal_the_cost_engine_fixtures():
    result = allocate(_candidates(), D("100000"), RISK_RULES["moderate"], RATES)
    for holding in result.holdings:
        shares, price, gross, *_, charges, cost = WORKED_EXAMPLE[holding.scored.ticker]
        purchase = holding.purchase
        assert (purchase.shares, purchase.price) == (shares, D(price))
        assert purchase.gross == D(gross)
        assert purchase.charges.total == D(charges)
        assert purchase.total_cost == D(cost)
    assert result.gross_total == D("99706.41")
    assert result.charges_total == D("180.80")
    assert result.cost_total == D("99887.21")
    assert result.idle.amount == D("112.79")
    # Rs 112.79 is less than one share of any holding, so nothing could have used it
    assert result.idle.flagged is False


def test_same_inputs_give_the_same_portfolio_in_any_order():
    first = allocate(_candidates(), D("100000"), RISK_RULES["moderate"], RATES)
    shuffled = _candidates()
    random.Random(3).shuffle(shuffled)
    second = allocate(shuffled, D("100000"), RISK_RULES["moderate"], RATES)
    assert [(h.scored.ticker, h.purchase) for h in first.holdings] == [
        (h.scored.ticker, h.purchase) for h in second.holdings
    ]


def test_idle_cash_is_flagged_when_caps_block_it():
    # Two sectors left (filter + exclusions): Aggressive caps each sector at 40%, so about
    # 20% of the capital cannot be placed although it could buy more shares
    kept = [c for c in _candidates() if c.ticker in {"MARI", "OGDC", "FFC", "EFERT"}]
    result = allocate(kept, D("100000"), RISK_RULES["aggressive"], RATES)
    assert len(result.holdings) == 4
    assert result.idle.flagged is True
    assert result.idle.amount > D("19000")
    assert set(result.idle.blocked_by.values()) == {"sector_cap"}
    sector_cost = {}
    for h in result.holdings:
        sector_cost[h.scored.candidate.sector] = (
            sector_cost.get(h.scored.candidate.sector, D(0)) + h.purchase.total_cost
        )
    assert all(cost <= D("40000") for cost in sector_cost.values())


def test_low_capital_explains_instead_of_building_an_unbalanced_portfolio():
    # Rs 500 at Moderate: no holding may exceed 20% (Rs 100), and only PAEL and MLCF cost
    # Rs 100 or less a share, so 5 holdings are impossible whatever the selection
    with pytest.raises(CapitalTooLow):
        allocate(_candidates(), D("500"), RISK_RULES["moderate"], RATES)

    smallest = minimum_capital(_candidates(), D("500"), RISK_RULES["moderate"], RATES)
    assert smallest is not None and smallest > D("500")
    result = allocate(_candidates(), smallest, RISK_RULES["moderate"], RATES)
    assert len(result.holdings) >= RISK_RULES["moderate"].min_holdings
    assert all(
        h.purchase.total_cost <= RISK_RULES["moderate"].max_stock_weight * smallest
        for h in result.holdings
    )
    with pytest.raises(CapitalTooLow):
        allocate(_candidates(), smallest - 500, RISK_RULES["moderate"], RATES)


def test_too_few_eligible_stocks_is_not_a_capital_problem():
    with pytest.raises(TooFewEligibleStocks):
        allocate(_candidates()[:4], D("100000"), RISK_RULES["moderate"], RATES)


def test_cap_weights_respects_stock_and_sector_limits():
    raw = {"A": D(10), "B": D(1), "C": D(1), "D": D(1), "E": D(1)}
    sectors = {"A": "x", "B": "x", "C": "y", "D": "z", "E": "w"}
    weights = cap_weights(raw, sectors, D("0.30"), D("0.40"))
    assert weights["A"] == D("0.30")
    assert weights["A"] + weights["B"] <= D("0.40")
    assert sum(weights.values()) == pytest.approx(D(1))


@pytest.mark.parametrize("category", ["conservative", "moderate", "aggressive"])
def test_tilt_never_moves_a_weight_more_than_its_bound(category):
    rules = RISK_RULES[category]
    rng = random.Random(category)
    sectors = ["s1", "s2", "s3", "s4", "s5", "s6"]
    for trial in range(300):
        candidates = [
            Candidate(
                ticker=f"T{i:02d}",
                sector=rng.choice(sectors),
                price=D(rng.randint(2000, 200000)) / 100,
                volatility=D(rng.randint(100, 450)) / 10000,
                expected_return=D(rng.randint(-300, 300)) / 10000,
                signal=rng.choice(["BUY", "SELL", "HOLD"]),
                signal_probability=D(rng.randint(30, 90)) / 100,
                sentiment_score=rng.choice([None, D(rng.randint(-100, 100)) / 100]),
            )
            for i in range(rng.randint(rules.min_holdings, 18))
        ]
        try:
            result = allocate(candidates, D("10000000"), rules, RATES)
        except (CapitalTooLow, TooFewEligibleStocks):
            continue
        for holding in result.holdings:
            assert abs(holding.tilt_effect_pp) <= rules.tilt_bound_pp, (trial, holding)
            assert holding.target_weight <= rules.max_stock_weight
