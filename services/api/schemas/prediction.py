import datetime
from typing import Literal

from pydantic import BaseModel

from schemas.types import UTCDateTime

LowConfidenceReason = Literal["below_threshold", "models_disagree", "no_edge_over_baseline"]


class ModelEvaluation(BaseModel):
    """This stock's results on the held-out test period."""

    test_start_date: str
    test_end_date: str
    test_rows: int
    directional_accuracy: float | None
    baseline_directional_accuracy: float | None  # always guessing the majority direction
    baseline_direction: Literal["up", "down"]
    typical_error_pct: float  # forecast RMSE as % of price on the test period
    theil_u: float  # forecast RMSE / "tomorrow = today" RMSE; below 1 beats it
    beats_naive: bool
    classifier_accuracy: float
    classifier_baseline_accuracy: float  # always answering the majority class
    top_features: list[str]


class PredictionResponse(BaseModel):
    ticker: str
    model_version: str
    generated_at: UTCDateTime
    as_of_date: datetime.date | None  # trading date of the close the forecast starts from
    last_close: float
    forecast_price: float
    expected_change_pct: float
    confidence_score: float  # calibrated probability that the forecast direction is right
    low_confidence: bool  # PRD.md FR16
    low_confidence_reasons: list[LowConfidenceReason]
    low_confidence_threshold: float
    signal: str  # Random Forest BUY / SELL / HOLD
    signal_probability: float | None
    models_agree: bool  # LSTM forecast direction matches the classifier signal
    evaluation: ModelEvaluation | None = None
    covered_stock_count: int  # how many stocks the current model forecasts
