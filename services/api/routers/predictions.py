from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.deps import get_current_user
from integrations.market_data import MarketDataClient
from ml.inference import ModelNotFoundError, load_bundle
from models.stock import PricePoint, Stock
from schemas.prediction import PredictionResponse
from services.prediction_service import (
    MODELS_DISAGREE,
    latest_prediction,
    low_confidence_reasons,
    model_evaluation,
)
from services.stock_service import SERVED

router = APIRouter(prefix="/stocks", tags=["predictions"], dependencies=[Depends(get_current_user)])


def _unavailable(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": code, "message": message})


@router.get(
    "/{ticker}/prediction",
    response_model=PredictionResponse,
    responses={
        404: {
            "description": (
                "detail.code is 'stock_not_found', 'not_covered', 'insufficient_data' "
                "or 'not_ready'"
            )
        }
    },
)
def get_stock_prediction(ticker: str, db: Session = Depends(get_db)):
    """
    Latest stored forecast from the current model. Forecasts are produced by the
    `run_predictions` background job from saved model artifacts; this endpoint only reads
    them, so it is fast and never trains a model.
    """
    symbol = MarketDataClient.normalize_ticker(ticker)
    stock = db.query(Stock).filter(Stock.ticker == symbol).first()
    if not stock:
        raise _unavailable("stock_not_found", f"{symbol} is not a tracked stock")

    try:
        bundle = load_bundle(settings.MODEL_DIR)
    except ModelNotFoundError:
        bundle = None
    covered = bundle.covers(symbol) if bundle else symbol in settings.tracked_tickers
    if not covered:
        raise _unavailable("not_covered", f"There is no forecast for {symbol} yet.")

    prediction = latest_prediction(db, stock, bundle.version) if bundle else None
    if not prediction:
        history_days = db.query(PricePoint).filter(PricePoint.stock_id == stock.id, SERVED).count()
        if history_days < settings.MIN_HISTORY_DAYS:
            # PRD.md FR10: say so plainly instead of guessing
            raise _unavailable(
                "insufficient_data",
                f"Insufficient data for a reliable prediction ({history_days} days of history).",
            )
        raise _unavailable("not_ready", "No prediction has been generated for this stock yet.")

    last_close = float(prediction.last_close)
    forecast = float(prediction.forecast_price)
    reasons = low_confidence_reasons(prediction, bundle, stock.ticker)
    return {
        "ticker": stock.ticker,
        "model_version": prediction.model_version,
        "generated_at": prediction.generated_at,
        "as_of_date": prediction.as_of_date,
        "last_close": last_close,
        "forecast_price": forecast,
        "expected_change_pct": (forecast / last_close - 1) * 100,
        "confidence_score": float(prediction.confidence_score),
        "low_confidence": bool(reasons),
        "low_confidence_reasons": reasons,
        "low_confidence_threshold": settings.LOW_CONFIDENCE_THRESHOLD,
        "signal": prediction.signal,
        "signal_probability": (
            float(prediction.signal_probability)
            if prediction.signal_probability is not None
            else None
        ),
        "models_agree": MODELS_DISAGREE not in reasons,
        "evaluation": model_evaluation(bundle, stock.ticker),
    }
