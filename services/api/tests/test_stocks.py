import datetime

import pytest

from core.deps import get_current_user
from integrations.market_data import MarketDataClient, MarketDataUnavailable
from main import app

QUOTE = {
    "ticker": "SYS",
    "name": "Systems Ltd (provider name)",
    "sector": None,
    "currency": "PKR",
    "price": 118.0,
    "open": 117.0,
    "high": 119.5,
    "low": 116.2,
    "previous_close": 116.0,
    "change": 2.0,
    "change_percent": 1.7241,
    "volume": 1_250_000,
    "timestamp": datetime.datetime(2026, 10, 7, tzinfo=datetime.timezone.utc),
    "fifty_two_week_high": 174.4,
    "fifty_two_week_low": 105.98,
    "market_cap": 6.6e11,
    "pe_ratio": 57.5,
}

HISTORY = [
    {
        "timestamp": datetime.datetime(2026, 10, d, tzinfo=datetime.timezone.utc),
        "open": 100.0 + d,
        "high": 101.0 + d,
        "low": 99.0 + d,
        "close": 100.5 + d,
        "volume": 1000 * d,
    }
    for d in range(1, 6)
]


@pytest.fixture(autouse=True)
def authenticated():
    app.dependency_overrides[get_current_user] = lambda: object()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def provider(monkeypatch):
    """Mock the external market-data client and count calls to it."""
    calls = {"quote": 0, "history": 0}

    def get_quote(ticker):
        calls["quote"] += 1
        return dict(QUOTE) if MarketDataClient.normalize_ticker(ticker) == "SYS" else None

    def get_history(ticker, period="1y", start=None, end=None):
        calls["history"] += 1
        return [dict(r) for r in HISTORY] if ticker.upper() == "SYS" else []

    monkeypatch.setattr(MarketDataClient, "get_quote", staticmethod(get_quote))
    monkeypatch.setattr(MarketDataClient, "get_history", staticmethod(get_history))
    return calls


def test_requires_auth(client):
    app.dependency_overrides.clear()
    assert client.get("/stocks/search?q=SYS").status_code == 401


def test_ticker_mapping():
    assert MarketDataClient.to_provider_symbol("sys") == "SYS.KA"
    assert MarketDataClient.to_provider_symbol("SYS.KA") == "SYS.KA"
    assert MarketDataClient.to_provider_symbol("^KSE") == "^KSE"
    assert MarketDataClient.normalize_ticker("sys.ka") == "SYS"


@pytest.mark.parametrize(
    "query, expected",
    [("SYS", "SYS"), ("systems", "SYS"), ("meezan", "MEBL"), ("cement", "LUCK")],
)
def test_search_by_ticker_name_or_sector(client, query, expected):  # PRD.md FR9
    response = client.get(f"/stocks/search?q={query}")
    assert response.status_code == 200
    tickers = [r["ticker"] for r in response.json()["results"]]
    assert expected in tickers


def test_search_exact_ticker_first_and_browse(client):
    results = client.get("/stocks/search?q=SYS").json()["results"]
    assert results[0]["ticker"] == "SYS"
    browse = client.get("/stocks/search").json()["results"]
    assert len(browse) >= 40


def test_get_quote_uses_catalog_name_and_has_key_stats(client, provider, fake_redis):
    response = client.get("/stocks/SYS")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "SYS"
    assert data["name"] == "Systems Limited"
    assert data["sector"] == "Technology & Communication"
    for key in (
        "price",
        "previous_close",
        "fifty_two_week_high",
        "fifty_two_week_low",
        "pe_ratio",
        "market_cap",
    ):
        assert data[key] is not None


def test_quote_cache_hit(client, provider, fake_redis):
    assert client.get("/stocks/SYS").status_code == 200
    assert client.get("/stocks/SYS").status_code == 200
    assert provider["quote"] == 1  # second call served from Redis


def test_history_and_cache_hit(client, provider, fake_redis):
    first = client.get("/stocks/SYS/history?period=1mo")
    assert first.status_code == 200
    assert len(first.json()) == 5
    assert {"timestamp", "open", "high", "low", "close", "volume"} <= set(first.json()[0])
    assert client.get("/stocks/SYS/history?period=1mo").json() == first.json()
    assert provider["history"] == 1


def test_unknown_ticker(client, provider, fake_redis):
    assert client.get("/stocks/NOPE").status_code == 404
    assert client.get("/stocks/NOPE/history").json() == []  # frontend shows "insufficient data"


def test_invalid_period_rejected(client, provider, fake_redis):
    assert client.get("/stocks/SYS/history?period=7y").status_code == 422


def test_provider_outage_degrades_gracefully(client, fake_redis, monkeypatch):
    def boom(*args, **kwargs):
        raise MarketDataUnavailable("timeout")

    monkeypatch.setattr(MarketDataClient, "get_quote", staticmethod(boom))
    monkeypatch.setattr(MarketDataClient, "get_history", staticmethod(boom))
    for url in ("/stocks/SYS", "/stocks/SYS/history"):
        response = client.get(url)
        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"]


def test_works_without_redis(client, provider, monkeypatch):
    def broken():
        raise ConnectionError("redis down")

    monkeypatch.setattr("services.stock_service.get_redis_client", broken)
    assert client.get("/stocks/SYS").status_code == 200
