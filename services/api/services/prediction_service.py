"""
Generates and reads stock predictions. Generation runs in the Celery worker
(`run_predictions`), never in the request cycle (Rules.md §3.5).
"""

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from core.config import settings
from ml.dataset import dividend_adjusted, served_frame
from ml.features import build_feature_frame
from ml.inference import ModelBundle, load_bundle, models_agree, predict_next_day
from models.prediction import Prediction
from models.stock import Stock

logger = logging.getLogger(__name__)

# Why a forecast is flagged low-confidence (PRD.md FR16, rules approved 2026-10-10)
BELOW_THRESHOLD = "below_threshold"
MODELS_DISAGREE = "models_disagree"
NO_EDGE_OVER_BASELINE = "no_edge_over_baseline"


class InsufficientHistoryError(Exception):
    def __init__(self, ticker: str, rows: int):
        super().__init__(f"{ticker} has {rows} days of history; {settings.MIN_HISTORY_DAYS} needed")
        self.rows = rows


class StockNotCoveredError(Exception):
    """The current model was not trained or tested on this stock, so it gets no forecast."""


def _decimal(value: float, places: str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places))


def generate_prediction(db: Session, stock: Stock, bundle: ModelBundle | None = None) -> Prediction:
    """
    Run the current model for one stock and store the result. The model sees the same
    series it was trained on: served bars only (split-adjusted, flagged bars left out),
    dividend-adjusted backwards (ml/dataset.py).
    """
    bundle = bundle or load_bundle(settings.MODEL_DIR)
    if not bundle.covers(stock.ticker):
        raise StockNotCoveredError(f"{stock.ticker} is not covered by {bundle.version}")
    frame = served_frame(db, stock)
    if len(frame) < settings.MIN_HISTORY_DAYS:
        raise InsufficientHistoryError(stock.ticker, len(frame))

    result = predict_next_day(bundle, build_feature_frame(dividend_adjusted(frame)))
    prediction = Prediction(
        stock_id=stock.id,
        model_version=result["model_version"],
        forecast_price=_decimal(result["forecast_price"], "0.0001"),
        last_close=_decimal(result["last_close"], "0.0001"),
        confidence_score=_decimal(result["confidence"], "0.0001"),
        signal=result["signal"],
        signal_probability=_decimal(result["signal_probability"], "0.0001"),
        as_of_date=result["as_of"],
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def latest_prediction(db: Session, stock: Stock, model_version: str) -> Prediction | None:
    """The newest forecast from the current model; older models' rows are history only."""
    return (
        db.query(Prediction)
        .filter(Prediction.stock_id == stock.id, Prediction.model_version == model_version)
        .order_by(Prediction.generated_at.desc())
        .first()
    )


def low_confidence_reasons(prediction: Prediction, bundle: ModelBundle, ticker: str) -> list[str]:
    reasons = []
    if float(prediction.confidence_score) < settings.LOW_CONFIDENCE_THRESHOLD:
        reasons.append(BELOW_THRESHOLD)
    expected_return = float(prediction.forecast_price) / float(prediction.last_close) - 1
    if not models_agree(prediction.signal, expected_return):
        reasons.append(MODELS_DISAGREE)
    evaluation = bundle.ticker_evaluation(ticker)
    if evaluation is None or not evaluation["beats_naive"]:
        reasons.append(NO_EDGE_OVER_BASELINE)
    return reasons


def model_evaluation(bundle: ModelBundle, ticker: str) -> dict | None:
    """This stock's test-period results, shown so a forecast is never taken as fact."""
    evaluation = bundle.ticker_evaluation(ticker)
    if evaluation is None:
        return None
    pooled = bundle.metadata["evaluation"]
    periods = bundle.metadata["data"]["periods"]
    importances = bundle.metadata["random_forest"]["feature_importance"]
    return {
        "test_start_date": periods["test"]["first_date"],
        "test_end_date": periods["test"]["last_date"],
        "test_rows": evaluation["test_rows"],
        "directional_accuracy": evaluation["directional_accuracy"],
        "baseline_directional_accuracy": evaluation["majority_direction_accuracy"],
        "baseline_direction": pooled["baselines"]["majority_direction"]["direction"],
        "typical_error_pct": evaluation["lstm_rmse_pct"],
        "theil_u": evaluation["theil_u"],
        "beats_naive": evaluation["beats_naive"],
        "classifier_accuracy": evaluation["rf_accuracy"],
        "classifier_baseline_accuracy": evaluation["rf_majority_class_accuracy"],
        "top_features": [f["feature"] for f in importances[:3]],
    }
