"""Polite fetching rules for the news scrapers (Workflow.md Step 4.2, Memory.md §3)."""

import pytest
import requests

from integrations.news.http import (
    BACKOFF_SECONDS,
    MIN_INTERVAL,
    RETRIES,
    USER_AGENT,
    FetchNotAllowed,
    NewsSourceUnavailable,
    PageNotFound,
    PoliteFetcher,
)

ROBOTS = "User-agent: *\nDisallow: /search\n"


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class FakeSession:
    """Answers from a {url: [responses or exceptions]} script and records every call."""

    def __init__(self, script):
        self.script = {url: list(answers) for url, answers in script.items()}
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        answer = self.script[url].pop(0) if len(self.script[url]) > 1 else self.script[url][0]
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def __call__(self):
        return self.now


def _fetcher(script):
    session = FakeSession(script)
    clock = FakeClock()
    return PoliteFetcher(session=session, sleep=clock.sleep, clock=clock), session, clock


def test_identifies_itself_with_the_project_user_agent():
    fetcher, session, _ = _fetcher({})
    assert session.headers["User-Agent"] == USER_AGENT
    assert "InvestIQ" in USER_AGENT and "github.com" in USER_AGENT


def test_robots_disallowed_url_is_never_requested():
    fetcher, session, _ = _fetcher({"https://news.example/robots.txt": [FakeResponse(text=ROBOTS)]})
    with pytest.raises(FetchNotAllowed):
        fetcher.get("https://news.example/search?q=ogdc")
    assert session.calls == ["https://news.example/robots.txt"]


def test_missing_robots_txt_allows_everything():
    fetcher, _, _ = _fetcher(
        {
            "https://news.example/robots.txt": [FakeResponse(404)],
            "https://news.example/a": [FakeResponse(text="ok")],
        }
    )
    assert fetcher.get("https://news.example/a").text == "ok"


def test_waits_between_requests_to_the_same_site():
    fetcher, session, clock = _fetcher(
        {
            "https://news.example/robots.txt": [FakeResponse(text=ROBOTS)],
            "https://news.example/a": [FakeResponse()],
            "https://news.example/b": [FakeResponse()],
        }
    )
    fetcher.get("https://news.example/a")
    fetcher.get("https://news.example/b")
    # robots.txt, /a and /b: two gaps, each a full MIN_INTERVAL
    assert clock.sleeps == [MIN_INTERVAL, MIN_INTERVAL]
    # robots.txt is read once and reused
    assert session.calls.count("https://news.example/robots.txt") == 1


def test_retries_server_errors_with_growing_backoff():
    fetcher, session, clock = _fetcher(
        {
            "https://news.example/robots.txt": [FakeResponse(text=ROBOTS)],
            "https://news.example/a": [
                FakeResponse(503),
                requests.ConnectionError("reset"),
                FakeResponse(text="ok"),
            ],
        }
    )
    assert fetcher.get("https://news.example/a").text == "ok"
    backoffs = [s for s in clock.sleeps if s >= BACKOFF_SECONDS and s != MIN_INTERVAL]
    assert backoffs == [BACKOFF_SECONDS, BACKOFF_SECONDS * 2]
    # A backoff counts toward the gap: requests are still never closer than MIN_INTERVAL
    assert clock.now >= MIN_INTERVAL * 3


def test_gives_up_after_the_retries():
    fetcher, session, _ = _fetcher(
        {
            "https://news.example/robots.txt": [FakeResponse(text=ROBOTS)],
            "https://news.example/a": [FakeResponse(429)],
        }
    )
    with pytest.raises(NewsSourceUnavailable):
        fetcher.get("https://news.example/a")
    assert session.calls.count("https://news.example/a") == RETRIES + 1


def test_a_missing_page_is_not_a_site_outage():
    fetcher, session, _ = _fetcher(
        {
            "https://news.example/robots.txt": [FakeResponse(text=ROBOTS)],
            "https://news.example/gone": [FakeResponse(404)],
        }
    )
    with pytest.raises(PageNotFound):
        fetcher.get("https://news.example/gone")
    assert session.calls.count("https://news.example/gone") == 1
