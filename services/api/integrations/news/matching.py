"""
Headline-to-ticker matching (decided 2026-10-11, Memory.md §3). A reviewed list of names
per tracked stock (`integrations/data/news_aliases.csv`) is matched as whole words,
ignoring case and punctuation, so "Mari Petroleum's" and the URL slug "mari-petroleum"
both match MARI. Routine items that only carry a company's name (NBP's daily exchange
rates, the HBL PMI, the banks' fund arms) are dropped by `news_exclusions.csv`.

An article is considered only if its URL slug names a tracked stock. The history of
Profit and Mettis is discovered through sitemaps that give the slug and not the headline,
so applying the same rule to every source and period keeps the news feature consistent
from training to live use. The tickers are then taken from the slug and the headline.
"""

import csv
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def normalize(text: str) -> str:
    """Lower case, every run of non-alphanumerics turned into one space."""
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def url_slug(url: str) -> str:
    """The last path segment, without Mettis's trailing article id (e.g. '-64110')."""
    segment = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"-\d+$", "", segment)


class TickerMatcher:
    def __init__(self, aliases: dict[str, list[str]], exclusions: dict[str, list[str]]):
        self.tickers = frozenset(aliases)
        self._aliases = {t: [normalize(a) for a in names] for t, names in aliases.items()}
        self._exclusions = {t: [normalize(p).strip() for p in ps] for t, ps in exclusions.items()}

    def match(self, text: str) -> set[str]:
        clean = normalize(text)
        return {
            ticker
            for ticker, names in self._aliases.items()
            if any(name in clean for name in names)
            and not any(phrase in clean for phrase in self._exclusions.get(ticker, []))
        }

    def match_article(self, url: str, headline: str | None = None) -> set[str]:
        """Tickers for an article; empty unless its URL slug names a tracked stock."""
        from_slug = self.match(url_slug(url))
        if not from_slug:
            return set()
        return from_slug | (self.match(headline) if headline else set())


def _read(path: Path, value_column: str) -> dict[str, list[str]]:
    table: dict[str, list[str]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            table.setdefault(row["ticker"].strip().upper(), []).append(row[value_column].strip())
    return table


@lru_cache(maxsize=1)
def default_matcher() -> TickerMatcher:
    return TickerMatcher(
        _read(DATA_DIR / "news_aliases.csv", "alias"),
        _read(DATA_DIR / "news_exclusions.csv", "phrase"),
    )
