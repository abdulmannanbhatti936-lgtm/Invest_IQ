// Run with: npm test (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { SentimentHeadline, StockSentiment } from '@investiq/shared-types';
import { formatScore, lastUpdated, splitHeadlines, weightShare } from './sentimentView.ts';

const headline = (overrides: Partial<SentimentHeadline> = {}): SentimentHeadline => ({
  headline: 'MOCK_ OGDC output rises',
  source: 'profit',
  source_name: 'Profit',
  url: 'https://example.com/MOCK/1',
  published_at: '2026-10-07T05:00:00Z',
  label: 'positive',
  score: 0.8,
  scorer: 'finbert',
  weight: 1,
  ...overrides,
});

const sentiment = (overrides: Partial<StockSentiment> = {}): StockSentiment => ({
  ticker: 'OGDC',
  as_of_date: '2026-10-07',
  label: 'positive',
  score: 0.4,
  news_weight: 1.5,
  counted_headlines: 2,
  window_trading_days: 10,
  half_life_trading_days: 3,
  headlines: [
    headline(),
    headline({ weight: 0.5, label: 'negative', score: -0.4 }),
    headline({ source: 'brecorder', source_name: 'Business Recorder', weight: null }),
  ],
  after_close_headlines: [],
  freshness: {
    stale: false,
    sources: [
      { source: 'profit', name: 'Profit', last_success_at: '2026-10-10T09:00:00Z', stale: false },
      { source: 'mettis', name: 'Mettis', last_success_at: '2026-10-10T12:00:00Z', stale: false },
    ],
  },
  ...overrides,
});

test('scores are signed with two decimals', () => {
  assert.equal(formatScore(0.4), '+0.40');
  assert.equal(formatScore(-0.456), '−0.46');
  assert.equal(formatScore(0.001), '0.00');
});

test('each counted headline shows its share of the score', () => {
  const s = sentiment();
  assert.equal(weightShare(s.headlines[0], s), 1 / 1.5);
  assert.equal(weightShare(s.headlines[2], s), null);
});

test('context-only headlines are listed apart from counted ones', () => {
  const { counted, context } = splitHeadlines(sentiment());
  assert.equal(counted.length, 2);
  assert.deepEqual(
    context.map((h) => h.source),
    ['brecorder'],
  );
});

test('last update is the newest successful scrape', () => {
  assert.equal(lastUpdated(sentiment()), '2026-10-10T12:00:00Z');
  const never = sentiment({
    freshness: {
      stale: true,
      sources: [{ source: 'profit', name: 'Profit', last_success_at: null, stale: true }],
    },
  });
  assert.equal(lastUpdated(never), null);
});
