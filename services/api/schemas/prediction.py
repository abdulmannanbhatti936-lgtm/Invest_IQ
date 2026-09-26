import datetime
from pydantic import BaseModel
from uuid import UUID

class PredictionResponse(BaseModel):
    stock_id: UUID
    predicted_price: float
    signal: str
    confidence_score: float
    model_version: str
    timestamp: datetime.datetime
    
    class Config:
        from_attributes = True
