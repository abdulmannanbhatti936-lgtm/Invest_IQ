"""
Generates and reads stock predictions. Generation runs in the Celery worker
(`run_predictions`), never in the request cycle (Rules.md §3.5).
"""

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from core.config import settings
from ml.features import build_feature_frame, price_points_to_frame
from ml.inference import ModelNotFoundError, load_bundle, predict_next_day
from models.prediction import Prediction
from models.sentiment import NewsSentiment
from models.stock import PricePoint, Stock

logger = logging.getLogger(__name__)


class InsufficientHistoryError(Exception):
    def __init__(self, ticker: str, rows: int):
        super().__init__(f"{ticker} has {rows} days of history; {settings.MIN_HISTORY_DAYS} needed")
        self.rows = rows


def _decimal(value: float, places: str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places))


def generate_prediction(db: Session, stock: Stock) -> Prediction:
    """Run the latest saved model for one stock and store the result."""
    points = (
        db.query(PricePoint)
        .filter(PricePoint.stock_id == stock.id)
        .order_by(PricePoint.timestamp.asc())
        .all()
    )
    if len(points) < settings.MIN_HISTORY_DAYS:
        raise InsufficientHistoryError(stock.ticker, len(points))

    sentiments = db.query(NewsSentiment).filter(NewsSentiment.stock_id == stock.id).all()
    frame = build_feature_frame(price_points_to_frame(points), sentiments)
    bundle = load_bundle(settings.MODEL_DIR, stock.ticker)
    result = predict_next_day(bundle, frame)

    prediction = Prediction(
        stock_id=stock.id,
        model_version=result["model_version"],
        forecast_price=_decimal(result["forecast_price"], "0.0001"),
        last_close=_decimal(result["last_close"], "0.0001"),
        signal=result["signal"],
        confidence_score=_decimal(result["confidence"], "0.0001"),
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def latest_prediction(db: Session, stock: Stock) -> Prediction | None:
    return (
        db.query(Prediction)
        .filter(Prediction.stock_id == stock.id)
        .order_by(Prediction.generated_at.desc())
        .first()
    )


def model_evaluation(ticker: str, version: str) -> dict | None:
    """Headline test-set metrics of the model that produced a prediction."""
    try:
        meta = load_bundle(settings.MODEL_DIR, ticker, version).metadata
    except (ModelNotFoundError, FileNotFoundError):
        return None
    lstm = meta["lstm"]["test_metrics"]
    rf = meta["random_forest"]["test_metrics"]
    return {
        "test_start_date": meta["data"]["val_end_date"],
        "test_end_date": meta["data"]["date_end"],
        "lstm_rmse_pct": lstm["rmse_pct_of_price"],
        "lstm_directional_accuracy": lstm["directional_accuracy"],
        "classifier_accuracy": rf["accuracy"],
        "classifier_baseline_accuracy": rf["baseline_majority_class_accuracy"],
        "top_features": [f["feature"] for f in meta["random_forest"]["feature_importance"][:3]],
    }
