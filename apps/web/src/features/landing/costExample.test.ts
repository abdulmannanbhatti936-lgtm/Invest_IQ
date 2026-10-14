// Run with: npm test (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { COST_EXAMPLE } from './costExample.ts';

const paisa = (v: string) => Math.round(Number(v) * 100);

test('the charge lines add up to the worked example total (Rs 180.80)', () => {
  const sum = COST_EXAMPLE.charges.reduce((s, c) => s + paisa(c.amount), 0);
  assert.equal(sum, paisa(COST_EXAMPLE.chargesTotal));
});

test('shares + charges + cash = the Rs 100,000 put in', () => {
  assert.equal(
    paisa(COST_EXAMPLE.shares) + paisa(COST_EXAMPLE.chargesTotal) + paisa(COST_EXAMPLE.cash),
    paisa(COST_EXAMPLE.capital),
  );
});
