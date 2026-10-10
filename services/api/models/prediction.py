import datetime
import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database import Base


class Prediction(Base):
    """One forecast for one stock, per Architecture.md §7 and §15.4."""

    __tablename__ = "predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_version = Column(String, nullable=False)

    # LSTM next-day close forecast and the close it was made from
    forecast_price = Column(Numeric(14, 4), nullable=False)
    last_close = Column(Numeric(14, 4), nullable=False)

    # Calibrated probability (0-1) that the LSTM's forecast direction is right
    # (ml/confidence.py). Rows from models before lstm-rf-2026-10-10 stored the RF class
    # probability here; they are kept as history and never served (filtered by version).
    confidence_score = Column(Numeric(5, 4), nullable=False)

    # Random Forest buy/sell/hold signal and its class probability (0-1)
    signal = Column(String, nullable=False)
    signal_probability = Column(Numeric(5, 4), nullable=True)

    # PSX trading date of the close the forecast was made from
    as_of_date = Column(Date, nullable=True)

    # 'used': the forecast read the news inputs; 'unavailable': the news sources were stale,
    # so the model's price-only fallback made it (PRD.md FR22); NULL: a price-only model
    sentiment_status = Column(String, nullable=True)

    generated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
        index=True,
    )

    stock = relationship("Stock", back_populates="predictions")
