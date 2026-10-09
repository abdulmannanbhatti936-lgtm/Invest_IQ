import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from schemas.stock import PricePointResponse, StockQuote, StockSearchResponse
from services.stock_service import PriceDataUnavailable, StockNotFound, StockService

router = APIRouter(prefix="/stocks", tags=["stocks"], dependencies=[Depends(get_current_user)])

UNAVAILABLE = "Market data is temporarily unavailable. Please try again in a few minutes."
NOT_FOUND = "'{ticker}' is not a KSE-100 stock tracked by InvestIQ."

HistoryPeriod = Literal["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]

ERROR_RESPONSES = {
    404: {"description": "The ticker is not in the stock universe"},
    503: {"description": "No stored prices yet for this stock (the data refresh has not run)"},
}


@router.get("/search", response_model=StockSearchResponse)
def search_stocks(
    q: str = Query("", max_length=60, description="Ticker, company name or sector"),
    db: Session = Depends(get_db),
):
    """Search/browse KSE-100 companies. An empty query lists the whole universe."""
    return {"results": StockService.search(db, q)}


@router.get("/{ticker}", response_model=StockQuote, responses=ERROR_RESPONSES)
def get_stock_quote(ticker: str, db: Session = Depends(get_db)):
    """Latest stored trading day and key statistics for a PSX ticker (e.g. SYS)."""
    try:
        return StockService.get_quote(db, ticker)
    except StockNotFound as e:
        raise HTTPException(status_code=404, detail=NOT_FOUND.format(ticker=e)) from e
    except PriceDataUnavailable as e:
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from e


@router.get("/{ticker}/history", response_model=list[PricePointResponse], responses=ERROR_RESPONSES)
def get_stock_history(
    ticker: str,
    period: HistoryPeriod = "1y",
    start: datetime.date | None = None,
    end: datetime.date | None = None,
    db: Session = Depends(get_db),
):
    """Stored daily OHLCV, oldest first. `start`/`end` are PSX trading dates."""
    try:
        return StockService.get_history(db, ticker, period=period, start=start, end=end)
    except StockNotFound as e:
        raise HTTPException(status_code=404, detail=NOT_FOUND.format(ticker=e)) from e
    except PriceDataUnavailable as e:
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from e
