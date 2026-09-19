from pydantic import BaseModel, Field
from typing import List, Optional
import datetime

class StockQuote(BaseModel):
    ticker: str
    name: str
    sector: str
    price: float
    volume: int
    timestamp: datetime.datetime

class PricePointResponse(BaseModel):
    timestamp: datetime.datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

class StockSearchResponse(BaseModel):
    # Search is simplified for now: if quote exists, it returns a list of 1.
    results: List[StockQuote]
