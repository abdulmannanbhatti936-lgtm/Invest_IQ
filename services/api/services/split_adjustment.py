"""
Split adjustment for Yahoo Finance PSX price history (method "split-v1").

WHY this exists: Yahoo applies PSX stock splits to its history inconsistently. Older splits
(e.g. SYS 2:1 in 2022, MTL 1.5:1 in 2023) are already reflected in the history it returns,
but recent ones (LUCK 5:1 and SYS 5:1 in 2025) are not, and for roughly 35 trading days
before such a split Yahoo mixes the two price levels bar by bar (LUCK: 1456, 292, 1412,
1560, 320). Raw bars are never modified: each bar gets a divisor (`split_factor`) and the
API serves raw / factor, so the adjustment is reproducible and can be recomputed or undone.

The rule, applied to splits from the latest to the earliest (bars after a split date
already carry its new price level and keep only the factors of later splits):
1. If the raw series has no one-day jump beyond MAX_DAILY_GAP from the window start to a
   few bars after the split, the provider already adjusted this split: nothing is applied.
2. Inside the mixed window (the MIXED_WINDOW trading bars before the split date), each bar
   is either already adjusted or not. Walking backwards from the split, a bar takes
   whichever reading (raw, or raw / ratio) is nearer to the next later accepted bar. If
   neither is within MAX_DAILY_GAP of it, the bar matches no consistent price level and is
   flagged "suspect": it stays stored but is left out of charts, statistics and training.
3. Before the window, one decision per split covers every bar: the price level just before
   the window is compared with the level at the start of the window (medians of
   BOUNDARY_BARS bars). If the history sits about `ratio` times higher, Yahoo did not
   adjust it and every earlier bar is divided by the ratio; if the levels match, Yahoo
   already adjusted it and nothing is applied. The decision is stored with the split.
"""

import math
from dataclasses import dataclass
from datetime import date
from statistics import median

METHOD_VERSION = "split-v1"
SUSPECT_FLAG = "mixed_split_level"  # quality_flag for a bar matching neither price level
MIXED_WINDOW = 45  # trading bars; Yahoo's mixing seen on PSX data spans ~35
MAX_DAILY_GAP = math.log(1.2)  # PSX circuit breakers cap a day at about +/-10%
BOUNDARY_BARS = 5
AFTER_SPLIT_BARS = 5  # the ex-date can fall a few bars from the date Yahoo lists


@dataclass(frozen=True)
class Split:
    day: date
    ratio: float


@dataclass(frozen=True)
class SplitDecision:
    day: date
    ratio: float
    history_adjusted_by_us: bool
    note: str


@dataclass
class Adjustment:
    factors: list[float]  # divisor per bar, same order as the input bars
    suspect: list[bool]
    decisions: list[SplitDecision]


def _distance(a: float, b: float) -> float:
    return abs(math.log(a / b))


def adjust(days: list[date], closes: list[float], splits: list[Split]) -> Adjustment:
    """Factors for bars sorted by date; `closes` are raw provider closes."""
    n = len(days)
    factors = [1.0] * n
    suspect = [False] * n
    decisions: list[SplitDecision] = []

    def adjusted(i: int) -> float:
        return closes[i] / factors[i]

    for split in sorted(
        (s for s in splits if s.ratio > 0 and s.ratio != 1), key=lambda s: s.day, reverse=True
    ):
        first_after = next((i for i in range(n) if days[i] >= split.day), n)
        if first_after == 0:
            continue  # the split predates the stored history
        window_start = max(0, first_after - MIXED_WINDOW)

        # 1. A series with no jump beyond a day's limit around the split was already adjusted
        # by the provider; running the nearest-bar rule there could misread an ordinary
        # move as a small split (e.g. 1.1:1)
        around = range(max(1, window_start), min(n, first_after + AFTER_SPLIT_BARS))
        if all(_distance(adjusted(i), adjusted(i - 1)) <= MAX_DAILY_GAP for i in around):
            decisions.append(
                SplitDecision(split.day, split.ratio, False, "continuous across the split")
            )
            continue

        # 2. Mixed window: nearest-bar rule against the next later accepted bar
        reference = next((adjusted(i) for i in range(first_after, n) if not suspect[i]), None)
        for i in range(first_after - 1, window_start - 1, -1):
            # factors[i] so far holds only later splits' adjustment
            if reference is None:
                reference = adjusted(i)
                continue
            if _distance(adjusted(i) / split.ratio, reference) < _distance(adjusted(i), reference):
                factors[i] *= split.ratio
            if _distance(adjusted(i), reference) > MAX_DAILY_GAP:
                suspect[i] = True
            else:
                reference = adjusted(i)

        # 3. Before the window: one decision for all earlier bars
        if window_start == 0:
            decisions.append(
                SplitDecision(split.day, split.ratio, False, "no history before the window")
            )
            continue
        inside = [adjusted(i) for i in range(window_start, first_after) if not suspect[i]][
            :BOUNDARY_BARS
        ]
        before = [adjusted(i) for i in range(max(0, window_start - BOUNDARY_BARS), window_start)]
        if not inside:
            decisions.append(
                SplitDecision(split.day, split.ratio, False, "no accepted bar in the window")
            )
            continue
        level = median(before) / median(inside)
        unadjusted = _distance(level, split.ratio) < _distance(level, 1.0)
        if unadjusted:
            for i in range(window_start):
                factors[i] *= split.ratio
        verdict = (
            "not adjusted by the provider" if unadjusted else "already adjusted by the provider"
        )
        note = f"price level before/after the window = {level:.3f} ({verdict})"
        decisions.append(SplitDecision(split.day, split.ratio, unadjusted, note))

    return Adjustment(factors, suspect, decisions)
