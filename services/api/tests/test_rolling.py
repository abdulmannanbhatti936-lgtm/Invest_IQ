"""
Step 5.4: rolling (FR25) with hand-worked figures. The holding is the worked example's HBL
(36 shares, total cost Rs 10,892.44); the replacement is SYS at Rs 117.96 with its real
forecast (Rs 118.3374, an expected rise of 0.31994%).
"""

from decimal import Decimal as D

from services.cost_engine import FilerStatus, load_rates
from services.rolling import HeldStock, Replacement, RollStatus, check_holding

RATES = load_rates()
SYS = Replacement("SYS", D("117.96"), D("118.3374") / D("117.96") - 1)


def _hbl(current: str, expected_return: str, signal: str = "HOLD") -> HeldStock:
    return HeldStock(
        ticker="HBL",
        shares=36,
        total_cost=D("10892.44"),
        entry_price=D("302.02"),
        current_price=D(current),
        volatility=D("0.023443"),
        expected_return=D(expected_return),
        signal=signal,
    )


def _check(held: HeldStock, benchmark: str, days: int = 25):
    return check_holding(held, D(benchmark), days, [SYS], FilerStatus.filer, RATES)


def test_too_early_before_twenty_trading_days():
    result = _check(_hbl("270.00", "-0.0005"), "0.02", days=19)
    assert result.status == RollStatus.too_early


def test_not_triggered_when_the_forecast_is_not_weak():
    # Far behind the benchmark, but the forecast is a rise and the signal is not SELL
    result = _check(_hbl("270.00", "0.0002"), "0.02")
    assert result.status == RollStatus.not_triggered
    assert result.weak_forecast is False


def test_not_triggered_within_one_volatility_of_the_benchmark():
    # Threshold = 0.023443 x sqrt(20) = 10.48%; trailing by 8.0% is within it
    result = _check(_hbl("284.00", "-0.0005"), "0.02")
    assert round(result.threshold, 4) == D("0.1048")
    assert result.status == RollStatus.not_triggered


def test_underperforming_holding_with_a_clear_edge_is_suggested():
    result = _check(_hbl("270.00", "-0.0005"), "0.02")

    # Sell 36 HBL at 270.00: gross 9,720.00, charges 17.63, a loss so no CGT
    assert result.sale.gross == D("9720.00")
    assert result.sale.charges.total == D("17.63")
    assert result.sale.cgt == D("0")
    assert result.sale.net_proceeds == D("9702.37")
    # Buy 82 SYS: gross 9,672.72, charges 17.55
    assert result.purchase.shares == 82
    assert result.purchase.charges.total == D("17.55")
    assert result.switch_cost == D("35.18")
    # (0.31994% + 0.05%) x 9,702.37 = 35.89 > 35.18
    assert result.expected_benefit == D("35.89")
    assert result.status == RollStatus.suggested
    assert result.replacement.ticker == "SYS"


def test_triggered_but_the_costs_exceed_the_expected_gain():
    result = _check(_hbl("270.00", "-0.0001"), "0.02")
    # (0.31994% + 0.01%) x 9,702.37 = 32.01 < 35.18
    assert result.expected_benefit == D("32.01")
    assert result.status == RollStatus.costs_exceed_benefit


def test_cgt_on_a_gain_counts_as_a_switching_cost():
    # HBL rose 6.0% but the benchmark rose 20%, and the signal is SELL
    result = _check(_hbl("320.00", "0.0001", signal="SELL"), "0.20")

    assert result.sale.charges.total == D("20.87")
    assert result.sale.gain == D("606.69")
    assert result.sale.cgt == D("91.00")
    assert result.purchase.shares == 96
    assert result.purchase.charges.total == D("20.54")
    assert result.switch_cost == D("132.41")
    assert result.expected_benefit == D("35.36")
    assert result.status == RollStatus.costs_exceed_benefit


def test_no_replacement_when_nothing_is_forecast_to_do_better():
    weak_sys = Replacement("SYS", D("117.96"), D("-0.001"))
    result = check_holding(
        _hbl("270.00", "-0.0005"), D("0.02"), 25, [weak_sys], FilerStatus.filer, RATES
    )
    assert result.status == RollStatus.no_replacement
