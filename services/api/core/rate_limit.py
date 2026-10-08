import logging

from fastapi import HTTPException, Request, status

from core.config import settings
from core.redis import get_redis_client

logger = logging.getLogger(__name__)


def auth_rate_limit(request: Request) -> None:
    """
    Fixed-window rate limit per client IP and endpoint, backed by Redis
    (Architecture.md §11: rate limiting on auth endpoints).
    Fails open if Redis is unavailable so auth keeps working.
    """
    client_ip = request.client.host if request.client else "unknown"
    key = f"ratelimit:{request.url.path}:{client_ip}"
    try:
        redis_client = get_redis_client()
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, settings.AUTH_RATE_LIMIT_WINDOW_SECONDS)
    except Exception as e:
        logger.warning(f"Rate limiter unavailable, allowing request: {e}")
        return

    if count > settings.AUTH_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait a minute and try again.",
        )
