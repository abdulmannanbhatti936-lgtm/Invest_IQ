"""
Feature engineering (Workflow.md Step 3.2, PRD.md FR13).

RSI, MACD, Bollinger Bands and SMA are hand-written in pandas with TA-Lib's exact
definitions, including how TA-Lib seeds its smoothing (see `_seeded_ewm`). TA-Lib itself
needs a native C library that is painful to install on Windows and in CI, so it is not a
dependency; instead `tests/test_indicators.py` checks our output against reference values
produced by TA-Lib 0.8.1 and against the published Wilder/StockCharts RSI example.

Every feature uses trailing windows only (value at day t depends on days <= t), and model
inputs are scale-free (returns and ratios), so the backward dividend adjustment, which
rescales whole stretches of history, cannot leak a future price level into a feature.

The module is generic over an optional `sentiment_score` column so Phase 4 can
merge sentiment in without restructuring (Workflow.md Step 4.6).
"""

from collections.abc import Iterable

import numpy as np
import pandas as pd

# Raw indicator columns (price-scale), shown for transparency / charts
INDICATOR_COLUMNS = [
    "RSI_14",
    "MACD",
    "MACD_signal",
    "MACD_hist",
    "SMA_20",
    "SMA_50",
    "BB_upper",
    "BB_mid",
    "BB_lower",
]

# Scale-free model inputs, so a model is not just memorising a price level
FEATURE_COLUMNS = [
    "return_1d",
    "return_5d",
    "return_20d",
    "volatility_20d",
    "rsi_14",
    "macd_norm",
    "macd_signal_norm",
    "macd_hist_norm",
    "close_to_sma20",
    "close_to_sma50",
    "sma20_to_sma50",
    "bb_position",
    "bb_width",
    "volume_ratio_20d",
    "range_pct",
]

# Next-day return thresholds for the buy/sell/hold label
SIGNAL_THRESHOLD = 0.01
SIGNAL_LABELS = {1: "BUY", 0: "HOLD", -1: "SELL"}
CLASS_ORDER = [-1, 0, 1]  # SELL, HOLD, BUY: column order of probabilities and the confusion matrix

# Rows needed before every indicator is defined (SMA_50 is the longest window)
WARMUP_ROWS = 50


def price_points_to_frame(price_points: Iterable) -> pd.DataFrame:
    """Convert ORM PricePoint rows (or dicts) to a date-indexed OHLCV frame."""
    rows = []
    for p in price_points:
        get = p.get if isinstance(p, dict) else lambda k, p=p: getattr(p, k)
        rows.append(
            {
                "date": pd.Timestamp(get("timestamp")),
                "open": get("open"),
                "high": get("high"),
                "low": get("low"),
                "close": get("close"),
                "volume": get("volume"),
            }
        )
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    return normalize_ohlcv(df)


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by date, coerce numeric types, drop rows without a close, de-duplicate days."""
    if df.empty:
        return df
    df = df.copy()
    dates = pd.to_datetime(df["date"], utc=True)
    df["date"] = dates.dt.tz_convert("Asia/Karachi").dt.tz_localize(None).dt.normalize()
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    df = df.dropna(subset=["close"])
    df["volume"] = df["volume"].fillna(0.0)
    for col in ["open", "high", "low"]:
        df[col] = df[col].fillna(df["close"])
    df = df.drop_duplicates(subset="date", keep="last").sort_values("date")
    return df.reset_index(drop=True)


def _seeded_ewm(values: pd.Series, length: int, alpha: float, seed_end: int | None = None):
    """
    Exponential smoothing seeded the way TA-Lib does it: the first output (at position
    `seed_end`, by default the `length`-th valid value) is the simple mean of the `length`
    values ending there, and each later output is alpha * value + (1 - alpha) * previous.
    """
    out = pd.Series(np.nan, index=values.index, dtype=float)
    first = values.first_valid_index()
    if first is None:
        return out
    start = values.index.get_loc(first)
    seed_end = start + length - 1 if seed_end is None else seed_end
    if seed_end >= len(values):
        return out
    seeded = values.astype(float).copy()
    seeded.iloc[:seed_end] = np.nan
    seeded.iloc[seed_end] = values.iloc[seed_end - length + 1 : seed_end + 1].mean()
    return seeded.ewm(alpha=alpha, adjust=False).mean()


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """Wilder's RSI: averages seeded with the mean of the first `length` changes (TA-Lib)."""
    delta = close.diff()
    avg_gain = _seeded_ewm(delta.clip(lower=0.0), length, 1 / length)
    avg_loss = _seeded_ewm(-delta.clip(upper=0.0), length, 1 / length)
    out = 100 * avg_gain / (avg_gain + avg_loss)
    # The one deliberate difference from TA-Lib: a flat window (no gains, no losses) reads as
    # neutral 50 here. TA-Lib returns 0, which would make an untraded stock look oversold.
    return out.where((avg_gain + avg_loss) != 0, 50.0).where(avg_gain.notna())


