// Run with: npm test (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  capitalError,
  cleanCapital,
  commissionError,
  errorMessageKey,
  isNegative,
  lowCapitalFrom,
} from './portfolioView.ts';

test('negative values are recognised from the string', () => {
  assert.equal(isNegative('-35.13'), true);
  assert.equal(isNegative('-0.00'), false);
  assert.equal(isNegative('0'), false);
});

test('capital must be a positive amount with at most two decimals', () => {
  assert.equal(capitalError(''), 'portfolio.form.capitalRequired');
  assert.equal(capitalError('abc'), 'portfolio.form.capitalInvalid');
  assert.equal(capitalError('0'), 'portfolio.form.capitalInvalid');
  assert.equal(capitalError('100.123'), 'portfolio.form.capitalInvalid');
  assert.equal(capitalError('100,000'), null);
  assert.equal(cleanCapital(' 100,000.50 '), '100000.50');
});

test('the optional broker commission must be a percentage', () => {
  assert.equal(commissionError(''), null);
  assert.equal(commissionError('0.25'), null);
  assert.equal(commissionError('0.2x'), 'portfolio.form.commissionInvalid');
  assert.equal(commissionError('0.1234'), 'portfolio.form.commissionInvalid');
});

test('the low-capital explanation is read from the API detail', () => {
  const detail = {
    code: 'capital_below_minimum',
    minimum_capital: '1500',
    min_holdings: 5,
    max_stock_weight_pct: '20.00',
    risk_category: 'moderate',
    prices_as_of: '2026-10-07',
  };
  assert.deepEqual(lowCapitalFrom(detail), {
    minimumCapital: '1500',
    minHoldings: 5,
    maxStockWeightPct: '20',
    riskCategory: 'moderate',
    pricesAsOf: '2026-10-07',
  });
  assert.equal(lowCapitalFrom({ code: 'too_few_eligible_stocks' }), null);
  assert.equal(lowCapitalFrom(null), null);
});

test('API error codes map to messages, unknown ones to the generic one', () => {
  assert.equal(errorMessageKey('too_few_eligible_stocks'), 'portfolio.error.tooFewStocks');
  assert.equal(errorMessageKey('something_new'), 'common.errorGeneric');
  assert.equal(errorMessageKey(null), 'common.errorGeneric');
});
