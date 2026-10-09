// Run with: npm test (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { Prediction } from '@investiq/shared-types';
import {
  confidenceLevel,
  forecastBand,
  forecastDirection,
  unavailableMessageKey,
} from './predictionView.ts';

const prediction = (overrides: Partial<Prediction> = {}): Prediction => ({
  ticker: 'HBL',
  model_version: 'lstm-rf-20261009T222331Z',
  generated_at: '2026-10-10T00:00:00Z',
  as_of_date: '2026-10-07',
  last_close: 302.02,
  forecast_price: 302.17,
  expected_change_pct: 0.05,
  confidence_score: 0.49,
  low_confidence: true,
  low_confidence_reasons: ['below_threshold'],
  low_confidence_threshold: 0.6,
  signal: 'HOLD',
  signal_probability: 0.5,
  models_agree: true,
  evaluation: {
    test_start_date: '2026-01-14',
    test_end_date: '2026-10-06',
    test_rows: 175,
    directional_accuracy: 0.49,
    baseline_directional_accuracy: 0.54,
    baseline_direction: 'down',
    typical_error_pct: 2.5,
    theil_u: 1.027,
    beats_naive: false,
    classifier_accuracy: 0.38,
    classifier_baseline_accuracy: 0.47,
    top_features: ['volatility_20d', 'range_pct', 'bb_width'],
  },
  ...overrides,
});

test('confidence level: below the threshold is low, then medium up to 75%, then high', () => {
  assert.equal(confidenceLevel(0.59, 0.6), 'low');
  assert.equal(confidenceLevel(0.6, 0.6), 'medium');
  assert.equal(confidenceLevel(0.749, 0.6), 'medium');
  assert.equal(confidenceLevel(0.75, 0.6), 'high');
});

test('forecast direction: changes that round to 0.0% read as flat', () => {
  assert.equal(forecastDirection(0.04), 'flat');
  assert.equal(forecastDirection(-0.04), 'flat');
  assert.equal(forecastDirection(0.05), 'up');
  assert.equal(forecastDirection(-0.39), 'down');
});

test('forecast band is the forecast plus or minus the typical test-period error', () => {
  const band = forecastBand(prediction());
  assert.ok(band);
  const [low, high] = band;
  assert.ok(Math.abs(low - 302.17 * 0.975) < 1e-9);
  assert.ok(Math.abs(high - 302.17 * 1.025) < 1e-9);
  assert.equal(forecastBand(prediction({ evaluation: null })), null);
});

test('unavailable codes map to their message; unknown codes read as not covered', () => {
  assert.equal(unavailableMessageKey('insufficient_data'), 'prediction.insufficientData');
  assert.equal(unavailableMessageKey('not_ready'), 'prediction.notReady');
  assert.equal(unavailableMessageKey('not_covered'), 'prediction.notCovered');
  assert.equal(unavailableMessageKey(undefined), 'prediction.notCovered');
});
