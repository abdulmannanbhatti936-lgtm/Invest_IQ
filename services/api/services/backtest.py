"""
Backtest engine (PRD.md FR29-FR32, method approved for Phase 6). Pure: it receives price and
dividend histories and returns the simulation; services/backtest_service.py gathers the inputs
from the database and stores the result.

Buy and hold, no rebalancing. Shares are bought at the start date's stored close, with whole
shares and every charge from services/cost_engine.py; the cash left over earns nothing. Cash
dividends (net of WHT) are credited on the ex-date and held as cash, because the KSE-100 is a
total-return index. Each holding is kept in today's share units (shares x the start bar's split
factor), so its value follows the split-adjusted closes and the provider's split-adjusted
dividend amounts. Everything is sold at the end date's close, with charges and CGT.
"""

import bisect
import datetime
from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import Decimal

from core.portfolio_rules import RiskRules
from services import cost_engine
from services.allocation import Candidate, allocate
from services.cost_engine import FilerStatus, Purchase, Rates, Sale, to_paisa

METHOD_VERSION = "bt-v1"
# A purchase may use a close up to this many trading days before the start date (e.g. a stock
# that did not trade that day), never a later one
MAX_START_GAP_TRADING_DAYS = 5


@dataclass(frozen=True)
class Bar:
    day: datetime.date
    close: Decimal  # the stored close (raw provider value)
    split_factor: Decimal

    @property
    def served(self) -> Decimal:
        return self.close / self.split_factor


@dataclass(frozen=True)
class History:
    ticker: str
    bars: list[Bar]  # served bars only, oldest first
    dividends: list[tuple[datetime.date, Decimal]]  # ex-date, Rs per share (today's units)

    def bar_on_or_before(self, day: datetime.date) -> Bar | None:
        position = bisect.bisect_right([b.day for b in self.bars], day)
        return self.bars[position - 1] if position else None


class InsufficientHistory(Exception):
    def __init__(self, required_start: datetime.date, first_dates: dict[str, datetime.date | None]):
        super().__init__(f"No close near {required_start} for {sorted(first_dates)}")
        self.required_start = required_start
        self.first_dates = first_dates


class WeightTooSmall(Exception):
    """A weight's share of the capital cannot buy one share at the start date's price."""

    def __init__(self, tickers: list[str]):
        super().__init__(f"Weight too small to buy one share: {tickers}")
        self.tickers = tickers


class UnsupportedSplit(Exception):
    """A split would leave a fraction of a share (e.g. a reverse split on an odd holding)."""

    def __init__(self, ticker: str):
        super().__init__(f"{ticker}: split leaves a fraction of a share")
        self.ticker = ticker


@dataclass(frozen=True)
class Period:
    start: datetime.date
    end: datetime.date
    calendar: list[datetime.date]  # trading days from start to end, both included


def period_for(years: int, end: datetime.date, trading_days: list[datetime.date]) -> Period:
    """The first trading day on or after `end` minus `years` (29 Feb falls back to 28 Feb)."""
    try:
        target = end.replace(year=end.year - years)
    except ValueError:
        target = end.replace(year=end.year - years, day=28)
    calendar = [d for d in trading_days if target <= d <= end]
    return Period(calendar[0], end, calendar)


def start_bars(
    histories: list[History], period: Period, all_days: list[datetime.date]
) -> dict[str, Bar]:
    """Each stock's close on the start date, or the last one within the allowed gap before it."""
    position = bisect.bisect_left(all_days, period.start)
    earliest = all_days[max(0, position - MAX_START_GAP_TRADING_DAYS)]
    bars, missing = {}, {}
    for history in histories:
        bar = history.bar_on_or_before(period.start)
        if bar is None or bar.day < earliest:
            missing[history.ticker] = history.bars[0].day if history.bars else None
        else:
            bars[history.ticker] = bar
    if missing:
        raise InsufficientHistory(period.start, missing)
    return bars


def purchases_from_weights(
    weights: dict[str, Decimal],
    capital: Decimal,
    bars: dict[str, Bar],
    rates: Rates,
    commission_rate: Decimal,
) -> dict[str, Purchase]:
    """Whole shares per stock within weight x capital, charges included (Phase 5's rule)."""
    shares = {
        ticker: cost_engine.max_affordable_shares(
            to_paisa(bars[ticker].close), weight * capital, rates, commission_rate
        )
        for ticker, weight in weights.items()
    }
    too_small = sorted(t for t, n in shares.items() if n == 0)
    if too_small:
        raise WeightTooSmall(too_small)
    return {
        t: cost_engine.buy(n, to_paisa(bars[t].close), rates, commission_rate)
        for t, n in shares.items()
    }


def purchases_from_rules(
    histories: dict[str, History],
    sectors: dict[str, str],
    capital: Decimal,
    bars: dict[str, Bar],
    rules: RiskRules,
    rates: Rates,
    commission_rate: Decimal,
    volatility_window: int,
    volatility: Callable[[list[Bar]], Decimal],
) -> dict[str, Purchase]:
    """
    The "rules applied at the start date" variant: the same risk-profile rules, with volatility
    from the closes up to the start date only and no forecast or news tilt (lambda = 0), since
    today's model cannot honestly be used on past dates. With equal weights (Aggressive) and no
    tilt, ties are ordered by ticker, as in Phase 5. `volatility` takes the bars newest first.
    """
    candidates = []
    for ticker, history in histories.items():
        closes = [b for b in history.bars if b.day <= bars[ticker].day][-(volatility_window + 1) :]
        if len(closes) < volatility_window + 1:
            continue
        candidates.append(
            Candidate(
                ticker=ticker,
                sector=sectors[ticker],
                price=to_paisa(bars[ticker].close),
                volatility=volatility(list(reversed(closes))),
                expected_return=Decimal(0),
                signal="HOLD",
                signal_probability=None,
                sentiment_score=None,
            )
        )
    allocation = allocate(
        candidates, capital, replace(rules, tilt_strength=Decimal(0)), rates, commission_rate
    )
    return {h.scored.ticker: h.purchase for h in allocation.holdings}


