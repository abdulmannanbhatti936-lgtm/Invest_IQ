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
        # Deliberate fail-open (Memory.md §11): auth stays available, but the skip is visible
        logger.warning(
            "Auth rate limit SKIPPED for %s (Redis unavailable: %s)",
            request.url.path,
            type(e).__name__,
        )
        return

    if count > settings.AUTH_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait a minute and try again.",
        )


def user_rate_limit(scope: str, user_id, limit: int, window: int) -> int | None:
    """
    Fixed-window limit per signed-in user and scope; returns the seconds to wait when the
    limit is exceeded. Fails open like the auth limiter when Redis is unavailable.
    """
    key = f"ratelimit:user:{scope}:{user_id}"
    try:
        redis_client = get_redis_client()
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, window)
        if count <= limit:
            return None
        ttl = redis_client.ttl(key)
    except Exception as e:
        logger.warning("Rate limit SKIPPED for %s (Redis unavailable: %s)", scope, type(e).__name__)
        return None
    return ttl if ttl and ttl > 0 else window
