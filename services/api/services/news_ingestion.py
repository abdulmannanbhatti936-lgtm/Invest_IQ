"""
News collection (Workflow.md Steps 4.2 and 4.5): find articles about the tracked stocks,
store one sentiment_scores row per matched stock (unscored), and record each source's
last attempt and success. The `scrape_news_sentiment` job runs this for the last
LIVE_WINDOW_DAYS; `python -m services.news_ingestion backfill` runs it back to the start of
the training window. A URL already stored is never fetched again, so the database doubles
as the cache and an interrupted backfill resumes where it stopped.
"""

import argparse
import datetime
import logging
from collections.abc import Callable, Iterable

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from integrations.news.http import (
    FetchNotAllowed,
    NewsSourceUnavailable,
    PageNotFound,
    PoliteFetcher,
)
from integrations.news.matching import TickerMatcher, default_matcher
from integrations.news.sources import (
    BRECORDER,
    METTIS,
    PROFIT,
    Article,
    ArticleLink,
    BusinessRecorderClient,
    MettisClient,
    ParseError,
    ProfitClient,
)
from models.sentiment import NewsSourceStatus, SentimentScore
from models.stock import Stock

logger = logging.getLogger(__name__)

LIVE_WINDOW_DAYS = 7
# Mettis's sitemaps stop here; later articles come from its "load more" feed. The overlap
# makes sure nothing falls between the two (duplicates are ignored by URL).
METTIS_SITEMAP_END = datetime.date(2025, 12, 1)
METTIS_OVERLAP_DAYS = 7
# The 10-trading-day news window of the first training row (2021-10-08) starts here
BACKFILL_START = datetime.date(2021, 9, 15)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class Collector:
    def __init__(self, db: Session, matcher: TickerMatcher | None = None):
        self.db = db
        self.matcher = matcher or default_matcher()
        self.stock_ids = {
            ticker: stock_id
            for ticker, stock_id in db.query(Stock.ticker, Stock.id).filter(
                Stock.ticker.in_(list(self.matcher.tickers))
            )
        }
        self._known: dict[str, set[str]] = {}

    def known_urls(self, source: str) -> set[str]:
        if source not in self._known:
            self._known[source] = {
                url
                for (url,) in self.db.query(SentimentScore.url)
                .filter(SentimentScore.source == source)
                .distinct()
            }
        return self._known[source]

    def store(self, article: Article) -> int:
        """Insert one row per matched stock; returns how many were new."""
        tickers = self.matcher.match_article(article.url, article.headline)
        rows = [
            {
                "stock_id": self.stock_ids[t],
                "source": article.source,
                "url": article.url,
                "headline": article.headline,
                "published_at": article.published_at,
                "fetched_at": _now(),
            }
            for t in sorted(tickers)
            if t in self.stock_ids
        ]
        self.known_urls(article.source).add(article.url)
        if not rows:
            return 0
        stmt = (
            insert(SentimentScore)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_sentiment_scores_stock_url")
        )
        inserted = self.db.execute(stmt).rowcount
        self.db.commit()
        return inserted

    def store_articles(self, articles: Iterable[Article], since: datetime.date) -> int:
        return sum(
            self.store(a)
            for a in articles
            if a.published_at.date() >= since and a.url not in self.known_urls(a.source)
        )

    def store_links(
        self,
        source: str,
        links: Iterable[ArticleLink],
        fetch: Callable[[str], Article],
        since: datetime.date,
        until: datetime.date | None = None,
    ) -> int:
        """Fetch the page of every new, in-range link whose slug names a tracked stock."""
        new = 0
        for link in links:
            if link.published_on < since or (until and link.published_on > until):
                continue
            if link.url in self.known_urls(source) or not self.matcher.match_article(link.url):
                continue
            try:
                new += self.store(fetch(link.url))
            except (PageNotFound, ParseError, FetchNotAllowed) as e:
                logger.warning(f"Skipped {link.url}: {e}")
                self.known_urls(source).add(link.url)
        return new


def collect_profit(collector: Collector, client: ProfitClient, since: datetime.date) -> int:
    new = 0
    for page in client.sitemap_pages():
        links = client.article_links(page)
        new += collector.store_links(PROFIT, links, client.article, since)
        # Sitemap pages run newest to oldest: stop once a page ends before `since`
        if links and min(link.published_on for link in links) < since:
            break
    return new


def collect_mettis(collector: Collector, client: MettisClient, since: datetime.date) -> int:
    feed_until = max(since, METTIS_SITEMAP_END - datetime.timedelta(days=METTIS_OVERLAP_DAYS))
    new, before = 0, MettisClient.NEWEST
    while True:
        page = client.load_more(before)
        if not page:
            break
        new += collector.store_articles((a for _, a in page), feed_until)
        before = min(row_id for row_id, _ in page)
        if min(a.published_at.date() for _, a in page) < feed_until:
            break
    if since < feed_until:
        for sitemap in client.sitemap_pages():
            links = client.article_links(sitemap)
            if links and max(link.published_on for link in links) < since:
                continue
            new += collector.store_links(METTIS, links, client.article, since, feed_until)
    return new


def collect_brecorder(collector: Collector, client: BusinessRecorderClient) -> int:
    since = (_now() - datetime.timedelta(days=LIVE_WINDOW_DAYS)).date()
    return collector.store_articles(client.latest(), since)


def record_status(
    db: Session, source: str, error: str | None, new_headlines: int | None = None
) -> None:
    status = db.get(NewsSourceStatus, source) or NewsSourceStatus(source=source)
    now = _now()
    status.last_attempt_at = now
    status.last_error = error
    if error is None:
        status.last_success_at = now
        status.last_new_headlines = new_headlines
    db.add(status)
    db.commit()


def collect_all(
    db: Session, since: datetime.date, fetcher: PoliteFetcher | None = None
) -> dict[str, dict]:
    """Run every source; one failing source never stops the others (PRD.md FR22)."""
    fetcher = fetcher or PoliteFetcher()
    collector = Collector(db)
    jobs = {
        PROFIT: lambda: collect_profit(collector, ProfitClient(fetcher), since),
        METTIS: lambda: collect_mettis(collector, MettisClient(fetcher), since),
        BRECORDER: lambda: collect_brecorder(collector, BusinessRecorderClient(fetcher)),
    }
    results = {}
    for source, job in jobs.items():
        try:
            new = job()
        except (NewsSourceUnavailable, FetchNotAllowed, ParseError) as e:
            db.rollback()
            logger.error(f"News source {source} failed: {e}")
            record_status(db, source, str(e))
            results[source] = {"status": "failed", "error": str(e)}
            continue
        record_status(db, source, None, new)
        results[source] = {"status": "ok", "new_headlines": new}
    return results


def main() -> None:
    """`python -m services.news_ingestion backfill [--since YYYY-MM-DD]`"""
    from core.database import SessionLocal

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("command", choices=["backfill"])
    parser.add_argument("--since", type=datetime.date.fromisoformat, default=BACKFILL_START)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    db = SessionLocal()
    try:
        print(collect_all(db, args.since))
    finally:
        db.close()


if __name__ == "__main__":
    main()
