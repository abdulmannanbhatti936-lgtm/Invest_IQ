"""
Backtest metrics (PRD.md FR31), in Decimal, with the formulas approved for Phase 6.

`values` is a value series on trading days: values[0] is the capital on the start date (so the
buying charges fall in the first period), each later value is the portfolio marked to that
day's close. Selling charges and CGT reach only the net total return; putting them in the last
day's return would distort the Sharpe ratio and the win rate.

QuantStats is used only in the tests as an independent cross-check (Architecture.md §3).
"""

import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

CALENDAR_YEAR_DAYS = Decimal("365.25")


class RiskFree(Protocol):
    def interval_return(self, previous: datetime.date, current: datetime.date) -> Decimal: ...


@dataclass(frozen=True)
class Drawdown:
    depth: Decimal  # zero or negative
    peak_date: datetime.date | None
    trough_date: datetime.date | None


@dataclass(frozen=True)
class Metrics:
    total_return: Decimal
    total_return_before_sale: Decimal
    annualised_return: Decimal
    sharpe_ratio: Decimal | None
    max_drawdown: Drawdown
    months_won: int
    months_total: int

    @property
    def win_rate(self) -> Decimal | None:
        return Decimal(self.months_won) / self.months_total if self.months_total else None


def period_returns(values: list[Decimal]) -> list[Decimal]:
    return [current / previous - 1 for previous, current in zip(values, values[1:], strict=False)]


def annualised_return(total_return: Decimal, start: datetime.date, end: datetime.date) -> Decimal:
    """(1 + total return) ^ (365.25 / calendar days) - 1."""
    days = (end - start).days
    return (1 + total_return) ** (CALENDAR_YEAR_DAYS / days) - 1


def periods_per_year(dates: list[datetime.date]) -> Decimal:
    """
    Observed trading days per year (about 245 for PSX), not the US convention of 252, so the
    annualisation matches the market and the sampling the series actually has.
    """
    return Decimal(len(dates) - 1) / (Decimal((dates[-1] - dates[0]).days) / CALENDAR_YEAR_DAYS)


def sharpe_ratio(
    dates: list[datetime.date], values: list[Decimal], risk_free: RiskFree
) -> Decimal | None:
    """
    mean(r - rf) / sd(r - rf) x sqrt(periods per year), sample standard deviation (n - 1).
    None when there are fewer than two returns or they never vary.
    """
    returns = period_returns(values)
    excess = [
        r - risk_free.interval_return(previous, current)
        for r, previous, current in zip(returns, dates, dates[1:], strict=False)
    ]
    if len(excess) < 2:
        return None
    mean = sum(excess, Decimal(0)) / len(excess)
    variance = sum(((e - mean) ** 2 for e in excess), Decimal(0)) / (len(excess) - 1)
    if variance == 0:
        return None
    return mean / variance.sqrt() * periods_per_year(dates).sqrt()


def max_drawdown(dates: list[datetime.date], values: list[Decimal]) -> Drawdown:
    """The largest fall from a running high, min over t of (V_t / max(V_0..V_t) - 1)."""
    worst = Drawdown(Decimal(0), None, None)
    peak_value, peak_date = values[0], dates[0]
    for day, value in zip(dates, values, strict=True):
        if value > peak_value:
            peak_value, peak_date = value, day
        depth = value / peak_value - 1
        if depth < worst.depth:
            worst = Drawdown(depth, peak_date, day)
    return worst


def monthly_wins(dates: list[datetime.date], values: list[Decimal]) -> tuple[int, int]:
    """
    Months in which the value rose, out of the months with a trading day after the start.
    Each month is its last value against the previous month's last value (the first against
    the start value); a month with no change does not count as a win.
    """
    month_ends: dict[tuple[int, int], Decimal] = {}
    for day, value in zip(dates[1:], values[1:], strict=True):
        month_ends[(day.year, day.month)] = value
    won, previous = 0, values[0]
    for value in month_ends.values():
        won += value > previous
        previous = value
    return won, len(month_ends)


def compute(
    dates: list[datetime.date],
    values: list[Decimal],
    risk_free: RiskFree,
    end_value_net: Decimal | None = None,
) -> Metrics:
    """`end_value_net` is what is left after selling; a benchmark has none."""
    capital = values[0]
    before_sale = values[-1] / capital - 1
    total = (end_value_net / capital - 1) if end_value_net is not None else before_sale
    won, months = monthly_wins(dates, values)
    return Metrics(
        total_return=total,
        total_return_before_sale=before_sale,
        annualised_return=annualised_return(total, dates[0], dates[-1]),
        sharpe_ratio=sharpe_ratio(dates, values, risk_free),
        max_drawdown=max_drawdown(dates, values),
        months_won=won,
        months_total=months,
    )
