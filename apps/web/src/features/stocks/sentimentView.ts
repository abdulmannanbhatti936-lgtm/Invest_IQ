import type { SentimentHeadline, StockSentiment } from '@investiq/shared-types';

/** A score on the -1..+1 scale with its sign, e.g. "+0.40". */
export const formatScore = (score: number): string => {
  const rounded = Math.round(score * 100) / 100;
  return `${rounded > 0 ? '+' : rounded < 0 ? '−' : ''}${Math.abs(rounded).toFixed(2)}`;
};

/** Each counted headline's share of today's sentiment (its decayed weight / the total). */
export const weightShare = (
  headline: SentimentHeadline,
  sentiment: StockSentiment,
): number | null =>
  headline.weight == null || sentiment.news_weight <= 0
    ? null
    : headline.weight / sentiment.news_weight;

/** Headlines inside the window: those that count, then those shown for context only. */
export const splitHeadlines = (sentiment: StockSentiment) => ({
  counted: sentiment.headlines.filter((h) => h.weight != null),
  context: sentiment.headlines.filter((h) => h.weight == null),
});

/** The newest successful scrape among the sources that feed the score, if any. */
export const lastUpdated = (sentiment: StockSentiment): string | null =>
  sentiment.freshness.sources
    .map((s) => s.last_success_at)
    .filter((value): value is string => value != null)
    .sort()
    .at(-1) ?? null;
