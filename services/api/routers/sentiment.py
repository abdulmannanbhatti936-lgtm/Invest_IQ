from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.deps import get_current_user
from integrations.market_data import MarketDataClient
from models.stock import Stock
from schemas.sentiment import StockSentimentResponse
from services.sentiment_service import stock_sentiment

router = APIRouter(prefix="/stocks", tags=["sentiment"], dependencies=[Depends(get_current_user)])


@router.get(
    "/{ticker}/sentiment",
    response_model=StockSentimentResponse,
    responses={
        404: {
            "description": (
                "detail.code is 'stock_not_found' or 'not_covered' (news is collected for "
                "the stocks the model forecasts; detail.covered_stock_count)"
            )
        }
    },
)
def get_stock_sentiment(ticker: str, db: Session = Depends(get_db)):
    """
    News sentiment for a stock and the headlines behind it (PRD.md FR21). Headlines are
    collected and scored by the `scrape_news_sentiment` job; this endpoint only reads them.
    """
    symbol = MarketDataClient.normalize_ticker(ticker)
    stock = db.query(Stock).filter(Stock.ticker == symbol).first()
    if not stock:
        raise HTTPException(
            status_code=404,
            detail={"code": "stock_not_found", "message": f"{symbol} is not a tracked stock"},
        )
    if symbol not in settings.tracked_tickers:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_covered",
                "message": f"News sentiment is not collected for {symbol}.",
                "covered_stock_count": len(settings.tracked_tickers),
            },
        )
    return stock_sentiment(db, stock)
