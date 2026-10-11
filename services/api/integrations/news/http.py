"""
Polite HTTP for the news scrapers (decided 2026-10-11, Memory.md §3): an identifying user
agent, robots.txt checked before every fetch and every redirect target, at most one request
per MIN_INTERVAL seconds per site, and retries with exponential backoff on network errors,
429 and 5xx, waiting at least as long as the site's Retry-After asks.
None of the sites has granted permission for automated use, so these limits are not tuning
knobs: keep them.
"""

import datetime
import logging
import time
import urllib.robotparser
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit

import requests

logger = logging.getLogger(__name__)

USER_AGENT = "InvestIQ-FYP/1.0 (+https://github.com/abdulmannanbhatti936-lgtm/Invest_IQ)"
MIN_INTERVAL = 3.0
RETRIES = 3
BACKOFF_SECONDS = 2.0
TIMEOUT_SECONDS = 25
ROBOTS_TTL_SECONDS = 24 * 3600
# A site asking us to wait longer than this is treated as unavailable for this run, rather
# than holding the job open; it is asked again on the next scheduled run
MAX_RETRY_AFTER_SECONDS = 300
MAX_REDIRECTS = 5


class NewsSourceUnavailable(Exception):
    """A news site could not be reached or kept failing after the retries."""


class FetchNotAllowed(Exception):
    """robots.txt disallows the URL for our user agent; it is never fetched."""


class PageNotFound(Exception):
    """The site answered with a 4xx for this one page (e.g. a deleted article)."""


class PoliteFetcher:
    def __init__(
        self,
        session: requests.Session | None = None,
        min_interval: float = MIN_INTERVAL,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.min_interval = min_interval
        self._sleep = sleep
        self._clock = clock
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, tuple[float, urllib.robotparser.RobotFileParser]] = {}

    def _throttle(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            wait = self.min_interval - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_request[host] = self._clock()

    def _request(self, url: str, params: dict | None = None) -> requests.Response:
        """One GET with retries; redirects are returned, not followed (see `get`)."""
        host = urlsplit(url).netloc
        for attempt in range(RETRIES + 1):
            self._throttle(host)
            retry_after = None
            try:
                response = self.session.get(
                    url, params=params, timeout=TIMEOUT_SECONDS, allow_redirects=False
                )
            except requests.RequestException as e:
                error = str(e)
            else:
                if response.status_code != 429 and response.status_code < 500:
                    return response
                error = f"HTTP {response.status_code}"
                retry_after = retry_after_seconds(response.headers.get("Retry-After"))
            if retry_after is not None and retry_after > MAX_RETRY_AFTER_SECONDS:
                raise NewsSourceUnavailable(f"{url}: {error}, asked to wait {retry_after:.0f} s")
            if attempt < RETRIES:
                delay = max(BACKOFF_SECONDS * 2**attempt, retry_after or 0.0)
                logger.warning(f"{url}: {error}; retrying in {delay:.0f} s")
                self._sleep(delay)
        raise NewsSourceUnavailable(f"{url}: {error} after {RETRIES} retries")

    def _robot_rules(self, url: str) -> urllib.robotparser.RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        cached = self._robots.get(origin)
        if cached and self._clock() - cached[0] < ROBOTS_TTL_SECONDS:
            return cached[1]
        rules = urllib.robotparser.RobotFileParser()
        response = self._follow(f"{origin}/robots.txt", None, check_robots=False)
        if response.status_code >= 400:
            # RFC 9309: an unavailable (4xx) robots.txt means no restrictions
            rules.parse([])
        else:
            rules.parse(response.text.splitlines())
        self._robots[origin] = (self._clock(), rules)
        return rules

    def _follow(self, url: str, params: dict | None, check_robots: bool) -> requests.Response:
        """GET, following redirects one hop at a time so each target can be checked."""
        for _ in range(MAX_REDIRECTS + 1):
            if check_robots and not self._robot_rules(url).can_fetch(USER_AGENT, url):
                raise FetchNotAllowed(f"robots.txt disallows {url}")
            response = self._request(url, params)
            location = response.headers.get("Location")
            if not response.is_redirect or not location:
                return response
            url, params = urljoin(response.url or url, location), None
        raise NewsSourceUnavailable(f"{url}: more than {MAX_REDIRECTS} redirects")

    def get(self, url: str, params: dict | None = None) -> requests.Response:
        """
        GET a URL that robots.txt allows, and only through redirect targets it also allows;
        raises on a disallowed URL or a failing site.
        """
        response = self._follow(url, params, check_robots=True)
        if response.status_code >= 400:
            raise PageNotFound(f"{url}: HTTP {response.status_code}")
        return response


def retry_after_seconds(value: str | None) -> float | None:
    """A Retry-After header (seconds or an HTTP date) in seconds from now; None if absent."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return max(0.0, (when - datetime.datetime.now(datetime.timezone.utc)).total_seconds())