@dataclass(frozen=True)
class HoldingResult:
    ticker: str
    purchase: Purchase
    start_day: datetime.date
    units: int  # in today's share units
    dividends: list[tuple[datetime.date, cost_engine.DividendIncome]]
    sale: Sale
    end_day: datetime.date
    carried_forward_days: int


@dataclass(frozen=True)
class Simulation:
    dates: list[datetime.date]
    values: list[Decimal]  # values[0] = capital; then marked to market, to the paisa
    idle_cash: Decimal
    holdings: list[HoldingResult]

    @property
    def buy_charges(self) -> Decimal:
        return sum((h.purchase.charges.total for h in self.holdings), Decimal(0))

    @property
    def dividends_gross(self) -> Decimal:
        return sum((d.gross for h in self.holdings for _, d in h.dividends), Decimal(0))

    @property
    def wht(self) -> Decimal:
        return sum((d.wht for h in self.holdings for _, d in h.dividends), Decimal(0))

    @property
    def sell_charges(self) -> Decimal:
        return sum((h.sale.charges.total for h in self.holdings), Decimal(0))

    @property
    def cgt(self) -> Decimal:
        return sum((h.sale.cgt for h in self.holdings), Decimal(0))

    @property
    def end_value_net(self) -> Decimal:
        dividends = self.dividends_gross - self.wht
        proceeds = sum((h.sale.net_proceeds for h in self.holdings), Decimal(0))
        return self.idle_cash + dividends + proceeds

    @property
    def carried_forward_days(self) -> int:
        return sum(h.carried_forward_days for h in self.holdings)


def _units(ticker: str, shares: int, factor: Decimal) -> int:
    units = shares * factor
    if units != units.to_integral_value():
        raise UnsupportedSplit(ticker)
    return int(units)


def simulate(
    purchases: dict[str, Purchase],
    bars: dict[str, Bar],
    histories: dict[str, History],
    capital: Decimal,
    period: Period,
    filer_status: FilerStatus,
    rates: Rates,
    commission_rate: Decimal,
) -> Simulation:
    idle_cash = capital - sum((p.total_cost for p in purchases.values()), Decimal(0))
    units = {t: _units(t, p.shares, bars[t].split_factor) for t, p in purchases.items()}

    dividends: dict[str, list[tuple[datetime.date, cost_engine.DividendIncome]]] = {}
    for ticker in purchases:
        dividends[ticker] = [
            (ex_date, cost_engine.dividend_income(units[ticker], amount, filer_status, rates))
            for ex_date, amount in histories[ticker].dividends
            if period.start < ex_date <= period.end
        ]

    values, carried = [capital], dict.fromkeys(purchases, 0)
    for day in period.calendar[1:]:
        value = idle_cash
        for ticker in purchases:
            bar = histories[ticker].bar_on_or_before(day)
            carried[ticker] += bar.day != day
            value += units[ticker] * bar.served
            value += sum((d.net for ex, d in dividends[ticker] if ex <= day), Decimal(0))
        values.append(to_paisa(value))

    results = []
    for ticker, purchase in purchases.items():
        end_bar = histories[ticker].bar_on_or_before(period.end)
        shares_at_end = units[ticker] / end_bar.split_factor
        if shares_at_end != shares_at_end.to_integral_value():
            raise UnsupportedSplit(ticker)
        sale = cost_engine.sell(
            int(shares_at_end),
            to_paisa(end_bar.close),
            purchase.total_cost,
            filer_status,
            rates,
            commission_rate,
        )
        results.append(
            HoldingResult(
                ticker,
                purchase,
                bars[ticker].day,
                units[ticker],
                dividends[ticker],
                sale,
                end_bar.day,
                carried[ticker],
            )
        )
    return Simulation(period.calendar, values, idle_cash, results)


@dataclass(frozen=True)
class BenchmarkRun:
    dates: list[datetime.date]
    values: list[Decimal]  # starts at 1
    tickers: list[str]


def equal_weight_benchmark(
    histories: list[History], bars: dict[str, Bar], period: Period
) -> BenchmarkRun:
    """
    The stand-in benchmark: the forecast stocks in equal parts, bought and held with gross cash
    dividends kept as cash, no charges or taxes (like an index). Never called KSE-100.
    """
    tickers = sorted(h.ticker for h in histories)
    share = Decimal(1) / len(tickers)
    units = {h.ticker: share / bars[h.ticker].served for h in histories}
    values = [Decimal(1)]
    for day in period.calendar[1:]:
        value = Decimal(0)
        for history in histories:
            value += units[history.ticker] * history.bar_on_or_before(day).served
            value += sum(
                (units[history.ticker] * amount for ex, amount in history.dividends
                 if period.start < ex <= day),
                Decimal(0),
            )  # fmt: skip
        values.append(value)
    return BenchmarkRun(period.calendar, values, tickers)


def index_benchmark(closes: dict[datetime.date, Decimal], period: Period) -> BenchmarkRun | None:
    """A loaded index (KSE-100) over the period, or None when it does not cover it."""
    days = sorted(closes)
    if not days or days[-1] < period.end:
        return None
    start = bisect.bisect_right(days, period.start)
    if start == 0:
        return None
    base = closes[days[start - 1]]
    values = [Decimal(1)]
    for day in period.calendar[1:]:
        values.append(closes[days[bisect.bisect_right(days, day) - 1]] / base)
    return BenchmarkRun(period.calendar, values, [])
