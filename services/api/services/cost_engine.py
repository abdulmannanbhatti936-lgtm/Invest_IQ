"""
Trading costs and taxes on PSX ready-market trades (PRD.md FR26), in Decimal only
(Rules.md §3.4). Every rate comes from the versioned rates file; this module holds the only
copy of the arithmetic, and portfolio code calls it instead of repeating it.

Rounding rule: each charge line is rounded to the paisa (half up) per holding and side, as
on a broker's contract note; sales tax is charged on the rounded commission line; totals are
sums of rounded lines; tax amounts are rounded the same way.
"""

import enum
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "integrations" / "data"
RATES_FILE = DATA_DIR / "psx_costs_2026-10-11.json"

PAISA = Decimal("0.01")
ZERO = Decimal("0")


def to_paisa(amount: Decimal) -> Decimal:
    return amount.quantize(PAISA, rounding=ROUND_HALF_UP)


class FilerStatus(str, enum.Enum):
    filer = "filer"
    non_filer = "non_filer"


@dataclass(frozen=True)
class Fee:
    key: str
    rate: Decimal
    status: str
    source_url: str


@dataclass(frozen=True)
class Rates:
    version: str
    checked_on: str
    commission_rate: Decimal
    commission_per_share_minimum: Decimal
    commission_max_rate: Decimal
    sales_tax_rate: Decimal
    fees: tuple[Fee, ...]
    cgt_filer_rate: Decimal
    cgt_non_filer_rate: Decimal
    cgt_status: str
    cgt_non_filer_label: str
    wht_filer_rate: Decimal
    wht_non_filer_rate: Decimal
    not_modelled: tuple[str, ...]

    def cgt_rate(self, filer_status: FilerStatus) -> Decimal:
        return self.cgt_filer_rate if filer_status == FilerStatus.filer else self.cgt_non_filer_rate

    def wht_rate(self, filer_status: FilerStatus) -> Decimal:
        return self.wht_filer_rate if filer_status == FilerStatus.filer else self.wht_non_filer_rate

    def approximate_side_rate(self, commission_rate: Decimal) -> Decimal:
        """Charges per rupee traded before rounding; only used to start a search."""
        return commission_rate * (1 + self.sales_tax_rate) + sum(f.rate for f in self.fees)


def _parse_rates(data: dict) -> Rates:
    commission = data["commission"]
    return Rates(
        version=data["version"],
        checked_on=data["checked_on"],
        commission_rate=Decimal(commission["rate"]),
        commission_per_share_minimum=Decimal(commission["per_share_minimum"]),
        commission_max_rate=Decimal(commission["max_rate"]),
        sales_tax_rate=Decimal(data["sales_tax_on_commission"]["rate"]),
        fees=tuple(
            Fee(f["key"], Decimal(f["rate"]), f["status"], f["source_url"]) for f in data["fees"]
        ),
        cgt_filer_rate=Decimal(data["cgt"]["filer_rate"]),
        cgt_non_filer_rate=Decimal(data["cgt"]["non_filer_rate"]),
        cgt_status=data["cgt"]["status"],
        cgt_non_filer_label=data["cgt"]["non_filer_label"],
        wht_filer_rate=Decimal(data["dividend_wht"]["filer_rate"]),
        wht_non_filer_rate=Decimal(data["dividend_wht"]["non_filer_rate"]),
        not_modelled=tuple(data["not_modelled"]),
    )


@lru_cache
def load_rates(path: Path = RATES_FILE) -> Rates:
    return _parse_rates(json.loads(path.read_text(encoding="utf-8")))


class InvalidCommissionRate(ValueError):
    pass


def check_commission_rate(rate: Decimal, rates: Rates) -> Decimal:
    """A user's own broker rate must lie between the PSX floor and the PSX ceiling."""
    if rate < rates.commission_rate or rate > rates.commission_max_rate:
        raise InvalidCommissionRate(
            "Commission rate must be between "
            f"{rates.commission_rate} and {rates.commission_max_rate}"
        )
    return rate


@dataclass(frozen=True)
class Charges:
    commission: Decimal
    sales_tax: Decimal
    fees: tuple[tuple[str, Decimal], ...]

    @property
    def total(self) -> Decimal:
        return self.commission + self.sales_tax + sum((amount for _, amount in self.fees), ZERO)


