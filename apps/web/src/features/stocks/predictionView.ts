import type { Prediction, PredictionUnavailableCode } from '@investiq/shared-types';

export type ConfidenceLevel = 'low' | 'medium' | 'high';
export type ForecastDirection = 'up' | 'down' | 'flat';

// Top of the meter's middle segment; the bottom is the API's low-confidence threshold
const HIGH_CONFIDENCE_FROM = 0.75;

// A forecast change smaller than this rounds to 0.0% and is described as "almost no change"
const FLAT_CHANGE_PCT = 0.05;

export const confidenceLevel = (value: number, threshold: number): ConfidenceLevel =>
  value < threshold ? 'low' : value < HIGH_CONFIDENCE_FROM ? 'medium' : 'high';

export const forecastDirection = (changePct: number): ForecastDirection =>
  Math.abs(changePct) < FLAT_CHANGE_PCT ? 'flat' : changePct > 0 ? 'up' : 'down';

/**
 * Range drawn around the forecast: the forecast plus or minus this model's typical error
 * (RMSE as % of price) on this stock's test period. The Monte-Carlo dropout spread behind
 * the confidence score is far narrower than the real error, so it is not used for the band.
 */
export const forecastBand = (prediction: Prediction): [number, number] | null => {
  if (!prediction.evaluation) return null;
  const error = prediction.evaluation.typical_error_pct / 100;
  return [prediction.forecast_price * (1 - error), prediction.forecast_price * (1 + error)];
};

const UNAVAILABLE_KEYS: Partial<Record<PredictionUnavailableCode, string>> = {
  insufficient_data: 'prediction.insufficientData',
  not_ready: 'prediction.notReady',
};

/** i18n key for a 404 from the prediction endpoint; anything else reads as "not covered". */
export const unavailableMessageKey = (code: string | null | undefined): string =>
  UNAVAILABLE_KEYS[code as PredictionUnavailableCode] ?? 'prediction.notCovered';
