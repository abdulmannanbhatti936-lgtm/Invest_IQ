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
    Isolated client for the market data provider (Workflow.md Step 2.2). Only the refresh
    job calls it: the API serves prices from the database (Memory.md §3), so a provider
    outage or rate limit never breaks a page. Wraps Yahoo Finance today; the PSX portal can
    replace it without touching calling code.
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
            # auto_adjust=False: "Close" is split-adjusted but not dividend-adjusted, so stored
            # prices match the prices PSX quotes for the same day
            hist = yf.Ticker(symbol).history(auto_adjust=False, **kwargs)
        except Exception as e:
            logger.error(f"Market data provider error for {symbol}: {e}")
            raise MarketDataUnavailable(str(e)) from e
        if hist is None or hist.empty:
            return pd.DataFrame()
        # Today's bar can be all-NaN before the provider fills it in
        return hist.dropna(subset=["Close"])

    @classmethod
    def get_shares_outstanding(cls, ticker: str) -> int | None:
        """
        Shares outstanding, used to compute market cap from our stored close. Yahoo's own
        marketCap and trailingPE for PSX symbols disagree with PSX by 2-4x, so they are not used.
        """
        symbol = cls.to_provider_symbol(ticker)
        try:
            info = yf.Ticker(symbol).info or {}
        except Exception as e:
            logger.error(f"Market data provider error for {symbol}: {e}")
            raise MarketDataUnavailable(str(e)) from e
        shares = _clean(info.get("sharesOutstanding"))
        return int(shares) if shares else None

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
