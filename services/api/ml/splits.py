"""Strictly chronological train/validation/test split (Workflow.md Step 3.3)."""

from typing import NamedTuple

import pandas as pd


class ChronoSplit(NamedTuple):
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame


def split_boundaries(
    n_rows: int, train_frac: float = 0.70, val_frac: float = 0.15
) -> tuple[int, int]:
    """Index where validation starts and where test starts."""
    if not 0 < train_frac < 1 or not 0 <= val_frac < 1 or train_frac + val_frac >= 1:
        raise ValueError("Fractions must satisfy 0 < train, 0 <= val, train + val < 1")
    train_end = int(n_rows * train_frac)
    val_end = int(n_rows * (train_frac + val_frac))
    return train_end, val_end


def chronological_split(
    df: pd.DataFrame,
    date_col: str = "date",
    train_frac: float = 0.70,
    val_frac: float = 0.15,
) -> ChronoSplit:
    """
    Split by date order, never shuffled: every validation date is after every
    training date, and every test date is after every validation date.
    """
    ordered = df.sort_values(date_col, kind="stable").reset_index(drop=True)
    train_end, val_end = split_boundaries(len(ordered), train_frac, val_frac)
    return ChronoSplit(
        train=ordered.iloc[:train_end].reset_index(drop=True),
        val=ordered.iloc[train_end:val_end].reset_index(drop=True),
        test=ordered.iloc[val_end:].reset_index(drop=True),
    )


class CutDates(NamedTuple):
    """Period boundaries shared by every ticker: train < val_start <= val < test_start."""

    val_start: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp  # last test date, inclusive


def _calendar(dates) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.unique(pd.DatetimeIndex(dates))).sort_values()


def shared_cut_dates(dates, train_frac: float = 0.70, val_frac: float = 0.15) -> CutDates:
    """
    One set of cut dates for all tickers, taken from the union of their trading dates, so
    every ticker's test period covers the same stretch of the market.
    """
    calendar = _calendar(dates)
    train_end, val_end = split_boundaries(len(calendar), train_frac, val_frac)
    return CutDates(calendar[train_end], calendar[val_end], calendar[-1])


def walk_forward_folds(dates, n_folds: int = 3, test_frac: float = 0.30) -> list[CutDates]:
    """
    Expanding-window folds over the last `test_frac` of the calendar: fold k tests on block
    k, validates on the equally long block just before it and trains on everything earlier.
    """
    calendar = _calendar(dates)
    first_test = int(len(calendar) * (1 - test_frac))
    block = (len(calendar) - first_test) // n_folds
    if block < 1 or first_test - block < 1:
        raise ValueError("Not enough dates for the requested folds")
    folds = []
    for k in range(n_folds):
        start = first_test + k * block
        end = len(calendar) - 1 if k == n_folds - 1 else start + block - 1
        folds.append(CutDates(calendar[start - block], calendar[start], calendar[end]))
    return folds


def assign_periods(dates: pd.Series, cuts: CutDates) -> pd.Series:
    """
    'train' / 'val' / 'test' (or None) for one ticker's rows, in date order. A row's label is
    the next day's close, so the last row of a period would be labelled with a price from the
    next period; that row is purged (None) so no label crosses a boundary.
    """
    period = pd.Series(None, index=dates.index, dtype=object)
    period[dates < cuts.val_start] = "train"
    period[(dates >= cuts.val_start) & (dates < cuts.test_start)] = "val"
    period[(dates >= cuts.test_start) & (dates <= cuts.test_end)] = "test"
    crosses = period.ne(period.shift(-1)) & period.isin(["train", "val"])
    period[crosses] = None
    return period
