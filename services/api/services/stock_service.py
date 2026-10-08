import datetime
import json
import logging
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.redis import get_redis_client
from integrations.market_data import MarketDataClient
from models.stock import Stock

logger = logging.getLogger(__name__)

# Cache TTL: 15 minutes (Architecture.md §10)
CACHE_TTL = 15 * 60


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    return value


def _deserialize_row(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("timestamp"):
        row["timestamp"] = datetime.datetime.fromisoformat(row["timestamp"])
    return row


class StockService:
    @staticmethod
    def _generate_cache_key(prefix: str, ticker: str, **kwargs) -> str:
        key = f"{prefix}:{MarketDataClient.normalize_ticker(ticker)}"
        for k, v in sorted(kwargs.items()):
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

    @classmethod
    def get_quote_cached(cls, db: Session, ticker: str) -> dict[str, Any] | None:
        cache_key = cls._generate_cache_key("quote", ticker)
        cached = cls._cache_get(cache_key)
        if cached is not None:
            return _deserialize_row(cached)

        logger.info(f"Cache miss for {cache_key}. Fetching from source.")
        quote = MarketDataClient.get_quote(ticker)
        if not quote:
            return None

        # Our catalog has cleaner PSX names/sectors than the provider
        stock = db.query(Stock).filter(Stock.ticker == quote["ticker"]).first()
        if stock:
            quote["name"] = stock.name
            quote["sector"] = stock.sector or quote["sector"]

        cls._cache_set(cache_key, {k: _serialize(v) for k, v in quote.items()})
        return quote

    @classmethod
    def get_history_cached(
        cls,
        ticker: str,
        period: str = "1y",
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> list[dict[str, Any]]:
        cache_key = cls._generate_cache_key(
            "history",
            ticker,
            period=period,
            start=start.isoformat() if start else "",
            end=end.isoformat() if end else "",
        )
        cached = cls._cache_get(cache_key)
        if cached is not None:
            return [_deserialize_row(row) for row in cached]

        logger.info(f"Cache miss for {cache_key}. Fetching from source.")
        history = MarketDataClient.get_history(ticker, period=period, start=start, end=end)
        if history:
            cls._cache_set(
                cache_key, [{k: _serialize(v) for k, v in row.items()} for row in history]
            )
        return history

    @staticmethod
    def search(db: Session, q: str, limit: int = 50) -> list[Stock]:
        """Search/browse the PSX catalog by ticker, name or sector (PRD.md FR9)."""
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
