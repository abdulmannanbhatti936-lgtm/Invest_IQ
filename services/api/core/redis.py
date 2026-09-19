import redis
from core.config import settings

# Create a connection pool for Redis
redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)

def get_redis_client() -> redis.Redis:
    """
    Get a Redis client from the connection pool.
    """
    return redis.Redis(connection_pool=redis_pool)
