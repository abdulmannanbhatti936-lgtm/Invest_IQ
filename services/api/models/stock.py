import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    sector = Column(String, nullable=True)
    # From the data provider; market cap = latest stored close x shares (PRD.md FR8)
    shares_outstanding = Column(BigInteger, nullable=True)

    # Relationship to price points
    price_points = relationship("PricePoint", back_populates="stock", cascade="all, delete-orphan")
    sentiments = relationship("NewsSentiment", back_populates="stock", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="stock", cascade="all, delete-orphan")
    splits = relationship("StockSplit", back_populates="stock", cascade="all, delete-orphan")
    dividends = relationship("StockDividend", back_populates="stock", cascade="all, delete-orphan")


class PricePoint(Base):
    __tablename__ = "price_points"
    __table_args__ = (UniqueConstraint("stock_id", "timestamp", name="uq_price_points_stock_ts"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_id = Column(
        UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    open = Column(Numeric, nullable=True)
    high = Column(Numeric, nullable=True)
    low = Column(Numeric, nullable=True)
    close = Column(Numeric, nullable=False)
    volume = Column(BigInteger, nullable=True)

    # The columns above are the provider's raw values and are never rewritten by our own
    # processing. Served prices are raw / split_factor and volume x split_factor
    # (services/split_adjustment.py); a bar with a quality_flag is left out.
    split_factor = Column(Numeric, nullable=False, default=1, server_default="1")
    quality_flag = Column(String, nullable=True)
    adjustment_version = Column(String, nullable=True)

    # Relationship back to stock
    stock = relationship("Stock", back_populates="price_points")


class StockSplit(Base):
    """A provider split event and InvestIQ's decision about the history before it."""

    __tablename__ = "stock_splits"
    __table_args__ = (
        UniqueConstraint("stock_id", "split_date", name="uq_stock_splits_stock_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_id = Column(
        UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    split_date = Column(Date, nullable=False)
    ratio = Column(Numeric, nullable=False)  # new shares per old share
    history_adjusted = Column(Boolean, nullable=True)
    decision_note = Column(String, nullable=True)
    method_version = Column(String, nullable=True)

    stock = relationship("Stock", back_populates="splits")


class StockDividend(Base):
    """A provider dividend event and InvestIQ's decision about adjusting for it."""

    __tablename__ = "stock_dividends"
    __table_args__ = (
        UniqueConstraint("stock_id", "ex_date", name="uq_stock_dividends_stock_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_id = Column(
        UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ex_date = Column(Date, nullable=False)
    amount = Column(Numeric, nullable=False)  # Rs. per share, split-adjusted by the provider
    source = Column(String, nullable=False, default="yahoo", server_default="yahoo")

    # Set by services/dividend_adjustment.py from the served closes around the ex-date.
    # Only the model's training/inference series uses the factor; served prices never do.
    previous_close = Column(Numeric, nullable=True)
    ex_close = Column(Numeric, nullable=True)
    adjustment_factor = Column(Numeric, nullable=True)  # None: not applied
    review_flag = Column(String, nullable=True)
    method_version = Column(String, nullable=True)

    stock = relationship("Stock", back_populates="dividends")
