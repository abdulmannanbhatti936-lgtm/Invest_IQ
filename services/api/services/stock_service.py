import json
import logging
from typing import Dict, Any, List, Optional
import datetime
from core.redis import get_redis_client
from integrations.market_data import MarketDataClient

logger = logging.getLogger(__name__)

# Default cache TTL: 15 minutes
CACHE_TTL = 15 * 60

class StockService:
    @staticmethod
    def _generate_cache_key(prefix: str, ticker: str, **kwargs) -> str:
        key = f"{prefix}:{ticker.upper()}"
        if kwargs:
            for k, v in sorted(kwargs.items()):
                if v:
                    key += f":{k}={v}"
        return key

    @classmethod
    def get_quote_cached(cls, ticker: str) -> Optional[Dict[str, Any]]:
        redis_client = get_redis_client()
        cache_key = cls._generate_cache_key("quote", ticker)
        
        # Check cache
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Cache hit for {cache_key}")
                data = json.loads(cached_data)
                if 'timestamp' in data and data['timestamp']:
                    data['timestamp'] = datetime.datetime.fromisoformat(data['timestamp'])
                return data
        except Exception as e:
            logger.warning(f"Redis cache read error for {cache_key}: {e}")

        # Fetch from source
        logger.info(f"Cache miss for {cache_key}. Fetching from source.")
        quote = MarketDataClient.get_quote(ticker)
        
        # Cache the result
        if quote:
            try:
                # Convert datetime to ISO string for JSON serialization
                cache_payload = quote.copy()
                if 'timestamp' in cache_payload and isinstance(cache_payload['timestamp'], datetime.datetime):
                    cache_payload['timestamp'] = cache_payload['timestamp'].isoformat()
                
                redis_client.setex(cache_key, CACHE_TTL, json.dumps(cache_payload))
            except Exception as e:
                logger.warning(f"Redis cache write error for {cache_key}: {e}")
                
        return quote

    @classmethod
    def get_history_cached(
        cls, 
        ticker: str, 
        period: str = "1y", 
        start: Optional[datetime.date] = None, 
        end: Optional[datetime.date] = None
    ) -> List[Dict[str, Any]]:
        redis_client = get_redis_client()
        
        # Handle start/end formatting for cache key
        start_str = start.strftime("%Y-%m-%d") if start else ""
        end_str = end.strftime("%Y-%m-%d") if end else ""
        
        cache_key = cls._generate_cache_key("history", ticker, period=period, start=start_str, end=end_str)
        
        # Check cache
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Cache hit for {cache_key}")
                data_list = json.loads(cached_data)
                # Parse timestamps back to datetime
                for item in data_list:
                    if 'timestamp' in item and item['timestamp']:
                        item['timestamp'] = datetime.datetime.fromisoformat(item['timestamp'])
                return data_list
        except Exception as e:
            logger.warning(f"Redis cache read error for {cache_key}: {e}")

        # Fetch from source
        logger.info(f"Cache miss for {cache_key}. Fetching from source.")
        history = MarketDataClient.get_history(ticker, period=period, start=start, end=end)
        
        # Cache the result
        if history:
            try:
                # Convert datetime to ISO string for JSON serialization
                cache_payload = []
                for row in history:
                    cache_row = row.copy()
                    if 'timestamp' in cache_row and isinstance(cache_row['timestamp'], datetime.datetime):
                        cache_row['timestamp'] = cache_row['timestamp'].isoformat()
                    cache_payload.append(cache_row)
                    
                redis_client.setex(cache_key, CACHE_TTL, json.dumps(cache_payload))
            except Exception as e:
                logger.warning(f"Redis cache write error for {cache_key}: {e}")
                
        return history
