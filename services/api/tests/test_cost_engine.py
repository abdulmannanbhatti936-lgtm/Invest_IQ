"""
Step 5.1: the cost engine against figures calculated by hand (DetailedReport.md Phase 5,
worked example: Rs 100,000, Moderate, prices as of the 7 Oct 2026 close, rates
psx-costs-2026-10-11.2). These are exact matches, never approximations; the portfolio
integration tests compare the API's figures with the same fixtures.
"""

import random
from decimal import Decimal as D

import pytest

from services.cost_engine import (
    FilerStatus,
    InvalidCommissionRate,
    break_even_price,
    buy,
    capital_gains_tax,
    check_commission_rate,
    dividend_income,
    load_rates,
    max_affordable_shares,
    round_trip_rate,
    sell,
    to_paisa,
    trade_charges,
)

RATES = load_rates()
FEE_ORDER = (
    "cdc_fee",
    "psx_trading_fee",
    "psx_regulatory_fee",
    "secp_levy",
    "nccpl_trade_fee",
    "nccpl_secp_fee",
)

# By hand. Columns: shares, price, gross, commission, sales tax, CDC, PSX fee, regulatory fee,
# SECP levy, NCCPL trade fee, NCCPL SECP fee, total charges, total cost
WORKED_EXAMPLE_TABLE = """
MARI   23  642.42  14775.66  22.16  3.32  0.53  0.52  0  0.10  0.12  0.04  26.79  14802.45
EFERT  73  193.00  14089.00  21.13  3.17  0.51  0.49  0  0.09  0.11  0.04  25.54  14114.54
OGDC   40  315.91  12636.40  18.95  2.84  0.45  0.44  0  0.08  0.10  0.04  22.90  12659.30
FFC    23  539.51  12408.73  18.61  2.79  0.45  0.43  0  0.08  0.10  0.04  22.50  12431.23
HUBC   58  200.49  11628.42  17.44  2.62  0.42  0.41  0  0.08  0.09  0.03  21.09  11649.51
MEBL   21  550.10  11552.10  17.33  2.60  0.42  0.40  0  0.08  0.09  0.03  20.95  11573.05
PSO    33  355.86  11743.38  17.62  2.64  0.42  0.41  0  0.08  0.10  0.04  21.31  11764.69
HBL    36  302.02  10872.72  16.31  2.45  0.39  0.38  0  0.07  0.09  0.03  19.72  10892.44
"""
WORKED_EXAMPLE = {
    cells[0]: (int(cells[1]), *cells[2:6], tuple(cells[6:12]), *cells[12:])
    for cells in (line.split() for line in WORKED_EXAMPLE_TABLE.strip().splitlines())
}


def test_rates_file_is_the_reviewed_version():
    assert RATES.version == "psx-costs-2026-10-11.2"
    assert tuple(f.key for f in RATES.fees) == FEE_ORDER
    assert RATES.commission_rate == D("0.0015")
    assert RATES.sales_tax_rate == D("0.15")


@pytest.mark.parametrize("ticker", WORKED_EXAMPLE)
def test_worked_example_buy_side_matches_hand_calculation(ticker):
    shares, price, gross, commission, sales_tax, fees, charges, cost = WORKED_EXAMPLE[ticker]
    purchase = buy(shares, D(price), RATES)

    assert purchase.gross == D(gross)
    assert purchase.charges.commission == D(commission)
    assert purchase.charges.sales_tax == D(sales_tax)
    assert purchase.charges.fees == tuple(zip(FEE_ORDER, map(D, fees), strict=True))
    assert purchase.charges.total == D(charges)
    assert purchase.total_cost == D(cost)


def test_worked_example_totals():
    purchases = [buy(row[0], D(row[1]), RATES) for row in WORKED_EXAMPLE.values()]
    assert sum(p.gross for p in purchases) == D("99706.41")
    assert sum(p.charges.total for p in purchases) == D("180.80")
    assert sum(p.total_cost for p in purchases) == D("99887.21")
    assert D("100000") - sum(p.total_cost for p in purchases) == D("112.79")


def test_ffc_exit_at_the_forecast_is_a_loss_with_no_cgt():
    sale = sell(23, D("539.94"), D("12431.23"), FilerStatus.filer, RATES)

    assert sale.gross == D("12418.62")
    assert (sale.charges.commission, sale.charges.sales_tax) == (D("18.63"), D("2.79"))
    assert sale.charges.fees == tuple(
        zip(FEE_ORDER, map(D, ("0.45", "0.43", "0", "0.08", "0.10", "0.04")), strict=True)
    )
    assert sale.charges.total == D("22.52")
    assert sale.proceeds == D("12396.10")
    assert sale.gain == D("-35.13")
    assert sale.cgt == D("0")
    assert sale.net_return == D("-35.13")


def test_ffc_break_even_price():
    assert break_even_price(23, D("12431.23"), RATES) == D("541.48")
    # One paisa lower falls one paisa short
    assert sell(23, D("541.47"), D("12431.23"), FilerStatus.filer, RATES).gain == D("-0.01")
    assert sell(23, D("541.48"), D("12431.23"), FilerStatus.filer, RATES).gain == D("0.22")


