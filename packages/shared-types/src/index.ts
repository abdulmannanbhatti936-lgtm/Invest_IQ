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

// ---- Risk questionnaire (PRD.md FR2). Mirrors services/api/services/risk_scoring.py;
// display text for each id/option lives in packages/i18n under onboarding.questions.

export const RISK_QUESTIONS = [
  { id: 'age_band', options: ['under_30', '30_to_50', 'over_50'] },
  { id: 'income_stability', options: ['very_stable', 'somewhat_stable', 'unstable'] },
  { id: 'investment_horizon', options: ['long', 'medium', 'short'] },
  { id: 'loss_tolerance', options: ['buy_more', 'hold', 'sell'] },
  { id: 'market_experience', options: ['experienced', 'some', 'none'] },
  { id: 'investment_goal', options: ['growth', 'income', 'preservation'] },
  { id: 'emergency_savings', options: ['over_6_months', '3_to_6_months', 'under_3_months'] },
] as const;

export type RiskQuestionId = (typeof RISK_QUESTIONS)[number]['id'];
export type RiskAnswers = Partial<Record<RiskQuestionId, string>>;

export interface RiskProfile {
  id: string;
  user_id: string;
  category: RiskCategory;
  answers: RiskAnswers;
  updated_at: string;
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
  pe_ratio: number | null;
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

export interface ModelEvaluation {
  test_start_date: string;
  test_end_date: string;
  lstm_rmse_pct: number;
  lstm_directional_accuracy: number;
  classifier_accuracy: number;
  classifier_baseline_accuracy: number;
  top_features: string[];
}

export interface Prediction {
  ticker: string;
  model_version: string;
  generated_at: string;
  last_close: number;
  forecast_price: number;
  expected_change_pct: number;
  signal: Signal;
  confidence_score: number;
  low_confidence: boolean;
  low_confidence_threshold: number;
  models_agree: boolean;
  evaluation: ModelEvaluation | null;
}

/** `detail` of a 404 from GET /stocks/{ticker}/prediction */
export type PredictionUnavailableCode = 'stock_not_found' | 'insufficient_data' | 'not_ready';
