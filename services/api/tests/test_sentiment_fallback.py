"""
PRD.md FR22 / Workflow.md Step 4.7: when the news sources fail, a model that reads news
falls back to its price-only model and the forecast is flagged as reduced confidence,
instead of failing or silently reading "no news".
"""

import datetime

import pytest

from core.config import settings
from core.deps import get_current_user
from integrations.news.http import NewsSourceUnavailable
from main import app
from ml.inference import load_bundle
from models.sentiment import NewsSourceStatus
from services import news_ingestion
from services.prediction_service import (
    SENTIMENT_STALE,
    SENTIMENT_UNAVAILABLE,
    SENTIMENT_USED,
    generate_prediction,
    low_confidence_reasons,
)
from tests.fixtures.build_model_fixture import FIXTURE_DIR, FIXTURE_VERSION, NEWS_FIXTURE_VERSION
from tests.test_predictions import mock_stock, store_history

UTC = datetime.timezone.utc


@pytest.fixture(autouse=True)
def authenticated():
    app.dependency_overrides[get_current_user] = lambda: object()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def news_model(monkeypatch, fake_redis):
    monkeypatch.setattr(settings, "MODEL_DIR", str(FIXTURE_DIR))
    return load_bundle(FIXTURE_DIR, NEWS_FIXTURE_VERSION)


@pytest.fixture
def mocka(db):
    stock = mock_stock(db)
    store_history(db, stock)
    return stock


def _sources_succeeded(db, hours_ago):
    when = datetime.datetime.now(UTC) - datetime.timedelta(hours=hours_ago)
    for source in ("profit", "mettis"):
        db.merge(NewsSourceStatus(source=source, last_attempt_at=when, last_success_at=when))
    db.commit()


class _Down:
    NEWEST = 10**9

    def __init__(self, fetcher):
        pass

    def sitemap_pages(self):
        raise NewsSourceUnavailable("HTTP 503 after 3 retries")

    def load_more(self, before_row_id):
        raise NewsSourceUnavailable("HTTP 503 after 3 retries")

    def latest(self):
        raise NewsSourceUnavailable("HTTP 503 after 3 retries")


def test_forced_source_failure_gives_a_flagged_price_only_forecast(
    client, db, mocka, news_model, monkeypatch
):
    # The last good scrape was 30 hours ago and every source fails now
    _sources_succeeded(db, hours_ago=30)
    for name in ("ProfitClient", "MettisClient", "BusinessRecorderClient"):
        monkeypatch.setattr(news_ingestion, name, _Down)
    results = news_ingestion.collect_all(db, datetime.date(2026, 10, 1), fetcher=object())
    assert {r["status"] for r in results.values()} == {"failed"}

    prediction = generate_prediction(db, mocka, news_model)

    assert prediction.sentiment_status == SENTIMENT_STALE
    assert prediction.model_version == NEWS_FIXTURE_VERSION
    price_only = generate_prediction(db, mocka, load_bundle(FIXTURE_DIR, FIXTURE_VERSION))
    assert float(prediction.forecast_price) == float(price_only.forecast_price)
    assert SENTIMENT_UNAVAILABLE in low_confidence_reasons(prediction, news_model, "MOCKA")

    monkeypatch.setattr(settings, "MODEL_DIR", str(FIXTURE_DIR))
    monkeypatch.setattr(
        "routers.predictions.load_bundle", lambda model_dir, version=None: news_model
    )
    body = client.get("/stocks/MOCKA/prediction").json()
    assert body["sentiment_status"] == "unavailable"
    assert body["low_confidence"] is True
    assert "sentiment_unavailable" in body["low_confidence_reasons"]


def test_fresh_sources_feed_the_news_inputs(db, mocka, news_model):
    _sources_succeeded(db, hours_ago=1)
    prediction = generate_prediction(db, mocka, news_model)
    assert prediction.sentiment_status == SENTIMENT_USED
    assert SENTIMENT_UNAVAILABLE not in low_confidence_reasons(prediction, news_model, "MOCKA")


def test_a_price_only_model_never_reports_sentiment(db, mocka, monkeypatch, fake_redis):
    monkeypatch.setattr(settings, "MODEL_DIR", str(FIXTURE_DIR))
    bundle = load_bundle(FIXTURE_DIR, FIXTURE_VERSION)
    prediction = generate_prediction(db, mocka, bundle)
    assert prediction.sentiment_status is None
    assert SENTIMENT_UNAVAILABLE not in low_confidence_reasons(prediction, bundle, "MOCKA")
