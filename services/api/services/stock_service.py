import datetime
import json
import logging
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core.redis import get_redis_client
from integrations.market_data import MarketDataClient
from models.stock import PricePoint, Stock

logger = logging.getLogger(__name__)

# Cache TTL: 15 minutes (Architecture.md §10)
CACHE_TTL = 15 * 60
CACHE_PREFIX = "stocks"

# Calendar days per chart period, counted back from the latest stored trading day
PERIOD_DAYS = {"1mo": 31, "3mo": 92, "6mo": 183, "1y": 366, "2y": 731, "5y": 1827}
FIFTY_TWO_WEEKS = datetime.timedelta(days=365)

# Only bars that passed the split-adjustment checks are served
SERVED = PricePoint.quality_flag.is_(None)

# Bars are stamped at midnight Pakistan time (19:00 UTC the day before), so date filters
# must use the PSX trading date, not the UTC date
PSX_TRADING_DATE = func.date(func.timezone("Asia/Karachi", PricePoint.timestamp))


class StockNotFound(Exception):
    """The ticker is not in the stock universe (the KSE-100 snapshot)."""


class PriceDataUnavailable(Exception):
    """A catalog stock has no stored prices yet: the provider refresh has not succeeded."""


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    return value


def _deserialize_row(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("timestamp"):
        row["timestamp"] = datetime.datetime.fromisoformat(row["timestamp"])
    return row


def _float(value: Any) -> float | None:
    return None if value is None else float(value)


def _adjusted(value: Any, factor: Any) -> float | None:
    return None if value is None else float(value) / float(factor)


def _point(p: PricePoint) -> dict[str, Any]:
    """A bar as served: split-adjusted (services/split_adjustment.py)."""
    return {
        "timestamp": p.timestamp,
        "open": _adjusted(p.open, p.split_factor),
        "high": _adjusted(p.high, p.split_factor),
        "low": _adjusted(p.low, p.split_factor),
        "close": _adjusted(p.close, p.split_factor),
        "volume": round((p.volume or 0) * float(p.split_factor)),
    }


class StockService:
    """
    Serves prices from `price_points`; the data provider is only used by the refresh job
    (worker.tasks.refresh_stock_prices), so pages keep working through provider outages.
    Responses are cached in Redis and invalidated when the refresh job stores new prices.
    """

    @staticmethod
    def _cache_key(kind: str, ticker: str, **params: Any) -> str:
        key = f"{CACHE_PREFIX}:{kind}:{MarketDataClient.normalize_ticker(ticker)}"
        for k, v in sorted(params.items()):
            if v:
                key += f":{k}={v}"
        return key

    @staticmethod
    def _cache_get(key: str) -> Any | None:
        try:
            cached = get_redis_client().get(key)
        except Exception as e:
            logger.warning(f"Redis cache read error for {key}: {e}")
            return None
        if cached is None:
            return None
        logger.info(f"Cache hit for {key}")
        return json.loads(cached)

    @staticmethod
    def _cache_set(key: str, payload: Any) -> None:
        try:
            get_redis_client().set(key, json.dumps(payload), ex=CACHE_TTL)
        except Exception as e:
            logger.warning(f"Redis cache write error for {key}: {e}")

    @staticmethod
    def invalidate(tickers: list[str]) -> None:
        """Drop cached quotes and histories after new prices are stored."""
        try:
            client = get_redis_client()
            for ticker in tickers:
                symbol = MarketDataClient.normalize_ticker(ticker)
                for kind in ("quote", "history"):
                    keys = list(client.scan_iter(f"{CACHE_PREFIX}:{kind}:{symbol}*"))
                    if keys:
                        client.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis cache invalidation failed: {e}")

    @staticmethod
    def _get_stock(db: Session, ticker: str) -> Stock:
        symbol = MarketDataClient.normalize_ticker(ticker)
        stock = db.query(Stock).filter(Stock.ticker == symbol).first()
        if not stock:
            raise StockNotFound(symbol)
        return stock

    @classmethod
    def get_quote(cls, db: Session, ticker: str) -> dict[str, Any]:
        """Latest stored trading day plus key statistics (PRD.md FR8)."""
        key = cls._cache_key("quote", ticker)
        cached = cls._cache_get(key)
        if cached is not None:
            return _deserialize_row(cached)

        stock = cls._get_stock(db, ticker)
        latest_two = (
            db.query(PricePoint)
            .filter(PricePoint.stock_id == stock.id, SERVED)
            .order_by(PricePoint.timestamp.desc())
            .limit(2)
            .all()
        )
        if not latest_two:
            raise PriceDataUnavailable(stock.ticker)

        latest = _point(latest_two[0])
        price = latest["close"]
        previous_close = _point(latest_two[1])["close"] if len(latest_two) > 1 else None
        change = price - previous_close if previous_close else None
        # A missing high/low on a day falls back to that day's close
        year_high, year_low = (
            db.query(
                func.max(
                    func.coalesce(PricePoint.high, PricePoint.close) / PricePoint.split_factor
                ),
                func.min(func.coalesce(PricePoint.low, PricePoint.close) / PricePoint.split_factor),
            )
            .filter(
                PricePoint.stock_id == stock.id,
                SERVED,
                PricePoint.timestamp > latest["timestamp"] - FIFTY_TWO_WEEKS,
            )
            .one()
        )

        quote = {
            "ticker": stock.ticker,
            "name": stock.name,
            "sector": stock.sector,
            "currency": "PKR",
            "price": price,
            "open": latest["open"],
            "high": latest["high"],
            "low": latest["low"],
            "previous_close": previous_close,
            "change": change,
            "change_percent": (change / previous_close * 100) if change is not None else None,
            "volume": latest["volume"],
            "timestamp": latest["timestamp"],
            "fifty_two_week_high": _float(year_high),
            "fifty_two_week_low": _float(year_low),
            "market_cap": price * stock.shares_outstanding if stock.shares_outstanding else None,
        }
        cls._cache_set(key, {k: _serialize(v) for k, v in quote.items()})
        return quote

    @classmethod
    def get_history(
        cls,
        db: Session,
        ticker: str,
        period: str = "1y",
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> list[dict[str, Any]]:
        """
        Stored daily OHLCV, split-adjusted, oldest first. Without start/end, `period` counts
        back from the latest stored trading day ("max" returns everything).
        """
        key = cls._cache_key(
            "history",
            ticker,
            period=period,
            start=start.isoformat() if start else "",
            end=end.isoformat() if end else "",
        )
        cached = cls._cache_get(key)
        if cached is not None:
            return [_deserialize_row(row) for row in cached]

        stock = cls._get_stock(db, ticker)
        latest = (
            db.query(func.max(PricePoint.timestamp))
            .filter(PricePoint.stock_id == stock.id, SERVED)
            .scalar()
        )
        if latest is None:
            raise PriceDataUnavailable(stock.ticker)

        query = db.query(PricePoint).filter(PricePoint.stock_id == stock.id, SERVED)
        if start or end:
            if start:
                query = query.filter(PSX_TRADING_DATE >= start)
            if end:
                query = query.filter(PSX_TRADING_DATE <= end)
        elif period in PERIOD_DAYS:
            since = latest - datetime.timedelta(days=PERIOD_DAYS[period])
            query = query.filter(PricePoint.timestamp > since)

        history = [_point(p) for p in query.order_by(PricePoint.timestamp).all()]
        cls._cache_set(key, [{k: _serialize(v) for k, v in row.items()} for row in history])
        return history

    @staticmethod
    def search(db: Session, q: str, limit: int = 100) -> list[Stock]:
        """Search/browse the stock universe by ticker, name or sector (PRD.md FR9)."""
        query = db.query(Stock)
        term = q.strip()
        if term:
            pattern = f"%{term}%"
            query = query.filter(
                or_(
                    Stock.ticker.ilike(pattern),
                    Stock.name.ilike(pattern),
                    Stock.sector.ilike(pattern),
                )
            )
        # Exact ticker matches first, then alphabetical
        stocks = query.order_by(Stock.ticker).limit(limit).all()
        upper = term.upper()
        return sorted(stocks, key=lambda s: (s.ticker != upper, s.ticker))
