import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from integrations.market_data import MarketDataUnavailable
from schemas.stock import PricePointResponse, StockQuote, StockSearchResponse
from services.stock_service import StockService

router = APIRouter(prefix="/stocks", tags=["stocks"], dependencies=[Depends(get_current_user)])

UNAVAILABLE = "Market data is temporarily unavailable. Please try again in a few minutes."

HistoryPeriod = Literal["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]


@router.get("/search", response_model=StockSearchResponse)
def search_stocks(
    q: str = Query("", max_length=60, description="Ticker, company name or sector"),
    db: Session = Depends(get_db),
):
    """Search/browse PSX companies. An empty query lists the whole catalog."""
    return {"results": StockService.search(db, q)}


@router.get("/{ticker}", response_model=StockQuote)
def get_stock_quote(ticker: str, db: Session = Depends(get_db)):
    """Latest quote and key statistics for a PSX ticker (e.g. SYS)."""
    try:
        quote = StockService.get_quote_cached(db, ticker)
    except MarketDataUnavailable as e:
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from e
    if not quote:
        raise HTTPException(status_code=404, detail=f"No market data found for '{ticker}'")
    return quote


@router.get("/{ticker}/history", response_model=list[PricePointResponse])
def get_stock_history(
    ticker: str,
    period: HistoryPeriod = "1y",
    start: datetime.date | None = None,
    end: datetime.date | None = None,
):
    """Daily OHLCV history. Returns an empty list when the stock has no history."""
    try:
        return StockService.get_history_cached(ticker, period=period, start=start, end=end)
    except MarketDataUnavailable as e:
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from e
