import datetime
import logging
import math
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

PSX_SUFFIX = ".KA"


class MarketDataUnavailable(Exception):
    """The upstream data provider failed or timed out (not the same as 'not found')."""


def _clean(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


class MarketDataClient:
    """
    Isolated client wrapper for fetching market data (Workflow.md Step 2.2).
    Currently wraps Yahoo Finance, but can be swapped out for official PSX APIs
    later without touching calling code.
    """

    @staticmethod
    def to_provider_symbol(ticker: str) -> str:
        """
        Map an app ticker to a Yahoo Finance symbol. App tickers are bare PSX
        symbols (e.g. "SYS") and get the ".KA" suffix; anything that already has
        a suffix or is an index ("^KSE") is passed through unchanged.
        """
        symbol = ticker.upper().strip()
        if "." in symbol or symbol.startswith("^"):
            return symbol
        return symbol + PSX_SUFFIX

    @staticmethod
    def normalize_ticker(ticker: str) -> str:
        """The app-facing ticker: upper-case, PSX suffix removed."""
        symbol = ticker.upper().strip()
        if symbol.endswith(PSX_SUFFIX):
            symbol = symbol[: -len(PSX_SUFFIX)]
        return symbol

    @classmethod
    def _download(cls, ticker: str, **kwargs) -> pd.DataFrame:
        symbol = cls.to_provider_symbol(ticker)
        try:
            hist = yf.Ticker(symbol).history(**kwargs)
        except Exception as e:
            logger.error(f"Market data provider error for {symbol}: {e}")
            raise MarketDataUnavailable(str(e)) from e
        if hist is None or hist.empty:
            return pd.DataFrame()
        # Today's bar can be all-NaN before the provider fills it in
        return hist.dropna(subset=["Close"])

    @classmethod
    def get_quote(cls, ticker: str) -> dict[str, Any] | None:
        """
        Latest quote plus key statistics (PRD.md FR8). Returns None when the
        ticker has no data; raises MarketDataUnavailable on provider failure.
        """
        hist = cls._download(ticker, period="1y")
        if hist.empty:
            logger.warning(f"No price data found for {ticker}")
            return None

        latest = hist.iloc[-1]
        previous_close = _clean(hist["Close"].iloc[-2]) if len(hist) > 1 else None
        price = float(latest["Close"])
        change = price - previous_close if previous_close else None

        # `info` is slow and flaky; stats from it are optional extras
        info: dict[str, Any] = {}
        try:
            info = yf.Ticker(cls.to_provider_symbol(ticker)).info or {}
        except Exception as e:
            logger.warning(f"Could not load fundamentals for {ticker}: {e}")

        return {
            "ticker": cls.normalize_ticker(ticker),
            "name": info.get("longName") or cls.normalize_ticker(ticker),
            "sector": info.get("sector"),
            "currency": info.get("currency") or "PKR",
            "price": price,
            "open": _clean(latest.get("Open")),
            "high": _clean(latest.get("High")),
            "low": _clean(latest.get("Low")),
            "previous_close": previous_close,
            "change": change,
            "change_percent": (change / previous_close * 100) if change is not None else None,
            "volume": int(latest["Volume"]) if _clean(latest.get("Volume")) is not None else 0,
            "timestamp": hist.index[-1].to_pydatetime(),
            "fifty_two_week_high": float(hist["High"].max()),
            "fifty_two_week_low": float(hist["Low"].min()),
            "market_cap": _clean(info.get("marketCap")),
            "pe_ratio": _clean(info.get("trailingPE")),
        }

    @classmethod
    def get_history(
        cls,
        ticker: str,
        period: str = "1y",
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> list[dict[str, Any]]:
        """
        Historical daily OHLCV. Returns [] when there is no data; raises
        MarketDataUnavailable on provider failure.
        """
        kwargs: dict[str, Any] = {}
        if start:
            kwargs["start"] = start.strftime("%Y-%m-%d")
        if end:
            kwargs["end"] = end.strftime("%Y-%m-%d")
        if not start and not end:
            kwargs["period"] = period

        hist = cls._download(ticker, **kwargs)
        return [
            {
                "timestamp": index.to_pydatetime(),
                "open": _clean(row["Open"]),
                "high": _clean(row["High"]),
                "low": _clean(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]) if _clean(row["Volume"]) is not None else 0,
            }
            for index, row in hist.iterrows()
        ]
