from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.deps import get_current_user
from integrations.market_data import MarketDataClient
from ml.inference import models_agree
from models.stock import PricePoint, Stock
from schemas.prediction import PredictionResponse
from services.prediction_service import latest_prediction, model_evaluation

router = APIRouter(prefix="/stocks", tags=["predictions"], dependencies=[Depends(get_current_user)])


@router.get(
    "/{ticker}/prediction",
    response_model=PredictionResponse,
    responses={
        404: {"description": "detail.code is 'stock_not_found', 'insufficient_data' or 'not_ready'"}
    },
)
def get_stock_prediction(ticker: str, db: Session = Depends(get_db)):
    """
    Latest stored forecast for a stock. Predictions are produced by the
    `run_predictions` background job from saved model artifacts; this endpoint
    only reads them, so it is fast and never trains a model.
    """
    symbol = MarketDataClient.normalize_ticker(ticker)
    stock = db.query(Stock).filter(Stock.ticker == symbol).first()
    if not stock:
        raise HTTPException(
            status_code=404,
            detail={"code": "stock_not_found", "message": f"{symbol} is not a tracked stock"},
        )

    prediction = latest_prediction(db, stock)
    if not prediction:
        history_days = db.query(PricePoint).filter(PricePoint.stock_id == stock.id).count()
        if history_days < settings.MIN_HISTORY_DAYS:
            # PRD.md FR10: say so plainly instead of guessing
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "insufficient_data",
                    "message": (
                        "Insufficient data for a reliable prediction "
                        f"({history_days} days of history)."
                    ),
                },
            )
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_ready",
                "message": "No prediction has been generated for this stock yet.",
            },
        )

    last_close = float(prediction.last_close)
    forecast = float(prediction.forecast_price)
    confidence = float(prediction.confidence_score)
    expected_return = forecast / last_close - 1
    agree = models_agree(prediction.signal, expected_return)
    return {
        "ticker": stock.ticker,
        "model_version": prediction.model_version,
        "generated_at": prediction.generated_at,
        "last_close": last_close,
        "forecast_price": forecast,
        "expected_change_pct": expected_return * 100,
        "signal": prediction.signal,
        "confidence_score": confidence,
        "low_confidence": confidence < settings.LOW_CONFIDENCE_THRESHOLD or not agree,
        "low_confidence_threshold": settings.LOW_CONFIDENCE_THRESHOLD,
        "models_agree": agree,
        "evaluation": model_evaluation(stock.ticker, prediction.model_version),
    }
