import datetime
from typing import Literal

from pydantic import BaseModel

from schemas.types import UTCDateTime

SentimentLabel = Literal["positive", "negative", "neutral"]


class SentimentHeadline(BaseModel):
    """A headline and its link; the article text is never stored or shown."""

    headline: str
    source: str
    source_name: str
    url: str
    published_at: UTCDateTime
    label: SentimentLabel | None  # None while the headline waits to be scored
    score: float | None  # -1 .. +1
    scorer: Literal["finbert", "vader"] | None
    weight: float | None  # share in today's sentiment; None = not counted


class SourceFreshness(BaseModel):
    source: str
    name: str
    last_success_at: UTCDateTime | None
    stale: bool


class Freshness(BaseModel):
    stale: bool  # a training source has not been scraped successfully for 24 hours
    sources: list[SourceFreshness]


class StockSentimentResponse(BaseModel):
    ticker: str
    as_of_date: datetime.date | None  # trading day of the latest stored close
    label: SentimentLabel | None  # None when no headline counts
    score: float | None
    news_weight: float
    counted_headlines: int
    window_trading_days: int
    half_life_trading_days: int
    headlines: list[SentimentHeadline]  # inside the window, newest first
    after_close_headlines: list[SentimentHeadline]  # count from the next trading day
    freshness: Freshness