def test_ffc_sale_with_a_gain_pays_cgt():
    sale = sell(23, D("600.00"), D("12431.23"), FilerStatus.filer, RATES)

    assert sale.gross == D("13800.00")
    assert (sale.charges.commission, sale.charges.sales_tax) == (D("20.70"), D("3.11"))
    assert sale.charges.total == D("25.03")
    assert sale.proceeds == D("13774.97")
    assert sale.gain == D("1343.74")
    assert sale.cgt == D("201.56")
    assert sale.net_proceeds == D("13573.41")
    assert sale.net_return == D("1142.18")


def test_non_filer_pays_the_same_cgt_and_double_dividend_wht():
    filer = sell(23, D("600.00"), D("12431.23"), FilerStatus.filer, RATES)
    non_filer = sell(23, D("600.00"), D("12431.23"), FilerStatus.non_filer, RATES)
    assert non_filer.cgt == filer.cgt == D("201.56")

    assert dividend_income(23, D("41.0"), FilerStatus.filer, RATES).wht == D("141.45")
    assert dividend_income(23, D("41.0"), FilerStatus.filer, RATES).net == D("801.55")
    assert dividend_income(23, D("41.0"), FilerStatus.non_filer, RATES).wht == D("282.90")
    assert dividend_income(23, D("41.0"), FilerStatus.non_filer, RATES).net == D("660.10")


def test_zero_gain_pays_no_cgt():
    assert capital_gains_tax(D("0"), FilerStatus.filer, RATES) == D("0")
    assert capital_gains_tax(D("-500.00"), FilerStatus.non_filer, RATES) == D("0")
    assert capital_gains_tax(D("0.01"), FilerStatus.filer, RATES) == D("0.00")
    assert capital_gains_tax(D("0.04"), FilerStatus.filer, RATES) == D("0.01")


def test_per_share_minimum_commission_applies_to_cheap_shares():
    # 1,000 shares at Rs 10: 0.15% of Rs 10,000 is Rs 15, below Rs 0.03 x 1,000 = Rs 30
    charges = trade_charges(1000, D("10.00"), RATES)
    assert charges.commission == D("30.00")
    assert charges.sales_tax == D("4.50")


def test_sales_tax_is_charged_on_the_rounded_commission():
    # 0.15% of Rs 2,196.67 is Rs 3.295005, so the commission line is Rs 3.30 and its tax
    # Rs 0.495 -> 0.50; tax on the unrounded commission would be Rs 0.494 -> 0.49
    charges = trade_charges(1, D("2196.67"), RATES)
    assert charges.commission == D("3.30")
    assert charges.sales_tax == D("0.50")


def test_tiny_trade_rounds_small_fees_to_zero():
    charges = trade_charges(1, D("34.06"), RATES)
    assert charges.commission == D("0.05")
    assert charges.sales_tax == D("0.01")
    assert all(amount == D("0.00") for _, amount in charges.fees)


def test_commission_override_is_checked_against_the_psx_limits():
    assert check_commission_rate(D("0.0025"), RATES) == D("0.0025")
    with pytest.raises(InvalidCommissionRate):
        check_commission_rate(D("0.0014"), RATES)
    with pytest.raises(InvalidCommissionRate):
        check_commission_rate(D("0.0251"), RATES)
    assert trade_charges(23, D("539.51"), RATES, D("0.0025")).commission == D("31.02")


def test_max_affordable_shares_matches_the_exact_cost():
    assert max_affordable_shares(D("539.51"), D("12551.72"), RATES) == 23
    assert max_affordable_shares(D("200.49"), D("11662.27"), RATES) == 58
    assert max_affordable_shares(D("200.49"), D("11649.50"), RATES) == 57
    assert max_affordable_shares(D("1626.80"), D("1000"), RATES) == 0


def test_round_trip_rate_for_ffc():
    assert to_paisa(round_trip_rate(23, D("539.51"), RATES) * 100) == D("0.36")


def test_invariants_hold_for_random_trades():
    rng = random.Random(5)
    for _ in range(2000):
        shares = rng.randint(1, 5000)
        price = D(rng.randint(100, 500_000)) / 100
        sell_price = D(rng.randint(100, 500_000)) / 100
        status = rng.choice(list(FilerStatus))

        purchase = buy(shares, price, RATES)
        charges = purchase.charges
        assert charges.commission >= 0 and charges.sales_tax >= 0
        assert all(amount >= 0 for _, amount in charges.fees)
        assert purchase.total_cost >= purchase.gross

        sale = sell(shares, sell_price, purchase.total_cost, status, RATES)
        assert sale.cgt >= 0
        assert sale.net_proceeds <= sale.gross
        assert sale.net_return <= sale.gross - purchase.gross

        dividend = dividend_income(shares, D("5.25"), status, RATES)
        assert 0 <= dividend.net <= dividend.gross
