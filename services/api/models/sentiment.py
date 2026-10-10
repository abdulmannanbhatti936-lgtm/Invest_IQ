import datetime
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class SentimentScore(Base):
    """
    One headline matched to one stock, with its sentiment (Architecture.md §7). Only the
    headline, its source, link and publish time are stored, never the article text
    (decided 2026-10-11). A headline about two stocks is stored once per stock.
    """

    __tablename__ = "sentiment_scores"
    __table_args__ = (
        UniqueConstraint("stock_id", "url", name="uq_sentiment_scores_stock_url"),
        CheckConstraint(
            "label IN ('positive', 'negative', 'neutral')", name="ck_sentiment_scores_label"
        ),
        CheckConstraint("scorer IN ('finbert', 'vader')", name="ck_sentiment_scores_scorer"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source = Column(String, nullable=False)
    url = Column(String, nullable=False)
    headline = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False, index=True)
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # NULL until the scoring step runs. score = P(positive) - P(negative) from FinBERT, or
    # VADER's compound score when the fallback scored it (ml/sentiment.py)
    score = Column(Numeric(5, 4), nullable=True)
    label = Column(String, nullable=True)
    scorer = Column(String, nullable=True)
    scorer_version = Column(String, nullable=True)
    # FinBERT's top class probability, kept even when VADER scored the headline
    finbert_confidence = Column(Numeric(5, 4), nullable=True)

    stock = relationship("Stock", back_populates="sentiments")


class NewsSourceStatus(Base):
    """
    Last attempt and last success per news source. Sentiment is stale when a training
    source has not succeeded for 24 hours (PRD.md FR22, decided 2026-10-11).
    """

    __tablename__ = "news_source_status"

    source = Column(String, primary_key=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    last_new_headlines = Column(Integer, nullable=True)
