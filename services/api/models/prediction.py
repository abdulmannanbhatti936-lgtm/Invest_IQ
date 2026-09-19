from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import datetime
from core.database import Base

class Prediction(Base):
    __tablename__ = "predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    
    predicted_price = Column(Float, nullable=False)
    signal = Column(String, nullable=False) # BUY, SELL, HOLD
    confidence_score = Column(Float, nullable=False) # 0.0 to 1.0
    model_version = Column(String, nullable=False) # e.g. "v1.0-random-forest"
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    # Relationships
    stock = relationship("Stock", back_populates="predictions")
