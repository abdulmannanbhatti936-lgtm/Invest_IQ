import redis

from core.config import settings

# Short timeouts so a missing/down Redis degrades gracefully instead of hanging requests
redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)


def get_redis_client() -> redis.Redis:
    """
    Get a Redis client from the connection pool.
    """
    return redis.Redis(connection_pool=redis_pool)
