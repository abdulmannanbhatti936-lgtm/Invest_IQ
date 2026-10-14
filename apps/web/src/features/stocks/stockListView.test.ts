// Run with: npm test (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { filterRows, nextSort, sectorsOf, sortRows, type ListRow } from './stockListView.ts';

const forecast = (pct: number) => ({
  expectedChangePct: pct,
  confidence: 0.54,
  threshold: 0.6,
  low: true,
  signal: 'HOLD' as const,
});

const rows: ListRow[] = [
  {
    ticker: 'HBL',
    name: 'Habib Bank',
    sector: 'Commercial Banks',
    last_close: 295.76,
    forecast_covered: true,
    forecast: forecast(-0.31),
  },
  {
    ticker: 'ABOT',
    name: 'Abbott',
    sector: 'Pharmaceuticals',
    last_close: 1200,
    forecast_covered: false,
  },
  {
    ticker: 'LUCK',
    name: 'Lucky Cement',
    sector: 'Cement',
    last_close: null,
    forecast_covered: true,
    forecast: forecast(0.8),
  },
];

test('sorts by ticker, sector, last close and forecast change', () => {
  assert.deepEqual(
    sortRows(rows, 'ticker', 'asc').map((r) => r.ticker),
    ['ABOT', 'HBL', 'LUCK'],
  );
  assert.deepEqual(
    sortRows(rows, 'sector', 'asc').map((r) => r.ticker),
    ['LUCK', 'HBL', 'ABOT'],
  );
  assert.deepEqual(
    sortRows(rows, 'close', 'desc').map((r) => r.ticker),
    ['ABOT', 'HBL', 'LUCK'],
  );
  assert.deepEqual(
    sortRows(rows, 'forecast', 'desc').map((r) => r.ticker),
    ['LUCK', 'HBL', 'ABOT'],
  );
});

test('stocks without a close or a forecast stay at the bottom in both directions', () => {
  assert.equal(sortRows(rows, 'close', 'asc').at(-1)?.ticker, 'LUCK');
  assert.equal(sortRows(rows, 'close', 'desc').at(-1)?.ticker, 'LUCK');
  assert.equal(sortRows(rows, 'forecast', 'asc').at(-1)?.ticker, 'ABOT');
});

test('filters by sector and by having a forecast', () => {
  assert.deepEqual(
    filterRows(rows, { sector: 'Cement', forecastOnly: false }).map((r) => r.ticker),
    ['LUCK'],
  );
  assert.deepEqual(
    filterRows(rows, { sector: '', forecastOnly: true }).map((r) => r.ticker),
    ['HBL', 'LUCK'],
  );
  assert.equal(filterRows(rows, { sector: '', forecastOnly: false }).length, 3);
});

test('a header click flips the same column, another column starts ascending', () => {
  assert.deepEqual(nextSort({ key: 'close', dir: 'asc' }, 'close'), { key: 'close', dir: 'desc' });
  assert.deepEqual(nextSort({ key: 'close', dir: 'desc' }, 'ticker'), {
    key: 'ticker',
    dir: 'asc',
  });
});

test('sector list for the filter is unique and sorted', () => {
  assert.deepEqual(sectorsOf(rows), ['Cement', 'Commercial Banks', 'Pharmaceuticals']);
});
