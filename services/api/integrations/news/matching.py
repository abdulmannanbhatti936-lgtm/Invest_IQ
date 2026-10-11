"""
Headline-to-ticker matching (decided 2026-10-11, Memory.md §3). A reviewed list of names
per tracked stock (`integrations/data/news_aliases.csv`) is matched as whole words,
ignoring case and punctuation, so "Mari Petroleum's" and the URL slug "mari-petroleum"
both match MARI. Routine items that only carry a company's name (NBP's daily exchange
rates, the HBL PMI, the banks' fund arms) are dropped by `news_exclusions.csv`.

An article's stocks are the tracked stocks its URL slug names, and only those: the history
of Profit and Mettis is discovered through sitemaps that give the slug and not the
headline, so the same rule for every source and period keeps the news feature consistent
from training to live use, and a passing mention in a headline never attaches a stock.
Exclusions are checked against the headline and the slug together, because either one may
carry the routine wording (audit fix, 2026-10-11).

A stored headline must also describe the article its URL names (`title_matches_slug`): a
few pages serve another article's title, and such a headline would be scored for the
wrong stock.
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


# Words too common in headlines to show that a title and a slug describe the same article
_COMMON_WORDS = frozenset(
    "the and for with from into over after amid its has have was are will this that than "
    "not but via per new says say".split()
)


def _content_words(text: str) -> set[str]:
    # The first 5 letters, so 'boosts' and 'boost' or 'production' and 'produces' meet
    return {w[:5] for w in normalize(text).split() if len(w) >= 3 and w not in _COMMON_WORDS}


class TickerMatcher:
    def __init__(self, aliases: dict[str, list[str]], exclusions: dict[str, list[str]]):
        self.tickers = frozenset(aliases)
        self._aliases = {t: [normalize(a) for a in names] for t, names in aliases.items()}
        self._exclusions = {t: [normalize(p).strip() for p in ps] for t, ps in exclusions.items()}

    def _named(self, clean: str) -> set[str]:
        return {t for t, names in self._aliases.items() if any(name in clean for name in names)}

    def _excluded(self, ticker: str, clean: str) -> bool:
        return any(phrase in clean for phrase in self._exclusions.get(ticker, []))

    def match(self, text: str) -> set[str]:
        clean = normalize(text)
        return {t for t in self._named(clean) if not self._excluded(t, clean)}

    def match_article(self, url: str, headline: str | None = None) -> set[str]:
        """The tracked stocks the URL slug names, less those the headline + slug exclude."""
        slug = url_slug(url)
        context = normalize(f"{headline or ''} {slug}")
        return {t for t in self._named(normalize(slug)) if not self._excluded(t, context)}

    def title_matches_slug(self, headline: str, url: str) -> bool:
        """
        Whether a headline plausibly belongs to the article its URL names: both name the
        same tracked stock, or they share at least two content words. Checked on the 2,164
        stored rows on 2026-10-11, this flagged only titles of other articles.
        """
        slug = url_slug(url)
        if self.match(headline) & self.match(slug):
            return True
        return len(_content_words(headline) & _content_words(slug)) >= 2


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
