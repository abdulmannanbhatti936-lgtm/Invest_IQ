"""
Dividend adjustment for model training and inference (method "div-v1").

WHY this exists: stored and displayed closes are not dividend-adjusted (they must equal the
prices PSX quoted), so on an ex-dividend day the close drops by roughly the dividend even
though holders lost nothing. A model fed those closes learns false losses. The training
series therefore uses the standard backward (total-return) adjustment, the method Yahoo
and CRSP use: for each ex-dividend date,

    factor = 1 - dividend / (last close before the ex-date)

and every bar before that date is multiplied by the product of the factors of all later
ex-dates. The newest bar always has factor 1, so the adjusted series ends at the real price.

A dividend is not applied when the price move on its ex-date does not look like a dividend
(team rule, 2026-10-10): if the drop from the previous close to the ex-date close is more
than twice the dividend or less than half of it (a rise counts as no drop), the provider's
amount or date may be wrong, so the adjustment is held back and flagged for review.
"""

from bisect import bisect_left
from dataclasses import dataclass
from datetime import date

METHOD_VERSION = "div-v1"
MISMATCH_FLAG = "drop_mismatch"  # ex-date move is not within 0.5x-2x of the dividend
NO_BAR_FLAG = "no_bar"  # no traded bar on one side of the ex-date
MAX_DROP_RATIO = 2.0


@dataclass(frozen=True)
class Dividend:
    day: date
    amount: float


@dataclass(frozen=True)
class DividendDecision:
    day: date
    amount: float
    previous_close: float | None
    ex_close: float | None
    factor: float | None  # None: not applied
    flag: str | None

    @property
    def yield_pct(self) -> float | None:
        if not self.previous_close:
            return None
        return self.amount / self.previous_close * 100


def assess(
    dates: list[date], closes: list[float], dividends: list[Dividend]
) -> list[DividendDecision]:
    """
    Decide each dividend against a stock's served (split-adjusted, unflagged) closes,
    given in date order. The ex-date bar is the first bar on or after the ex-date, since
    the provider's date can fall on a day without a bar.
    """
    decisions = []
    for dividend in sorted(dividends, key=lambda d: d.day):
        ex_index = bisect_left(dates, dividend.day)
        if ex_index == 0 or ex_index == len(dates):
            decisions.append(
                DividendDecision(dividend.day, dividend.amount, None, None, None, NO_BAR_FLAG)
            )
            continue
        previous_close, ex_close = closes[ex_index - 1], closes[ex_index]
        drop = previous_close - ex_close
        plausible = dividend.amount / MAX_DROP_RATIO <= drop <= dividend.amount * MAX_DROP_RATIO
        decisions.append(
            DividendDecision(
                day=dividend.day,
                amount=dividend.amount,
                previous_close=previous_close,
                ex_close=ex_close,
                factor=1 - dividend.amount / previous_close if plausible else None,
                flag=None if plausible else MISMATCH_FLAG,
            )
        )
    return decisions


def cumulative_factors(dates: list[date], applied: list[tuple[date, float]]) -> list[float]:
    """Per bar: the product of the factors of every applied ex-date after the bar's date."""
    factors = []
    for day in dates:
        product = 1.0
        for ex_date, factor in applied:
            if ex_date > day:
                product *= factor
        factors.append(product)
    return factors
