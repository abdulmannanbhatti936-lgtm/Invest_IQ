"""
Scoring stored headlines and serving a stock's news sentiment (Workflow.md Steps 4.5 and
4.8, PRD.md FR17-FR22).

The stock detail page shows the same number the model reads: the decayed sentiment of the
last NEWS_WINDOW_DAYS trading days up to the latest stored close (ml/features.py), from the
training sources only. Headlines published after that close are listed separately: they
count from the next trading day. The badge is the label with the largest decayed weight
among the counted headlines (a tie is neutral), so no extra cut-off is needed.
"""

import datetime
import logging

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from integrations.news.sources import SOURCE_NAMES, TRAINING_SOURCES
from ml.features import NEWS_HALF_LIFE_DAYS, NEWS_WINDOW_DAYS, headline_trading_days, news_weights
from ml.sentiment import HeadlineScorer
from models.sentiment import NewsSourceStatus, SentimentScore
from models.stock import Stock
from services.stock_service import PriceDataUnavailable, StockService

logger = logging.getLogger(__name__)

STALE_AFTER = datetime.timedelta(hours=24)
SCORE_BATCH = 64
# Headlines listed on the page: the counted window plus the newest ones after the last close
LISTED_AFTER_CLOSE = 10


def score_pending(db: Session, scorer: HeadlineScorer | None = None) -> int:
    """Score every unscored headline. Raises SentimentModelUnavailable if FinBERT is down."""
    scorer = scorer or HeadlineScorer()
    done = 0
    while True:
        batch = (
            db.query(SentimentScore)
            .filter(SentimentScore.score.is_(None))
            .order_by(SentimentScore.published_at)
            .limit(SCORE_BATCH)
            .all()
        )
        if not batch:
            return done
        for row, result in zip(batch, scorer.score([r.headline for r in batch]), strict=True):
            row.score = round(result.score, 4)
            row.label = result.label
            row.scorer = result.scorer
            row.scorer_version = result.scorer_version
            row.finbert_confidence = round(result.finbert_confidence, 4)
        db.commit()
        done += len(batch)


def source_freshness(db: Session, now: datetime.datetime | None = None) -> dict:
    """
    Whether every training source succeeded within STALE_AFTER (PRD.md FR22). A source
    that never succeeded counts as stale.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    statuses = {s.source: s for s in db.query(NewsSourceStatus)}
    sources = []
    for source in TRAINING_SOURCES:
        status = statuses.get(source)
        last = status.last_success_at if status else None
        sources.append(
            {
                "source": source,
                "name": SOURCE_NAMES[source],
                "last_success_at": last,
                "stale": last is None or now - last > STALE_AFTER,
            }
        )
    return {"stale": any(s["stale"] for s in sources), "sources": sources}


def headline_frame(db: Session, stock: Stock) -> pd.DataFrame:
    """A stock's scored headlines from the training sources: `published_at`, `score`."""
    rows = (
        db.query(SentimentScore.published_at, SentimentScore.score)
        .filter(
            SentimentScore.stock_id == stock.id,
            SentimentScore.source.in_(TRAINING_SOURCES),
            SentimentScore.score.isnot(None),
        )
        .all()
    )
    return pd.DataFrame(
        {
            "published_at": pd.to_datetime([r.published_at for r in rows], utc=True),
            "score": [float(r.score) for r in rows],
        }
    )


def _trading_days(db: Session, ticker: str) -> pd.Series:
    try:
        history = StockService.get_history(db, ticker, period="3mo")
    except PriceDataUnavailable:
        return pd.Series([], dtype="datetime64[ns]")
    return pd.Series(
        pd.to_datetime([bar["timestamp"] for bar in history], utc=True)
        .tz_convert("Asia/Karachi")
        .tz_localize(None)
        .normalize()
    )


def _headline_payload(row: SentimentScore, weight: float | None) -> dict:
    return {
        "headline": row.headline,
        "source": row.source,
        "source_name": SOURCE_NAMES[row.source],
        "url": row.url,
        "published_at": row.published_at,
        "label": row.label,
        "score": float(row.score) if row.score is not None else None,
        "scorer": row.scorer,
        "weight": weight,
    }


def badge_label(labels: list[str], weights: list[float]) -> str | None:
    if not labels:
        return None
    totals = {}
    for label, weight in zip(labels, weights, strict=True):
        totals[label] = totals.get(label, 0.0) + weight
    best = max(totals.values())
    leaders = [label for label, total in totals.items() if np.isclose(total, best)]
    return leaders[0] if len(leaders) == 1 else "neutral"


def stock_sentiment(db: Session, stock: Stock) -> dict:
    """The payload of GET /stocks/{ticker}/sentiment."""
    trading_days = _trading_days(db, stock.ticker)
    as_of = trading_days.iloc[-1] if len(trading_days) else None
    rows = (
        db.query(SentimentScore)
        .filter(SentimentScore.stock_id == stock.id)
        .order_by(SentimentScore.published_at.desc())
        .limit(200)
        .all()
    )
    days = headline_trading_days(
        pd.Series(pd.to_datetime([r.published_at for r in rows], utc=True)), trading_days
    )
    position = {day: i for i, day in enumerate(trading_days)}
    counted, after_close, labels, weights = [], [], [], []
    total_weight = weighted = 0.0
    for row, day in zip(rows, days, strict=True):
        if pd.isna(day):
            if len(after_close) < LISTED_AFTER_CLOSE:
                after_close.append(_headline_payload(row, None))
            continue
        weight = float(news_weights([len(trading_days) - 1 - position[day]])[0])
        # Business Recorder is shown but never counted: it is not a training source
        if weight == 0 or row.source not in TRAINING_SOURCES or row.score is None:
            if weight > 0:
                counted.append(_headline_payload(row, None))
            continue
        counted.append(_headline_payload(row, weight))
        labels.append(row.label)
        weights.append(weight)
        total_weight += weight
        weighted += weight * float(row.score)

    return {
        "ticker": stock.ticker,
        "as_of_date": as_of.date() if as_of is not None else None,
        "label": badge_label(labels, weights),
        "score": weighted / total_weight if total_weight else None,
        "news_weight": total_weight,
        "counted_headlines": len(labels),
        "window_trading_days": NEWS_WINDOW_DAYS,
        "half_life_trading_days": NEWS_HALF_LIFE_DAYS,
        "headlines": counted,
        "after_close_headlines": after_close,
        "freshness": source_freshness(db),
    }
