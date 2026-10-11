import type { SentimentHeadline, StockSentiment } from '@investiq/shared-types';

/** Each counted headline's share of today's sentiment (its decayed weight / the total). */
export const weightShare = (
  headline: SentimentHeadline,
  sentiment: StockSentiment,
): number | null =>
  headline.weight == null || sentiment.news_weight <= 0
    ? null
    : headline.weight / sentiment.news_weight;

/** The newest successful scrape among the sources that feed the score, if any. */
export const lastUpdated = (sentiment: StockSentiment): string | null =>
  sentiment.freshness.sources
    .map((s) => s.last_success_at)
    .filter((value): value is string => value != null)
    .sort()
    .at(-1) ?? null;
