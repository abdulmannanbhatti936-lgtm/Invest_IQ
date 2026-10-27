// Run with: npm test (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { AppNotification, NotificationPreferences } from '@investiq/shared-types';
import {
  editable,
  groupByType,
  isLowConfidence,
  isOptedOut,
  quietHoursValid,
  toTimeInput,
  unreadBadge,
} from './notificationView.ts';

const prefs = (overrides: Partial<NotificationPreferences> = {}): NotificationPreferences => ({
  buy_enabled: false,
  sell_enabled: false,
  roll_enabled: false,
  push_enabled: false,
  sensitivity: 'all',
  daily_cap: 3,
  quiet_hours_enabled: false,
  quiet_start: '22:00:00',
  quiet_end: '08:00:00',
  language: 'en',
  timezone: 'Asia/Karachi',
  push_available: false,
  ...overrides,
});

const base = { strength: null, ticker: null, reasoning: '', link: '/portfolio', data_as_of: null };
const idle = (id: string): AppNotification => ({
  ...base,
  id,
  type: 'buy',
  rule: 'idle_cash',
  params: { amount: '100.00', blocked_by: {}, as_of: '2026-10-09' },
  sent_at: '2026-10-09T14:00:00Z',
  read: false,
  read_at: null,
});
const sell = (id: string, reasons: string[]): AppNotification =>
  ({
    ...base,
    id,
    type: 'sell',
    rule: 'sell_forecast',
    strength: 'watch',
    params: { low_confidence_reasons: reasons },
    sent_at: '2026-10-09T14:00:00Z',
    read: false,
    read_at: null,
  }) as unknown as AppNotification;

test('a user with every type off has opted out; any one type on counts as opted in', () => {
  assert.equal(isOptedOut(prefs()), true);
  assert.equal(isOptedOut(prefs({ push_enabled: true })), true);
  assert.equal(isOptedOut(prefs({ sell_enabled: true })), false);
});

test('the unread badge hides at zero and caps at 9+', () => {
  assert.equal(unreadBadge(0), null);
  assert.equal(unreadBadge(3), '3');
  assert.equal(unreadBadge(9), '9');
  assert.equal(unreadBadge(12), '9+');
});

test('grouping keeps switches, then sales, then unused cash, and drops empty groups', () => {
  const groups = groupByType([idle('a'), sell('b', []), idle('c')]);
  assert.deepEqual(
    groups.map((g) => [g.type, g.items.map((n) => n.id)]),
    [
      ['sell', ['b']],
      ['buy', ['a', 'c']],
    ],
  );
});

test('low confidence comes from the stored reasons; idle cash rests on no forecast', () => {
  assert.equal(isLowConfidence(sell('a', ['no_edge_over_baseline'])), true);
  assert.equal(isLowConfidence(sell('b', [])), false);
  assert.equal(isLowConfidence(idle('c')), false);
});

test('times from the API fit a time input, and quiet hours need two different times', () => {
  assert.equal(toTimeInput('22:00:00'), '22:00');
  const form = editable(prefs({ quiet_hours_enabled: true, quiet_end: '22:00:00' }));
  assert.equal(form.quiet_start, '22:00');
  assert.equal(quietHoursValid(form), false);
  assert.equal(quietHoursValid({ ...form, quiet_hours_enabled: false }), true);
  assert.equal(quietHoursValid({ ...form, quiet_end: '07:00' }), true);
});
