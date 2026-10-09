import csv
import datetime

import pytest

from core.deps import get_current_user
from integrations.market_data import MarketDataClient, MarketDataUnavailable
from integrations.psx_catalog import SNAPSHOT_FILE, load_snapshot
from main import app
from models.stock import PricePoint, Stock
from services.stock_service import StockService
from worker.tasks import refresh_stock_prices

PKT = datetime.timezone(datetime.timedelta(hours=5))


def bar(day: datetime.date, close: float, **extra) -> dict:
    """A daily bar stamped like the provider's: midnight Pakistan time."""
    return {
        "timestamp": datetime.datetime(day.year, day.month, day.day, tzinfo=PKT),
        "open": extra.get("open", close - 1),
        "high": extra.get("high", close + 1),
        "low": extra.get("low", close - 2),
        "close": close,
        "volume": extra.get("volume", 1000),
    }


def store(db, ticker: str, bars: list[dict]) -> Stock:
    stock = db.query(Stock).filter(Stock.ticker == ticker).one()
    db.add_all(PricePoint(stock_id=stock.id, **b) for b in bars)
    db.commit()
    return stock


LATEST = datetime.date(2026, 10, 8)


@pytest.fixture(autouse=True)
def authenticated():
    app.dependency_overrides[get_current_user] = lambda: object()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def provider_down(monkeypatch):
    """Every call to the external provider fails, as during a Yahoo outage."""

    def boom(*args, **kwargs):
        raise MarketDataUnavailable("timeout")

    monkeypatch.setattr(MarketDataClient, "get_history", staticmethod(boom))
    monkeypatch.setattr(MarketDataClient, "get_history_and_splits", staticmethod(boom))
    monkeypatch.setattr(MarketDataClient, "get_shares_outstanding", staticmethod(boom))
    monkeypatch.setattr(MarketDataClient, "_download", staticmethod(boom))


def test_requires_auth(client):
    app.dependency_overrides.clear()
    assert client.get("/stocks/search?q=SYS").status_code == 401


def test_ticker_mapping():
    assert MarketDataClient.to_provider_symbol("sys") == "SYS.KA"
    assert MarketDataClient.to_provider_symbol("SYS.KA") == "SYS.KA"
    assert MarketDataClient.to_provider_symbol("^KSE") == "^KSE"
    assert MarketDataClient.normalize_ticker("sys.ka") == "SYS"


# ---- Stock universe: the KSE-100 snapshot


def test_snapshot_file_is_a_complete_kse100_list():
    with SNAPSHOT_FILE.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    tickers = [r["ticker"] for r in rows]
    assert len(tickers) == 100 and len(set(tickers)) == 100
    assert {"LUCK", "OGDC", "HBL", "SYS"} <= set(tickers)
    assert {r["snapshot_date"] for r in rows} == {"2026-10-10"}
    assert {r["source_url"] for r in rows} == {"https://dps.psx.com.pk/indices/KSE100"}
    excluded = [r for r in rows if r["included"] != "true"]
    assert all(r["exclusion_reason"] for r in excluded)
    assert len(load_snapshot()) == 100 - len(excluded) == 95


def test_catalog_matches_the_snapshot(client, db):
    seeded = {t for (t,) in db.query(Stock.ticker)}
    assert seeded == {c.ticker for c in load_snapshot()}
    assert not seeded & {"AAPL", "LOWCONF", "EPCL", "NETSOL", "NRL", "UNITY"}
    browse = client.get("/stocks/search").json()["results"]
    assert len(browse) == 95


@pytest.mark.parametrize(
    "query, expected",
    [("SYS", "SYS"), ("systems", "SYS"), ("meezan", "MEBL"), ("cement", "LUCK")],
)
def test_search_by_ticker_name_or_sector(client, query, expected):  # PRD.md FR9
    response = client.get(f"/stocks/search?q={query}")
    assert response.status_code == 200
    assert expected in [r["ticker"] for r in response.json()["results"]]


def test_search_exact_ticker_first(client):
    assert client.get("/stocks/search?q=SYS").json()["results"][0]["ticker"] == "SYS"


# ---- Quote and history are served from the database


