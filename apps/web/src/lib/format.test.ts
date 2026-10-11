// Run with: npm test (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatDate, formatMoney, formatPctString, withSign } from './format.ts';

test('API timestamps (UTC, "Z") are shown as the Pakistan date', () => {
  // 21:18 UTC on 8 Oct is 02:18 on 9 Oct in Karachi — the day the user actually saw
  assert.match(formatDate('2026-10-08T21:18:00Z', 'en'), /^9 Oct 2026$/);
  assert.match(formatDate('2026-10-08T21:18:00Z', 'ur'), /9/);
  assert.match(formatDate('2026-10-08T21:18:00Z', 'ur'), /اکتوبر/);
  // Earlier the same UTC day it is still the 8th in Karachi
  assert.match(formatDate('2026-10-08T10:00:00Z', 'en'), /^8 Oct 2026$/);
});

test('date-only strings keep their calendar date', () => {
  assert.match(formatDate('2026-01-02', 'en'), /^2 Jan 2026$/);
});

test('Urdu dates keep Western digits (Design.md §23)', () => {
  assert.doesNotMatch(formatDate('2026-10-08T21:18:00Z', 'ur'), /[۰-۹٠-٩]/);
});

test('money strings from the API are formatted, never recalculated', () => {
  assert.equal(formatMoney('99887.21'), 'Rs. 99,887.21');
  assert.equal(formatMoney('-35.13'), 'Rs. -35.13');
  assert.equal(formatMoney(null), '—');
});

test('percent strings keep the API value, isolated left-to-right for Urdu text', () => {
  const ltr = (s: string) => `⁦${s}⁩`;
  assert.equal(formatPctString('0.36'), ltr('0.36%'));
  assert.equal(formatPctString('0.30', true), ltr('+0.30%'));
  assert.equal(formatPctString('-0.28', true), ltr('-0.28%'));
  assert.equal(formatPctString('0.00', true), ltr('0.00%'));
  assert.equal(formatPctString(null), '—');
});

test('positive figures get a plus sign, zero and negative ones keep theirs', () => {
  assert.equal(withSign('0.30'), '+0.30');
  assert.equal(withSign('-0.07'), '-0.07');
  assert.equal(withSign('0.00'), '0.00');
});
