from pydantic import BaseModel

from schemas.types import UTCDateTime


class ModelEvaluation(BaseModel):
    test_start_date: str
    test_end_date: str
    lstm_rmse_pct: float
    lstm_directional_accuracy: float
    classifier_accuracy: float
    classifier_baseline_accuracy: float
    top_features: list[str]


class PredictionResponse(BaseModel):
    ticker: str
    model_version: str
    generated_at: UTCDateTime
    last_close: float
    forecast_price: float
    expected_change_pct: float
    signal: str  # BUY / SELL / HOLD
    confidence_score: float  # classifier probability of `signal`, 0-1
    low_confidence: bool  # PRD.md FR16
    low_confidence_threshold: float
    models_agree: bool  # LSTM forecast direction matches the classifier signal
    evaluation: ModelEvaluation | None = None