def test_quote_from_stored_prices(client, db, fake_redis):  # PRD.md FR8
    stock = store(
        db,
        "SYS",
        [
            bar(LATEST - datetime.timedelta(days=400), 150.0, high=999.0),  # outside 52 weeks
            bar(LATEST - datetime.timedelta(days=100), 130.0, high=140.0, low=90.0),
            bar(LATEST - datetime.timedelta(days=1), 116.0),
            bar(LATEST, 118.0, open=116.5, high=119.5, low=115.0, volume=1_250_000),
        ],
    )
    stock.shares_outstanding = 1_000_000
    db.commit()

    data = client.get("/stocks/SYS").json()
    assert (data["ticker"], data["name"], data["sector"]) == (
        "SYS",
        "Systems Limited",
        "Technology & Communication",
    )
    assert data["price"] == 118.0
    assert data["previous_close"] == 116.0
    assert data["change"] == pytest.approx(2.0)
    assert data["change_percent"] == pytest.approx(2.0 / 116.0 * 100)
    assert (data["open"], data["high"], data["low"], data["volume"]) == (
        116.5,
        119.5,
        115.0,
        1_250_000,
    )
    assert data["fifty_two_week_high"] == 140.0
    assert data["fifty_two_week_low"] == 90.0
    assert data["market_cap"] == 118.0 * 1_000_000
    assert "pe_ratio" not in data
    # The "as of" date is the PSX trading day of the latest stored bar
    as_of = datetime.datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    assert as_of.astimezone(PKT).date() == LATEST


def test_market_cap_unknown_without_shares(client, db, fake_redis):
    store(db, "SYS", [bar(LATEST, 118.0)])
    data = client.get("/stocks/SYS").json()
    assert data["market_cap"] is None
    assert data["previous_close"] is None and data["change"] is None


def test_history_window_counts_back_from_latest_stored_day(client, db, fake_redis):
    days = [LATEST - datetime.timedelta(days=n) for n in (400, 60, 20, 1, 0)]
    store(db, "SYS", [bar(d, 100.0 + i) for i, d in enumerate(days)])

    month = client.get("/stocks/SYS/history?period=1mo").json()
    assert [p["close"] for p in month] == [102.0, 103.0, 104.0]  # oldest first
    assert {"timestamp", "open", "high", "low", "close", "volume"} == set(month[0])
    assert len(client.get("/stocks/SYS/history?period=1y").json()) == 4
    assert len(client.get("/stocks/SYS/history?period=max").json()) == 5


def test_history_dates_are_psx_trading_dates(client, db, fake_redis):
    # Stored as 2026-10-06 19:00 UTC, but it is the 7 October trading day in Karachi
    store(db, "SYS", [bar(datetime.date(2026, 10, 7), 117.0), bar(LATEST, 118.0)])
    response = client.get("/stocks/SYS/history?start=2026-10-07&end=2026-10-07")
    assert [p["close"] for p in response.json()] == [117.0]


def test_unknown_ticker_is_404(client, fake_redis):
    for url in ("/stocks/NOPE", "/stocks/NOPE/history"):
        response = client.get(url)
        assert response.status_code == 404
        assert "not a KSE-100 stock" in response.json()["detail"]


def test_catalog_stock_without_prices_is_503(client, fake_redis):
    # The refresh job has not stored anything yet: an upstream problem, not "not found"
    for url in ("/stocks/HBL", "/stocks/HBL/history"):
        response = client.get(url)
        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"]


def test_provider_outage_does_not_affect_pages(client, db, fake_redis, provider_down):
    # Memory.md §4: with Yahoo down, history used to return 200 with 0 points
    store(db, "SYS", [bar(LATEST - datetime.timedelta(days=1), 116.0), bar(LATEST, 118.0)])
    assert client.get("/stocks/SYS").json()["price"] == 118.0
    assert len(client.get("/stocks/SYS/history").json()) == 2


def test_invalid_period_rejected(client, fake_redis):
    assert client.get("/stocks/SYS/history?period=7y").status_code == 422


# ---- Redis cache


def test_quote_served_from_cache_until_invalidated(client, db, fake_redis):
    stock = store(db, "SYS", [bar(LATEST, 118.0)])
    assert client.get("/stocks/SYS").json()["price"] == 118.0
    assert "stocks:quote:SYS" in fake_redis.store

    db.add(PricePoint(stock_id=stock.id, **bar(LATEST + datetime.timedelta(days=1), 121.0)))
    db.commit()
    assert client.get("/stocks/SYS").json()["price"] == 118.0  # cache hit

    StockService.invalidate(["SYS"])
    assert not [k for k in fake_redis.store if k.startswith("stocks:")]
    assert client.get("/stocks/SYS").json()["price"] == 121.0


