"""
Feature engineering (Workflow.md Step 3.2, PRD.md FR13).

Indicators are the standard TA-Lib definitions (RSI, MACD, Bollinger Bands,
SMA), implemented directly in pandas. TA-Lib needs a native C build that is
painful on Windows/CI, and pandas-ta is unmaintained and breaks on numpy 2;
the formulas below are the textbook ones and are unit-tested.

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


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """Wilder's RSI (same smoothing as TA-Lib)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    rs = avg_gain / avg_loss
    out = 100 - 100 / (1 + rs)
    # No losses in the window -> RSI 100; flat window -> 50
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)
    return out.where(avg_gain.notna())


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    line = ema_fast - ema_slow
    signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return line, signal_line, line - signal_line


def bollinger(
    close: pd.Series, length: int = 20, std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = close.rolling(length).mean()
    dev = close.rolling(length).std(ddof=0)
    return mid + std * dev, mid, mid - std * dev


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add raw indicators and scale-free model features. Never drops rows."""
    df = df.copy()
    close = df["close"]

    df["RSI_14"] = rsi(close, 14)
    df["MACD"], df["MACD_signal"], df["MACD_hist"] = macd(close)
    df["SMA_20"] = close.rolling(20).mean()
    df["SMA_50"] = close.rolling(50).mean()
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
