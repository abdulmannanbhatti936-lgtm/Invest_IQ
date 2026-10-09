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