def test_history_cache_key_includes_params(client, db, fake_redis):
    store(db, "SYS", [bar(LATEST - datetime.timedelta(days=60), 100.0), bar(LATEST, 118.0)])
    assert len(client.get("/stocks/SYS/history?period=1mo").json()) == 1
    assert len(client.get("/stocks/SYS/history?period=1y").json()) == 2
    assert {"stocks:history:SYS:period=1mo", "stocks:history:SYS:period=1y"} <= set(
        fake_redis.store
    )


def test_works_without_redis(client, db, monkeypatch):
    def broken():
        raise ConnectionError("redis down")

    monkeypatch.setattr("services.stock_service.get_redis_client", broken)
    store(db, "SYS", [bar(LATEST, 118.0)])
    assert client.get("/stocks/SYS").status_code == 200


# ---- End-of-day refresh job


@pytest.fixture
def provider(monkeypatch):
    """SYS has data, HBL's request fails, every other ticker returns nothing."""
    calls = []

    def get_history_and_splits(ticker, period="1y"):
        calls.append((ticker, period))
        if ticker == "HBL":
            raise MarketDataUnavailable("timeout")
        if ticker == "SYS":
            return [bar(LATEST - datetime.timedelta(days=1), 116.0), bar(LATEST, 118.0)], []
        return [], []

    monkeypatch.setattr(
        MarketDataClient, "get_history_and_splits", staticmethod(get_history_and_splits)
    )
    monkeypatch.setattr(
        MarketDataClient, "get_shares_outstanding", staticmethod(lambda ticker: 1_473_404_435)
    )
    return calls


def _stored(db, ticker: str) -> list[float]:
    stock = db.query(Stock).filter(Stock.ticker == ticker).one()
    db.expire_all()
    return [
        float(p.close)
        for p in db.query(PricePoint)
        .filter(PricePoint.stock_id == stock.id)
        .order_by(PricePoint.timestamp)
    ]


def test_refresh_stores_prices_and_reports_failures(db, provider, fake_redis):
    fake_redis.set("stocks:quote:SYS", "{}")
    result = refresh_stock_prices.run(tickers=["SYS", "HBL", "MCB"], update_shares=True)

    assert result["status"] == "completed"
    assert result["refreshed"] == 1 and result["upserted_points"] == 2
    assert result["failed"] == ["HBL"] and result["no_data"] == ["MCB"]
    assert _stored(db, "SYS") == [116.0, 118.0]
    assert db.query(Stock).filter(Stock.ticker == "SYS").one().shares_outstanding == 1_473_404_435
    assert "stocks:quote:SYS" not in fake_redis.store  # stale cache dropped


def test_refresh_is_idempotent_and_updates_corrected_bars(db, provider, fake_redis, monkeypatch):
    refresh_stock_prices.run(tickers=["SYS"])
    monkeypatch.setattr(
        MarketDataClient,
        "get_history_and_splits",
        staticmethod(lambda ticker, period="1y": ([bar(LATEST, 118.5)], [])),
    )
    refresh_stock_prices.run(tickers=["SYS"])
    assert _stored(db, "SYS") == [116.0, 118.5]


def test_refresh_defaults_to_the_whole_universe(db, provider, fake_redis):
    refresh_stock_prices.run()
    assert {t for t, _ in provider} == {c.ticker for c in load_snapshot()}
    assert {p for _, p in provider} == {"1mo"}


def test_refresh_with_no_data_at_all_is_reported_as_outage(db, fake_redis, provider_down):
    result = refresh_stock_prices.run(tickers=["SYS", "HBL"])
    assert result["status"] == "provider_unavailable"
    assert result["refreshed"] == 0 and result["failed"] == ["SYS", "HBL"]


def test_refresh_skips_tickers_outside_the_universe(db, provider, fake_redis):
    result = refresh_stock_prices.run(tickers=["AAPL"])
    assert result["failed"] == ["AAPL"] and provider == []