def trade_charges(
    shares: int, price: Decimal, rates: Rates, commission_rate: Decimal | None = None
) -> Charges:
    """Charges on one side (buy or sell) of a trade of `shares` at `price`."""
    if shares <= 0:
        raise ValueError("A trade needs at least one share")
    gross = to_paisa(shares * price)
    rate = rates.commission_rate if commission_rate is None else commission_rate
    # PSX floor: 0.15% of the value or Rs 0.03 per share, whichever is higher
    commission = max(to_paisa(gross * rate), to_paisa(shares * rates.commission_per_share_minimum))
    sales_tax = to_paisa(commission * rates.sales_tax_rate)
    fees = tuple((fee.key, to_paisa(gross * fee.rate)) for fee in rates.fees)
    return Charges(commission, sales_tax, fees)


@dataclass(frozen=True)
class Purchase:
    shares: int
    price: Decimal
    gross: Decimal
    charges: Charges

    @property
    def total_cost(self) -> Decimal:
        return self.gross + self.charges.total


def buy(
    shares: int, price: Decimal, rates: Rates, commission_rate: Decimal | None = None
) -> Purchase:
    charges = trade_charges(shares, price, rates, commission_rate)
    return Purchase(shares, price, to_paisa(shares * price), charges)


def max_affordable_shares(
    price: Decimal, budget: Decimal, rates: Rates, commission_rate: Decimal | None = None
) -> int:
    """The most whole shares whose total cost, charges included, fits within `budget`."""
    if budget <= 0:
        return 0
    rate = rates.commission_rate if commission_rate is None else commission_rate
    shares = int(budget / (price * (1 + rates.approximate_side_rate(rate))))
    # The estimate ignores rounding, so settle it against the exact cost both ways
    while shares > 0 and buy(shares, price, rates, commission_rate).total_cost > budget:
        shares -= 1
    while buy(shares + 1, price, rates, commission_rate).total_cost <= budget:
        shares += 1
    return shares


def capital_gains_tax(gain: Decimal, filer_status: FilerStatus, rates: Rates) -> Decimal:
    """CGT is charged on a gain only; a loss pays none (set-off is not modelled)."""
    if gain <= 0:
        return ZERO
    return to_paisa(gain * rates.cgt_rate(filer_status))


@dataclass(frozen=True)
class Sale:
    shares: int
    price: Decimal
    gross: Decimal
    charges: Charges
    total_cost: Decimal
    cgt: Decimal

    @property
    def proceeds(self) -> Decimal:
        """Sale value after selling charges, before CGT."""
        return self.gross - self.charges.total

    @property
    def gain(self) -> Decimal:
        return self.proceeds - self.total_cost

    @property
    def net_proceeds(self) -> Decimal:
        return self.proceeds - self.cgt

    @property
    def net_return(self) -> Decimal:
        return self.net_proceeds - self.total_cost


def sell(
    shares: int,
    price: Decimal,
    total_cost: Decimal,
    filer_status: FilerStatus,
    rates: Rates,
    commission_rate: Decimal | None = None,
) -> Sale:
    """Selling `shares` bought for `total_cost` (charges included) at `price`."""
    gross = to_paisa(shares * price)
    charges = trade_charges(shares, price, rates, commission_rate)
    gain = gross - charges.total - total_cost
    return Sale(
        shares,
        price,
        gross,
        charges,
        total_cost,
        capital_gains_tax(gain, filer_status, rates),
    )


def break_even_price(
    shares: int, total_cost: Decimal, rates: Rates, commission_rate: Decimal | None = None
) -> Decimal:
    """The lowest price, to the paisa, at which selling returns at least the total cost."""
    rate = rates.commission_rate if commission_rate is None else commission_rate

    def covers(price: Decimal) -> bool:
        proceeds = to_paisa(shares * price) - trade_charges(shares, price, rates, rate).total
        return proceeds >= total_cost

    price = to_paisa(total_cost / (shares * (1 - rates.approximate_side_rate(rate))))
    while not covers(price):
        price += PAISA
    while price > PAISA and covers(price - PAISA):
        price -= PAISA
    return price


def round_trip_rate(
    shares: int, price: Decimal, rates: Rates, commission_rate: Decimal | None = None
) -> Decimal:
    """Buying and then selling at the same price: both sides' charges as a share of the value."""
    gross = to_paisa(shares * price)
    one_side = trade_charges(shares, price, rates, commission_rate).total
    return (2 * one_side) / gross


@dataclass(frozen=True)
class DividendIncome:
    gross: Decimal
    wht: Decimal

    @property
    def net(self) -> Decimal:
        return self.gross - self.wht


def dividend_income(
    shares: int, dividend_per_share: Decimal, filer_status: FilerStatus, rates: Rates
) -> DividendIncome:
    gross = to_paisa(shares * dividend_per_share)
    return DividendIncome(gross, to_paisa(gross * rates.wht_rate(filer_status)))
