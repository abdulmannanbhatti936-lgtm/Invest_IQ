"""
Clients for the three news sources chosen in Step 4.1 (Memory.md §9). Each returns only a
headline, its link and its publish time: article text that a page or feed carries is never
kept (decided 2026-10-11).

- Profit (Pakistan Today): article sitemaps (2016 onwards, publish date in the URL); the
  exact headline and publish time come from the article page's metadata.
- Mettis Global: sitemaps up to 2025-12-01 (lastmod = publish time); everything after,
  and the live feed, from the site's own "load more" JSON (Home/LoadMore).
- Business Recorder: RSS feeds, live display only (no archive before about Dec 2022).
"""

import datetime
import html
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from integrations.news.http import PoliteFetcher

PROFIT = "profit"
METTIS = "mettis"
BRECORDER = "brecorder"
SOURCE_NAMES = {PROFIT: "Profit", METTIS: "Mettis Global", BRECORDER: "Business Recorder"}
# The sources whose history covers the whole training window, so only they feed the model
TRAINING_SOURCES = (PROFIT, METTIS)

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
UTC = datetime.timezone.utc


@dataclass(frozen=True)
class ArticleLink:
    """An article found in a sitemap: its URL and the date the sitemap gives for it."""

    url: str
    published_on: datetime.date


@dataclass(frozen=True)
class Article:
    source: str
    url: str
    headline: str
    published_at: datetime.datetime  # timezone-aware, UTC


class ParseError(ValueError):
    """A page or feed did not have the expected structure."""


def _utc(value: str) -> datetime.datetime:
    parsed = datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    # Mettis's JSON times carry no offset; they equal its sitemap times, which are UTC
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value).replace("\xa0", " ")).strip()


def _sitemap_entries(xml_text: str) -> Iterator[tuple[str, str | None]]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    for node in root.findall("sm:url", SITEMAP_NS) + root.findall("sm:sitemap", SITEMAP_NS):
        loc = node.findtext("sm:loc", default="", namespaces=SITEMAP_NS).strip()
        if loc:
            yield loc, node.findtext("sm:lastmod", default=None, namespaces=SITEMAP_NS)


def page_headline_and_time(page: str, title_suffix: str) -> tuple[str, datetime.datetime]:
    """Headline from og:title (or <title>) and publish time from the JSON-LD datePublished."""
    soup = BeautifulSoup(page, "lxml")
    meta = soup.find("meta", attrs={"property": "og:title"})
    title = meta.get("content") if meta else (soup.title.string if soup.title else None)
    if not title:
        raise ParseError("no headline on the page")
    headline = _clean_text(re.sub(rf"\s*[|\-–]\s*{re.escape(title_suffix)}\s*$", "", title))

    published = None
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        found = re.search(r'"datePublished"\s*:\s*"([^"]+)"', script.string or "")
        if found:
            published = found.group(1)
            break
    if published is None:
        meta = soup.find("meta", attrs={"property": "article:published_time"})
        published = meta.get("content") if meta else None
    if not published:
        raise ParseError("no publish time on the page")
    return headline, _utc(published)


class ProfitClient:
    BASE = "https://profit.pakistantoday.com.pk"
    TITLE_SUFFIX = "Profit by Pakistan Today"

    def __init__(self, fetcher: PoliteFetcher):
        self.fetcher = fetcher

    def sitemap_pages(self) -> list[str]:
        """Article sitemaps, newest first (sitemap-articles-1 holds the latest articles)."""
        index = self.fetcher.get(f"{self.BASE}/sitemap.xml").text
        return [loc for loc, _ in _sitemap_entries(index) if "sitemap-articles-" in loc]

    def article_links(self, sitemap_url: str) -> list[ArticleLink]:
        links = []
        for loc, _ in _sitemap_entries(self.fetcher.get(sitemap_url).text):
            found = re.search(r"/(\d{4})/(\d{2})/(\d{2})/[^/]+$", loc)
            if found:
                links.append(ArticleLink(loc, datetime.date(*map(int, found.groups()))))
        return links

    def article(self, url: str) -> Article:
        headline, published = page_headline_and_time(self.fetcher.get(url).text, self.TITLE_SUFFIX)
        return Article(PROFIT, url, headline, published)


class MettisClient:
    BASE = "https://mettisglobal.news"
    TITLE_SUFFIX = "Mettis Global"
    # Larger than any row id: asks the "load more" endpoint for the newest articles
    NEWEST = 10**9

    def __init__(self, fetcher: PoliteFetcher):
        self.fetcher = fetcher

    def sitemap_pages(self) -> list[str]:
        index = self.fetcher.get(f"{self.BASE}/sitemap_index.xml").text
        return [loc for loc, _ in _sitemap_entries(index) if "post-sitemap" in loc]

    def article_links(self, sitemap_url: str) -> list[ArticleLink]:
        return [
            ArticleLink(loc, _utc(lastmod).date())
            for loc, lastmod in _sitemap_entries(self.fetcher.get(sitemap_url).text)
            if lastmod and "/author/" not in loc
        ]

    def article(self, url: str) -> Article:
        headline, published = page_headline_and_time(self.fetcher.get(url).text, self.TITLE_SUFFIX)
        return Article(METTIS, url, headline, published)

    def load_more(self, before_row_id: int = NEWEST) -> list[tuple[int, Article]]:
        """The 10 articles listed just before `before_row_id`, newest first, with row ids."""
        response = self.fetcher.get(f"{self.BASE}/Home/LoadMore", {"lastNewsID": before_row_id})
        try:
            items = response.json()
            return [
                (
                    int(item["rowid"]),
                    Article(
                        METTIS,
                        f"{self.BASE}/{item['link'].lstrip('/')}",
                        _clean_text(item["headings"]["heading"][0]),
                        _utc(item["publishedTime"]),
                    ),
                )
                for item in items
            ]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise ParseError(f"Unexpected Mettis load-more response: {e}") from e


class BusinessRecorderClient:
    FEEDS = (
        "https://www.brecorder.com/feeds/markets",
        "https://www.brecorder.com/feeds/latest-news",
    )

    def __init__(self, fetcher: PoliteFetcher):
        self.fetcher = fetcher

    def latest(self) -> list[Article]:
        articles: dict[str, Article] = {}
        for feed in self.FEEDS:
            try:
                root = ET.fromstring(self.fetcher.get(feed).content)
            except ET.ParseError as e:
                raise ParseError(f"{feed}: {e}") from e
            for item in root.iter("item"):
                title, link, date = (item.findtext(k) for k in ("title", "link", "pubDate"))
                if title and link and date:
                    url = link.strip()
                    articles[url] = Article(
                        BRECORDER,
                        url,
                        _clean_text(title),
                        parsedate_to_datetime(date).astimezone(UTC),
                    )
        return list(articles.values())