def ema(values: pd.Series, length: int, seed_end: int | None = None) -> pd.Series:
    return _seeded_ewm(values, length, 2 / (length + 1), seed_end)


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    MACD as TA-Lib computes it: both EMAs are seeded on the slow EMA's first bar, so the
    fast EMA's seed is the mean of the `fast` closes ending there, not of the first ones.
    """
    first = close.first_valid_index()
    seed_end = (close.index.get_loc(first) if first is not None else 0) + slow - 1
    line = ema(close, fast, seed_end) - ema(close, slow, seed_end)
    signal_line = ema(line, signal)
    return line, signal_line, line - signal_line


def sma(close: pd.Series, length: int) -> pd.Series:
    return close.rolling(length).mean()


def bollinger(
    close: pd.Series, length: int = 20, std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """SMA middle band +/- `std` population standard deviations (TA-Lib BBANDS, MA type 0)."""
    mid = sma(close, length)
    dev = close.rolling(length).std(ddof=0)
    return mid + std * dev, mid, mid - std * dev


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add raw indicators and scale-free model features. Never drops rows."""
    df = df.copy()
    close = df["close"]

    df["RSI_14"] = rsi(close, 14)
    df["MACD"], df["MACD_signal"], df["MACD_hist"] = macd(close)
    df["SMA_20"] = sma(close, 20)
    df["SMA_50"] = sma(close, 50)
    df["BB_upper"], df["BB_mid"], df["BB_lower"] = bollinger(close)

    daily_ret = close.pct_change()
    df["return_1d"] = daily_ret
    df["return_5d"] = close.pct_change(5)
    df["return_20d"] = close.pct_change(20)
    df["volatility_20d"] = daily_ret.rolling(20).std()
    df["rsi_14"] = df["RSI_14"] / 100.0
    df["macd_norm"] = df["MACD"] / close
    df["macd_signal_norm"] = df["MACD_signal"] / close
    df["macd_hist_norm"] = df["MACD_hist"] / close
    df["close_to_sma20"] = close / df["SMA_20"] - 1
    df["close_to_sma50"] = close / df["SMA_50"] - 1
    df["sma20_to_sma50"] = df["SMA_20"] / df["SMA_50"] - 1
    band = df["BB_upper"] - df["BB_lower"]
    df["bb_position"] = ((close - df["BB_lower"]) / band.replace(0, np.nan)).fillna(0.5)
    df["bb_width"] = band / df["BB_mid"]
    vol_avg = df["volume"].rolling(20).mean().replace(0, np.nan)
    df["volume_ratio_20d"] = (df["volume"] / vol_avg).fillna(1.0)
    df["range_pct"] = (df["high"] - df["low"]) / close
    return df


def add_sentiment_feature(df: pd.DataFrame, sentiments: Iterable | None) -> pd.DataFrame:
    """
    Merge a daily mean sentiment score (missing days = 0.0 neutral).
    Unscored headlines (sentiment_score is None) are ignored.
    """
    df = df.copy()
    rows = [
        {"date": pd.Timestamp(s.timestamp).normalize(), "score": float(s.sentiment_score)}
        for s in (sentiments or [])
        if s.sentiment_score is not None and s.timestamp is not None
    ]
    if not rows:
        df["sentiment_score"] = 0.0
        return df
    daily = pd.DataFrame(rows).groupby("date")["score"].mean()
    df["sentiment_score"] = df["date"].map(daily).fillna(0.0).astype(float)
    return df


def add_targets(df: pd.DataFrame, threshold: float = SIGNAL_THRESHOLD) -> pd.DataFrame:
    """
    Targets for row t describe day t -> t+1. The last row has no target (NaN);
    it is the row we predict for at inference time, so it is never dropped here.
    """
    df = df.copy()
    df["next_close"] = df["close"].shift(-1)
    df["target_return"] = df["next_close"] / df["close"] - 1
    signal = np.where(
        df["target_return"] > threshold, 1, np.where(df["target_return"] < -threshold, -1, 0)
    )
    df["target_signal"] = pd.Series(signal, index=df.index).where(df["target_return"].notna())
    return df


def build_feature_frame(df: pd.DataFrame, sentiments: Iterable | None = None) -> pd.DataFrame:
    """
    OHLCV frame -> features + targets, with only the indicator warm-up rows removed.
    The most recent row is always kept (its targets are NaN).
    """
    df = normalize_ohlcv(df)
    if df.empty:
        return df
    df = add_technical_indicators(df)
    df = add_sentiment_feature(df, sentiments)
    df = add_targets(df)
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)
    return df


def training_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Rows usable for supervised training (those with a known next-day outcome)."""
    return df.dropna(subset=["target_return"]).reset_index(drop=True)
