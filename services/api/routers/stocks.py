from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
import datetime
from schemas.stock import StockQuote, PricePointResponse, StockSearchResponse
from services.stock_service import StockService
from core.deps import get_current_user

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
