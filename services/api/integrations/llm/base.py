"""
What every LLM provider adapter shares: the call shape, the errors, and the HTTP policy
(Architecture.md §6.4; numbers decided 2026-10-13).

- Timeouts: 5 s to connect, 25 s to read.
- One retry on a timeout, a 5xx or a 429, after the provider's Retry-After (at most 5 s) or 2 s,
  and only if the caller's deadline leaves room for it.
- At most one provider call per second across the whole app (free-tier limits), through a
  Redis slot; if Redis is down the slot is skipped with a warning, like the auth limiter.
- Every 429 is logged and counted per day in Redis (`chat:provider_429:<date>`), because the
  free tier's exact limits are not published (Memory.md §4).
- A 429, a 5xx or a timeout may fail over to the backup provider (`LLMUnavailable.failover`);
  a refused request (bad key, bad request) or an unusable reply may not. When a backup exists
  the primary is not retried, so the backup still has time inside the deadline.
"""

import datetime
import logging
import time
from dataclasses import dataclass

import httpx

from core.redis import get_redis_client

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 25.0
MAX_RETRY_AFTER_S = 5.0
DEFAULT_RETRY_WAIT_S = 2.0
SLOT_KEY = "chat:provider_slot"
SLOT_MS = 1000


@dataclass(frozen=True)
class Turn:
    role: str  # "user" or "assistant"
    content: str


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    # The reply stopped because it reached the token limit, so it may be cut off mid-sentence
    truncated: bool = False


class LLMUnavailable(Exception):
    """The provider gave no usable reply."""

    reason = "provider_error"

    def __init__(self, message: str, failover: bool = False):
        super().__init__(message)
        self.failover = failover


class LLMRateLimited(LLMUnavailable):
    """The provider kept answering 429 (rate limited)."""

    reason = "provider_busy"

    def __init__(self, retry_after: float | None):
        super().__init__("provider rate limit", failover=True)
        self.retry_after = retry_after


# The last rate-limit headers each provider sent (Groq's x-ratelimit-*), read by the evaluation
# to wait for a token reset instead of hitting 429
RATE_LIMIT_HEADERS: dict[str, dict[str, str]] = {}


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return float(response.headers.get("retry-after", ""))
    except ValueError:
        return None


def _count_429() -> None:
    day = datetime.date.today().isoformat()
    try:
        client = get_redis_client()
        key = f"chat:provider_429:{day}"
        client.incr(key)
        client.expire(key, 8 * 24 * 3600)
    except Exception as e:
        logger.warning("Could not count a provider 429 (Redis unavailable: %s)", type(e).__name__)


def _wait_for_slot(deadline: float) -> None:
    """Holds the call until the app-wide one-call-per-second slot is free."""
    try:
        client = get_redis_client()
        while not client.set(SLOT_KEY, "1", nx=True, px=SLOT_MS):
            if time.monotonic() + 0.1 > deadline:
                return
            time.sleep(0.1)
    except Exception as e:
        logger.warning("Provider call slot SKIPPED (Redis unavailable: %s)", type(e).__name__)


def post_json(
    url: str, headers: dict, body: dict, deadline: float, provider: str, retry: bool = True
) -> dict:
    """POST with the shared timeouts, retry, call slot and 429 accounting; returns the JSON."""
    last: LLMUnavailable = LLMUnavailable("no attempt made", failover=True)
    for attempt in (1, 2) if retry else (1,):
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            break
        _wait_for_slot(deadline)
        timeout = httpx.Timeout(
            min(READ_TIMEOUT_S, remaining), connect=min(CONNECT_TIMEOUT_S, remaining)
        )
        wait = DEFAULT_RETRY_WAIT_S
        try:
            response = httpx.post(url, headers=headers, json=body, timeout=timeout)
        except httpx.HTTPError as e:
            logger.warning("%s call failed (attempt %d): %s", provider, attempt, type(e).__name__)
            last = LLMUnavailable(type(e).__name__, failover=True)
        else:
            RATE_LIMIT_HEADERS[provider] = {
                k: v
                for k, v in response.headers.items()
                if k.startswith("x-ratelimit-") or k == "retry-after"
            }
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:
                _count_429()
                retry_after = _retry_after(response)
                logger.warning("%s answered 429 (attempt %d)", provider, attempt)
                last = LLMRateLimited(retry_after)
                wait = min(retry_after, MAX_RETRY_AFTER_S) if retry_after else wait
            elif response.status_code >= 500:
                logger.warning(
                    "%s answered %d (attempt %d)", provider, response.status_code, attempt
                )
                last = LLMUnavailable(f"HTTP {response.status_code}", failover=True)
            else:
                # 4xx other than 429: a bad key or request; retrying cannot help
                logger.error("%s refused the request: HTTP %d", provider, response.status_code)
                raise LLMUnavailable(f"HTTP {response.status_code}")
        if retry and attempt == 1 and time.monotonic() + wait + 1 < deadline:
            time.sleep(wait)
        else:
            break
    raise last


class Provider:
    name: str

    def complete(
        self,
        system: str,
        turns: list[Turn],
        *,
        max_tokens: int,
        temperature: float,
        deadline: float,
        retry: bool = True,
    ) -> LLMResult:
        raise NotImplementedError
