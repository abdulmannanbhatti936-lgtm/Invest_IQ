import uuid

from sqlalchemy import (
    BigInteger,
    Column,
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

    # Relationship back to stock
    stock = relationship("Stock", back_populates="price_points")
