"""GET /stocks/{ticker}/sentiment, scoring and source freshness (Steps 4.5 and 4.7)."""

import datetime
from decimal import Decimal

import pytest

from core.config import settings
from core.deps import get_current_user
from main import app
from ml.sentiment import HeadlineScore, SentimentModelUnavailable
from models.sentiment import NewsSourceStatus, SentimentScore
from services.sentiment_service import badge_label, score_pending, source_freshness
from tests.test_predictions import mock_stock, store_history

UTC = datetime.timezone.utc
# store_history(days=40) ends on Friday 2022-02-25 (synthetic MOCK prices)
LAST_CLOSE_DAY = datetime.date(2022, 2, 25)


@pytest.fixture(autouse=True)
def authenticated():
    app.dependency_overrides[get_current_user] = lambda: object()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mocka(db, monkeypatch, fake_redis):
    monkeypatch.setattr(settings, "TRACKED_TICKERS", "MOCKA")
    stock = mock_stock(db)
    store_history(db, stock, days=40)
    return stock


def _headline(db, stock, when, score, label, source="profit", slug=None):
    row = SentimentScore(
        stock_id=stock.id,
        source=source,
        url=f"https://example.com/MOCK/{slug or when.isoformat()}",
        headline=f"MOCK_ headline {label} {when.isoformat()}",
        published_at=when,
        score=None if score is None else Decimal(str(score)),
        label=label,
        scorer=None if score is None else "finbert",
    )
    db.add(row)
    db.commit()
    return row


def _fresh(db, hours_ago=1):
    when = datetime.datetime.now(UTC) - datetime.timedelta(hours=hours_ago)
    for source in ("profit", "mettis"):
        db.merge(NewsSourceStatus(source=source, last_attempt_at=when, last_success_at=when))
    db.commit()


def test_counts_the_window_and_lists_news_after_the_close_separately(client, db, mocka):
    _fresh(db)
    # 05:00 UTC = 10:00 PKT, during the session
    on_close_day = datetime.datetime(2022, 2, 25, 5, 0, tzinfo=UTC)
    three_days_before = datetime.datetime(2022, 2, 22, 5, 0, tzinfo=UTC)
    after_close = datetime.datetime(2022, 2, 25, 12, 0, tzinfo=UTC)  # 17:00 PKT
    _headline(db, mocka, on_close_day, 0.8, "positive")
    _headline(db, mocka, three_days_before, -0.4, "negative")
    _headline(db, mocka, after_close, -0.9, "negative")
    _headline(db, mocka, on_close_day, 0.9, "positive", source="brecorder", slug="br")

    body = client.get("/stocks/MOCKA/sentiment").json()

    assert body["as_of_date"] == LAST_CLOSE_DAY.isoformat()
    assert body["counted_headlines"] == 2
    # weights 1 and 0.5: (0.8 * 1 - 0.4 * 0.5) / 1.5
    assert body["news_weight"] == pytest.approx(1.5)
    assert body["score"] == pytest.approx(0.4)
    assert body["label"] == "positive"
    counted = {h["source"]: h["weight"] for h in body["headlines"]}
    # Business Recorder is shown but carries no weight: it is not a training source
    assert counted["brecorder"] is None
    assert [h["label"] for h in body["after_close_headlines"]] == ["negative"]
    assert body["freshness"]["stale"] is False


def test_no_recent_news_is_reported_as_such(client, db, mocka):
    _fresh(db)
    body = client.get("/stocks/MOCKA/sentiment").json()
    assert body["label"] is None and body["score"] is None
    assert body["counted_headlines"] == 0 and body["headlines"] == []


def test_stale_sources_are_flagged(client, db, mocka):
    _fresh(db, hours_ago=30)
    body = client.get("/stocks/MOCKA/sentiment").json()
    assert body["freshness"]["stale"] is True
    assert all(s["stale"] for s in body["freshness"]["sources"])


def test_a_source_that_never_succeeded_is_stale(db):
    assert source_freshness(db)["stale"] is True


def test_stock_without_news_coverage_is_not_covered(client, db, mocka):
    response = client.get("/stocks/HBL/sentiment")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_covered"
    assert response.json()["detail"]["covered_stock_count"] == 1


def test_unknown_stock(client, mocka):
    response = client.get("/stocks/NOPE/sentiment")
    assert response.json()["detail"]["code"] == "stock_not_found"


def test_requires_login(client):
    app.dependency_overrides.clear()
    assert client.get("/stocks/OGDC/sentiment").status_code == 401


def test_badge_is_the_label_with_most_weight_and_a_tie_is_neutral():
    assert badge_label(["positive", "negative", "negative"], [1.0, 0.4, 0.4]) == "positive"
    assert badge_label(["positive", "negative"], [0.5, 0.5]) == "neutral"
    assert badge_label([], []) is None


class _Scorer:
    def __init__(self, fail=False):
        self.fail = fail

    def score(self, texts):
        if self.fail:
            raise SentimentModelUnavailable("FinBERT could not be loaded")
        return [HeadlineScore(0.5, "positive", "finbert", "MOCK", 0.9) for _ in texts]


def test_score_pending_fills_every_unscored_row(db, mocka):
    _headline(db, mocka, datetime.datetime(2022, 2, 25, 5, tzinfo=UTC), None, None)
    assert score_pending(db, _Scorer()) == 1
    row = db.query(SentimentScore).one()
    assert (float(row.score), row.label, row.scorer) == (0.5, "positive", "finbert")


def test_finbert_failure_leaves_rows_unscored(db, mocka):
    _headline(db, mocka, datetime.datetime(2022, 2, 25, 5, tzinfo=UTC), None, None)
    with pytest.raises(SentimentModelUnavailable):
        score_pending(db, _Scorer(fail=True))
    row = db.query(SentimentScore).one()
    assert row.score is None and row.label is None
