from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import datetime

from core.database import Base

class NewsSentiment(Base):
    __tablename__ = "news_sentiments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    headline = Column(String, nullable=False)
    sentiment_score = Column(Float, nullable=False)  # e.g., -1.0 to 1.0
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    stock = relationship("Stock", back_populates="sentiments")
