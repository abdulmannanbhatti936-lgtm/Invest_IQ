"""
Portfolio rolling (PRD.md FR25). A holding is a candidate for switching only when both hold:

1. Trigger: at least 20 trading days have passed, it trails the benchmark by more than one
   20-day volatility (daily sigma x sqrt(20)), and its latest forecast is SELL or a fall.
2. Cost test: the expected gain from switching, (expected return of the replacement minus
   that of the holding) x the money moved, beats the switch's cost: selling charges, CGT on
   any gain and buying charges. The forecasts are for the next trading day only, so the
   expected gain is a one-day figure and rarely beats the costs; that is reported honestly.
"""

import enum
from dataclasses import dataclass, replace
from decimal import Decimal

from core.portfolio_rules import ROLL_SIGMA_MULTIPLE, ROLL_WINDOW_TRADING_DAYS
from services import cost_engine
from services.cost_engine import FilerStatus, Purchase, Rates, Sale


class RollStatus(str, enum.Enum):
    too_early = "too_early"
    not_triggered = "not_triggered"
    no_replacement = "no_replacement"
    costs_exceed_benefit = "costs_exceed_benefit"
    suggested = "suggested"


@dataclass(frozen=True)
class HeldStock:
    ticker: str
    shares: int
    total_cost: Decimal
    entry_price: Decimal
    current_price: Decimal
    volatility: Decimal
    expected_return: Decimal
    signal: str


@dataclass(frozen=True)
class Replacement:
    ticker: str
    price: Decimal
    expected_return: Decimal


@dataclass(frozen=True)
class RollCheck:
    ticker: str
    status: RollStatus
    trading_days: int
    holding_return: Decimal
    benchmark_return: Decimal
    threshold: Decimal
    weak_forecast: bool
    replacement: Replacement | None = None
    sale: Sale | None = None
    purchase: Purchase | None = None
    expected_benefit: Decimal | None = None

    @property
    def relative_return(self) -> Decimal:
        return self.holding_return - self.benchmark_return

    @property
    def switch_cost(self) -> Decimal | None:
        """Selling charges + CGT on any gain + buying charges."""
        if self.sale is None or self.purchase is None:
            return None
        return self.sale.charges.total + self.sale.cgt + self.purchase.charges.total


def underperformance_threshold(volatility: Decimal) -> Decimal:
    return ROLL_SIGMA_MULTIPLE * volatility * Decimal(ROLL_WINDOW_TRADING_DAYS).sqrt()


def check_holding(
    held: HeldStock,
    benchmark_return: Decimal,
    trading_days: int,
    replacements: list[Replacement],
    filer_status: FilerStatus,
    rates: Rates,
    commission_rate: Decimal | None = None,
) -> RollCheck:
    holding_return = held.current_price / held.entry_price - 1
    threshold = underperformance_threshold(held.volatility)
    weak = held.signal == "SELL" or held.expected_return < 0
    base = dict(
        ticker=held.ticker,
        trading_days=trading_days,
        holding_return=holding_return,
        benchmark_return=benchmark_return,
        threshold=threshold,
        weak_forecast=weak,
    )
    if trading_days < ROLL_WINDOW_TRADING_DAYS:
        return RollCheck(status=RollStatus.too_early, **base)
    if not (holding_return - benchmark_return < -threshold and weak):
        return RollCheck(status=RollStatus.not_triggered, **base)

    better = sorted(
        (r for r in replacements if r.expected_return > held.expected_return),
        key=lambda r: (-r.expected_return, r.ticker),
    )
    if not better:
        return RollCheck(status=RollStatus.no_replacement, **base)
    best = better[0]

    sale = cost_engine.sell(
        held.shares, held.current_price, held.total_cost, filer_status, rates, commission_rate
    )
    shares = cost_engine.max_affordable_shares(
        best.price, sale.net_proceeds, rates, commission_rate
    )
    if shares == 0:
        return RollCheck(status=RollStatus.no_replacement, replacement=best, sale=sale, **base)
    purchase = cost_engine.buy(shares, best.price, rates, commission_rate)
    benefit = cost_engine.to_paisa(
        (best.expected_return - held.expected_return) * sale.net_proceeds
    )
    check = RollCheck(
        status=RollStatus.suggested,
        replacement=best,
        sale=sale,
        purchase=purchase,
        expected_benefit=benefit,
        **base,
    )
    if benefit <= check.switch_cost:
        return replace(check, status=RollStatus.costs_exceed_benefit)
    return check
