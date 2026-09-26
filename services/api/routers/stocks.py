import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.deps import get_current_user
from schemas.stock import PricePointResponse, StockQuote, StockSearchResponse
from schemas.prediction import PredictionResponse
from services.stock_service import StockService
from core.database import get_db
from sqlalchemy.orm import Session
from models.prediction import Prediction
from models.stock import Stock

router = APIRouter()

@router.get("/search", response_model=StockSearchResponse)
def search_stocks(q: str = Query(..., min_length=1), current_user=Depends(get_current_user)):
    """
    Search for a stock ticker. For now, since we rely on yfinance directly, 
    we will query it as a quote and return a 1-item list if found.
    """
    quote = StockService.get_quote_cached(q)
    if quote:
        return {"results": [quote]}
    return {"results": []}

@router.get("/{ticker}", response_model=StockQuote)
def get_stock_quote(ticker: str, current_user=Depends(get_current_user)):
    """
    Get the latest quote and info for a specific ticker.
    """
    quote = StockService.get_quote_cached(ticker)
    if not quote:
        raise HTTPException(status_code=404, detail="Stock not found or data unavailable")
    return quote

@router.get("/{ticker}/history", response_model=List[PricePointResponse])
def get_stock_history(
    ticker: str, 
    period: str = "1y",
    start: Optional[datetime.date] = None,
    end: Optional[datetime.date] = None,
    current_user=Depends(get_current_user)
):
    """
    Get historical price points for a specific ticker.
    """
    history = StockService.get_history_cached(ticker, period=period, start=start, end=end)
    if not history:
        raise HTTPException(status_code=404, detail="Stock history not found or data unavailable")
    return history

@router.get("/{ticker}/prediction", response_model=PredictionResponse)
def get_stock_prediction(
    ticker: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the latest prediction (LSTM + Base models) for a specific ticker.
    """
    stock = db.query(Stock).filter(Stock.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
        
    prediction = db.query(Prediction).filter(Prediction.stock_id == stock.id).order_by(Prediction.timestamp.desc()).first()
    if not prediction:
        raise HTTPException(status_code=404, detail="No prediction available for this stock yet")
        
    return prediction
