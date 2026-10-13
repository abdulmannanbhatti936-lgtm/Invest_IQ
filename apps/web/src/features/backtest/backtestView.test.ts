// Run with: npm test (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { BacktestUniverse } from '@investiq/shared-types';
import {
  chartRows,
  errorMessageKey,
  gapPp,
  isLoss,
  maxYearsFor,
  mixProblems,
  mixTotal,
  ratioToPct,
  roundDecimal,
  yearOptions,
} from './backtestView.ts';

test('fractions become percent strings rounded half up, without float drift', () => {
  // The hand-worked fixture's figures (Phase 6)
  assert.equal(ratioToPct('0.235491'), '23.55');
  assert.equal(ratioToPct('-0.011903'), '-1.19');
  assert.equal(ratioToPct('0.274827', 4), '27.4827');
  assert.equal(ratioToPct('2.240446'), '224.04');
  // A float would give 0.0125 * 100 = 1.2499999...; the string shift rounds the half up
  assert.equal(ratioToPct('0.000125', 3), '0.013');
  assert.equal(ratioToPct('-0.000125', 3), '-0.013');
  assert.equal(ratioToPct('0'), '0.00');
});

test('Sharpe ratios are rounded as decimal strings', () => {
  assert.equal(roundDecimal('1.325222'), '1.33');
  assert.equal(roundDecimal('1.167685'), '1.17');
  assert.equal(roundDecimal('-0.005'), '-0.01');
});

test('the hindsight gap is the difference in percentage points', () => {
  assert.equal(gapPp('2.240446', '2.242818'), '-0.24');
  assert.equal(gapPp('0.30', '0.25'), '5.00');
});

test('losses are recognised from the string', () => {
  assert.equal(isLoss('-0.000001'), true);
  assert.equal(isLoss('0.000000'), false);
  assert.equal(isLoss(null), false);
});

test('year choices run from three to the history available', () => {
  assert.deepEqual(yearOptions(3, 5), [3, 4, 5]);
  assert.deepEqual(yearOptions(3, 2), []);
  assert.deepEqual(yearOptions(3, null), []);
});

const UNIVERSE: BacktestUniverse = {
  latest_date: '2026-10-09',
  min_years: 3,
  max_years: 5,
  stocks: [
    { ticker: 'HBL', name: 'HBL', sector: 'Banks', first_date: '2021-10-08', max_years: 5 },
    { ticker: 'NEW', name: 'New', sector: 'X', first_date: '2022-11-01', max_years: 3 },
  ],
  left_out: [],
};

test('a mix can only go as far back as its shortest history', () => {
  assert.equal(maxYearsFor(UNIVERSE, ['HBL', 'NEW']), 3);
  assert.equal(maxYearsFor(UNIVERSE, ['HBL']), 5);
  assert.equal(maxYearsFor(UNIVERSE, ['HBL', 'FHAM']), null);
  assert.equal(maxYearsFor(UNIVERSE, []), null);
});

test('weights must be valid and total exactly 100', () => {
  const rows = [
    { ticker: 'A', weight: '33.33' },
    { ticker: 'B', weight: '33.33' },
    { ticker: 'C', weight: '33.34' },
  ];
  assert.equal(mixTotal(rows), '100.00');
  assert.deepEqual(mixProblems(rows), []);
  assert.deepEqual(mixProblems([{ ticker: 'A', weight: '60' }]), ['backtest.mix.total']);
  assert.deepEqual(mixProblems([{ ticker: 'A', weight: '100.001' }]), [
    'backtest.mix.weightInvalid',
  ]);
  assert.deepEqual(mixProblems([{ ticker: 'A', weight: '0' }]), ['backtest.mix.weightInvalid']);
});

test('a mix needs a stock in every row and no stock twice', () => {
  assert.deepEqual(mixProblems([{ ticker: '', weight: '100' }]), ['backtest.mix.needStock']);
  assert.deepEqual(
    mixProblems([
      { ticker: 'A', weight: '50' },
      { ticker: 'A', weight: '50' },
    ]),
    ['backtest.mix.duplicate'],
  );
});

test('API error codes map to messages, with a generic fallback', () => {
  assert.equal(errorMessageKey('insufficient_history'), 'backtest.error.insufficientHistory');
  assert.equal(errorMessageKey('weights_not_100'), 'backtest.mix.total');
  assert.equal(errorMessageKey('something_new'), 'common.errorGeneric');
  assert.equal(errorMessageKey(null), 'common.errorGeneric');
});

test('chart rows carry only the lines that exist', () => {
  const rows = chartRows([
    {
      date: '2023-10-09',
      portfolio: '100000.00',
      start_date_rules: null,
      benchmark: '100000.00',
      kse100: null,
    },
  ]);
  assert.deepEqual(rows, [{ date: '2023-10-09', portfolio: 100000, benchmark: 100000 }]);
});
