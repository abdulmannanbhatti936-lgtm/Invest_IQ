// Shared domain types. These mirror the FastAPI Pydantic schemas in
// services/api/schemas — keep them in sync (see /docs on the running API).

export type UserRole = 'user' | 'admin';
export type RiskCategory = 'conservative' | 'moderate' | 'aggressive';
export type Signal = 'BUY' | 'SELL' | 'HOLD';
export type Language = 'en' | 'ur';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  created_at: string;
  has_risk_profile: boolean;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// ---- Risk questionnaire (PRD.md FR2). The question set comes from the API
// (GET /users/risk-questionnaire, defined in services/api/services/risk_scoring.py);
// display text for each id/option lives in packages/i18n under onboarding.questions.

export interface RiskQuestion {
  id: string;
  options: string[];
}

/** Question id -> chosen option value. */
export type RiskAnswers = Record<string, string>;

/** Safety caps that can lower the score-based category (services/api/services/risk_scoring.py). */
export type RiskCap = 'short_horizon' | 'sells_on_loss' | 'low_emergency_savings';

export interface RiskProfile {
  id: string;
  user_id: string;
  category: RiskCategory;
  answers: RiskAnswers;
  updated_at: string;
  score: number;
  /** Caps that lowered the category; empty when the score alone decided it. */
  caps_applied: RiskCap[];
}

export interface OnboardingProgress {
  answers: RiskAnswers;
  current_step: number;
}

// ---- Stocks

export interface StockSummary {
  ticker: string;
  name: string;
  sector: string | null;
}

export interface StockQuote {
  ticker: string;
  name: string;
  sector: string | null;
  currency: string;
  price: number;
  open: number | null;
  high: number | null;
  low: number | null;
  previous_close: number | null;
  change: number | null;
  change_percent: number | null;
  volume: number;
  timestamp: string;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
  market_cap: number | null;
}

export interface PricePoint {
  timestamp: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  volume: number;
}

export type HistoryPeriod = '1mo' | '3mo' | '6mo' | '1y' | '2y' | '5y' | 'max';

// ---- Predictions

/** This stock's results on the held-out test period (the model never trained on it). */
export interface ModelEvaluation {
  test_start_date: string;
  test_end_date: string;
  test_rows: number;
  directional_accuracy: number | null;
  /** Accuracy of always guessing the most common direction, on the same days */
  baseline_directional_accuracy: number | null;
  baseline_direction: 'up' | 'down';
  /** Forecast RMSE as % of price: the typical size of the forecast's error */
  typical_error_pct: number;
  /** Forecast RMSE / RMSE of "tomorrow = today"; below 1 beats it */
  theil_u: number;
  beats_naive: boolean;
  classifier_accuracy: number;
  classifier_baseline_accuracy: number;
  top_features: string[];
}

/** Why a forecast is flagged low-confidence (PRD FR16). */
export type LowConfidenceReason = 'below_threshold' | 'models_disagree' | 'no_edge_over_baseline';

export interface Prediction {
  ticker: string;
  model_version: string;
  generated_at: string;
  /** Trading date of the close the forecast starts from */
  as_of_date: string | null;
  last_close: number;
  forecast_price: number;
  expected_change_pct: number;
  /** Calibrated probability (0-1) that the forecast direction is right */
  confidence_score: number;
  low_confidence: boolean;
  low_confidence_reasons: LowConfidenceReason[];
  low_confidence_threshold: number;
  /** Random Forest buy/sell/hold signal and its class probability */
  signal: Signal;
  signal_probability: number | null;
  models_agree: boolean;
  evaluation: ModelEvaluation | null;
}

/** `detail` of a 404 from GET /stocks/{ticker}/prediction */
export type PredictionUnavailableCode =
  | 'stock_not_found'
  | 'not_covered'
  | 'insufficient_data'
  | 'not_ready';
