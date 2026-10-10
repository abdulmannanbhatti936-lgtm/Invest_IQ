"""News collection into sentiment_scores (Workflow.md Steps 4.2 and 4.5)."""

import datetime

from integrations.news.http import NewsSourceUnavailable, PageNotFound
from integrations.news.sources import BRECORDER, METTIS, PROFIT, Article, ArticleLink
from models.sentiment import NewsSourceStatus, SentimentScore
from services import news_ingestion
from services.news_ingestion import Collector, collect_all

UTC = datetime.timezone.utc
SINCE = datetime.date(2026, 10, 1)


def _article(source, slug, headline, day=8):
    return Article(
        source,
        f"https://example.com/MOCK/2026/10/{day:02d}/{slug}",
        headline,
        datetime.datetime(2026, 10, day, 6, 0, tzinfo=UTC),
    )


def _rows(db, source=None):
    query = db.query(SentimentScore)
    if source:
        query = query.filter(SentimentScore.source == source)
    return query.all()


def test_one_row_per_matched_stock_and_never_twice(db):
    collector = Collector(db)
    article = _article(
        PROFIT, "lucky-cement-hub-power-shortlisted", "MOCK_ Lucky Cement, Hub Power"
    )
    assert collector.store(article) == 2
    assert sorted(r.stock.ticker for r in _rows(db)) == ["HUBC", "LUCK"]
    assert all(r.score is None and r.label is None for r in _rows(db))
    # A second run, or a fresh collector, finds the URL already stored
    assert Collector(db).store_articles([article], SINCE) == 0
    assert len(_rows(db)) == 2


def test_articles_without_a_tracked_stock_in_the_slug_are_not_stored(db):
    article = _article(METTIS, "kse-100-closes-higher", "MOCK_ KSE-100 up as OGDC gains")
    assert Collector(db).store_articles([article], SINCE) == 0
    assert _rows(db) == []


def test_links_are_fetched_only_when_new_in_range_and_matching(db):
    fetched = []

    def fetch(url):
        fetched.append(url)
        if url.endswith("gone"):
            raise PageNotFound(url)
        return Article(
            PROFIT, url, "MOCK_ OGDC output rises", datetime.datetime(2026, 10, 8, tzinfo=UTC)
        )

    links = [
        ArticleLink("https://example.com/MOCK/ogdc-output-rises", datetime.date(2026, 10, 8)),
        ArticleLink("https://example.com/MOCK/ogdc-old-news", datetime.date(2026, 9, 1)),
        ArticleLink("https://example.com/MOCK/budget-debate", datetime.date(2026, 10, 8)),
        ArticleLink("https://example.com/MOCK/ogdc-gone", datetime.date(2026, 10, 8)),
    ]
    assert Collector(db).store_links(PROFIT, links, fetch, SINCE) == 1
    assert fetched == [
        "https://example.com/MOCK/ogdc-output-rises",
        "https://example.com/MOCK/ogdc-gone",
    ]


class _FailingClient:
    def __init__(self, fetcher):
        pass

    def sitemap_pages(self):
        raise NewsSourceUnavailable("profit.example: HTTP 503 after 3 retries")


class _MettisClient:
    NEWEST = 10**9

    def __init__(self, fetcher):
        pass

    def load_more(self, before_row_id):
        if before_row_id != self.NEWEST:
            return []
        return [(5, _article(METTIS, "pso-signs-deal-64109", "MOCK_ PSO signs deal"))]

    def sitemap_pages(self):
        return []


class _RecorderClient:
    def __init__(self, fetcher):
        pass

    def latest(self):
        return [_article(BRECORDER, "ogdc-profit-rises", "MOCK_ OGDC profit rises")]


def test_a_failing_source_is_recorded_and_the_others_still_run(db, monkeypatch):
    monkeypatch.setattr(news_ingestion, "ProfitClient", _FailingClient)
    monkeypatch.setattr(news_ingestion, "MettisClient", _MettisClient)
    monkeypatch.setattr(news_ingestion, "BusinessRecorderClient", _RecorderClient)
    monkeypatch.setattr(news_ingestion, "_now", lambda: datetime.datetime(2026, 10, 9, tzinfo=UTC))

    results = collect_all(db, SINCE, fetcher=object())

    assert results[PROFIT]["status"] == "failed"
    assert results[METTIS] == {"status": "ok", "new_headlines": 1}
    assert results[BRECORDER] == {"status": "ok", "new_headlines": 1}
    profit = db.get(NewsSourceStatus, PROFIT)
    assert profit.last_success_at is None and "503" in profit.last_error
    assert db.get(NewsSourceStatus, METTIS).last_success_at is not None


def test_articles_older_than_the_window_are_ignored(db):
    since = datetime.date(2026, 10, 9)
    assert Collector(db).store_articles([_article(PROFIT, "ogdc-x", "MOCK_ OGDC")], since) == 0
