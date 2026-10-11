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
export type LowConfidenceReason =
  'below_threshold' | 'models_disagree' | 'no_edge_over_baseline' | 'sentiment_unavailable';

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
  /**
   * 'used': the forecast read news sentiment; 'unavailable': the news sources were stale, so a
   * price-only forecast was made (PRD FR22); null: the model reads prices only
   */
  sentiment_status: 'used' | 'unavailable' | null;
  evaluation: ModelEvaluation | null;
  /** How many stocks the current model forecasts (also in a `not_covered` 404's detail) */
  covered_stock_count: number;
}

// ---- News sentiment (Phase 4)

export type SentimentLabel = 'positive' | 'negative' | 'neutral';

/** A headline with its link; the article text is never stored or shown. */
export interface SentimentHeadline {
  headline: string;
  source: string;
  source_name: string;
  url: string;
  published_at: string;
  /** null while the headline waits to be scored */
  label: SentimentLabel | null;
  /** FinBERT's probability for `label`; null when VADER scored it or it is not scored yet */
  label_probability: number | null;
  /** Model input P(positive) - P(negative), -1 to +1; not shown in the UI */
  score: number | null;
  scorer: 'finbert' | 'vader' | null;
  /** Share in today's sentiment (decayed weight); null = shown but not counted */
  weight: number | null;
}

export interface SentimentSourceFreshness {
  source: string;
  name: string;
  last_success_at: string | null;
  stale: boolean;
}

export interface StockSentiment {
  ticker: string;
  /** Trading day of the latest stored close; the window ends here */
  as_of_date: string | null;
  /** null when no headline counts */
  label: SentimentLabel | null;
  score: number | null;
  news_weight: number;
  counted_headlines: number;
  window_trading_days: number;
  half_life_trading_days: number;
  /** Inside the window, newest first */
  headlines: SentimentHeadline[];
  /** Published after the last close; they count from the next trading day */
  after_close_headlines: SentimentHeadline[];
  freshness: { stale: boolean; sources: SentimentSourceFreshness[] };
}

/** `detail` of a 404 from GET /stocks/{ticker}/prediction */
export type PredictionUnavailableCode =
  'stock_not_found' | 'not_covered' | 'insufficient_data' | 'not_ready';

// ---- Portfolio (Phase 5). Money and percentages are decimal strings from the API; the
// clients only format them for display and never do arithmetic on them.

export type Money = string;
export type FilerStatus = 'filer' | 'non_filer';

export interface GeneratePortfolioRequest {
  capital: string;
  filer_status: FilerStatus;
  shariah_only: boolean;
  excluded_tickers: string[];
  /** The user's own broker commission in percent; omitted = the PSX minimum */
  commission_pct?: string;
}

export interface PortfolioCharges {
  commission: Money;
  sales_tax: Money;
  cdc_fee: Money;
  psx_trading_fee: Money;
  psx_regulatory_fee: Money;
  secp_levy: Money;
  nccpl_trade_fee: Money;
  nccpl_secp_fee: Money;
  total: Money;
}

export type ChargeKey = Exclude<keyof PortfolioCharges, 'total'>;

export interface ForecastExit {
  price: Money;
  gross: Money;
  charges: PortfolioCharges;
  proceeds: Money;
  gain: Money;
  cgt: Money;
  net_proceeds: Money;
  net_return: Money;
  net_return_pct: string;
}

export interface PortfolioDividends {
  per_share: Money;
  payments: { ex_date: string; amount: Money }[];
  period_start: string;
  period_end: string;
  gross: Money;
  wht_rate_pct: string;
  wht: Money;
  net: Money;
  source: 'yahoo';
}

export interface WhyThisStock {
  rank: number;
  volatility_pct: string;
  forecast_price: Money;
  last_close: Money;
  expected_change_pct: string;
  confidence_score: string;
  low_confidence_reasons: LowConfidenceReason[];
  low_confidence_threshold: number;
  signal: Signal;
  signal_probability: string | null;
  sentiment_label: SentimentLabel | null;
  sentiment_score: string | null;
  counted_headlines: number;
  /** How far the forecast and news moved this weight, in percentage points */
  tilt_effect_pp: string;
}

export interface PortfolioHolding {
  ticker: string;
  name: string;
  sector: string | null;
  shares: number;
  price: Money;
  target_weight_pct: string;
  allocation_pct: string;
  gross: Money;
  charges: PortfolioCharges;
  total_cost: Money;
  break_even_price: Money;
  break_even_change_pct: string;
  round_trip_pct: string;
  forecast_exit: ForecastExit;
  dividends: PortfolioDividends | null;
  why: WhyThisStock;
}

export interface PortfolioRates {
  version: string;
  checked_on: string;
  /** Rate keys whose official source could not be read (shown as "rate not confirmed") */
  unverified: string[];
  not_modelled: string[];
  cgt_non_filer_label: string;
  commission_floor_pct: string;
  commission_max_pct: string;
}

export interface Portfolio {
  id: string;
  status: 'active' | 'archived';
  generated_at: string;
  risk_category: RiskCategory;
  capital: Money;
  filer_status: FilerStatus;
  shariah_only: boolean;
  shariah_list_version: string | null;
  excluded_tickers: string[];
  commission_pct: string;
  model_version: string;
  prices_as_of: string;
  rates: PortfolioRates;
  totals: { gross: Money; charges: Money; cost: Money; idle_cash: Money };
  /** FR24: flagged when the cash could buy more shares but a limit stopped it */
  idle: { amount: Money; flagged: boolean; blocked_by: Record<string, 'stock_cap' | 'sector_cap'> };
  holdings: PortfolioHolding[];
}

export type RollStatus =
  'too_early' | 'not_triggered' | 'no_replacement' | 'costs_exceed_benefit' | 'suggested';

export interface RollHolding {
  ticker: string;
  status: RollStatus;
  trading_days: number;
  holding_return_pct: string;
  benchmark_return_pct: string;
  relative_return_pct: string;
  threshold_pct: string;
  weak_forecast: boolean;
  replacement: { ticker: string; price: Money; expected_change_pct: string } | null;
  sale: { gross: Money; charges_total: Money; cgt: Money; net_proceeds: Money } | null;
  purchase: { shares: number; gross: Money; charges_total: Money } | null;
  switch_cost: Money | null;
  expected_benefit: Money | null;
}

export interface RollCheckResult {
  portfolio_id: string;
  checked_at: string;
  required_trading_days: number;
  benchmark: {
    kind: 'equal_weight_forecast_stocks';
    stock_count: number;
    since: string;
    return_pct: string | null;
  };
  holdings: RollHolding[];
}

export type PortfolioErrorCode =
  | 'risk_profile_required'
  | 'no_active_portfolio'
  | 'capital_below_minimum'
  | 'too_few_eligible_stocks'
  | 'invalid_commission_rate'
  | 'ticker_not_in_portfolio'
  | 'portfolio_archived'
  | 'portfolio_not_found'
  | 'predictions_unavailable';
