import type { ChatHistory, ChatLanguage, ChatMessage, ChatSourceTag } from '@investiq/shared-types';

export const MAX_MESSAGE_CHARS = 1000;

/** Urdu replies read right to left; English and Roman Urdu left to right (Design.md §23). */
export const messageDir = (language: ChatLanguage): 'rtl' | 'ltr' =>
  language === 'ur' ? 'rtl' : 'ltr';

export interface Segment {
  text: string;
  figure: boolean;
}

// A figure with its unit: "Rs. 99,887.21", "PKR 5", "-20.25%", "1,00,000"
const FIGURE = /(?:Rs\.?\s?|PKR\s?)?[-+]?\d[\d,]*(?:\.\d+)?%?/g;

/**
 * Splits reply text so every figure can sit in its own left-to-right isolate: inside an Urdu
 * sentence, "Rs. 99,887.21" and "-20.25%" would otherwise be reordered by the bidi algorithm.
 */
export const figureSegments = (text: string): Segment[] => {
  const segments: Segment[] = [];
  let last = 0;
  for (const match of text.matchAll(FIGURE)) {
    const start = match.index ?? 0;
    if (start > last) segments.push({ text: text.slice(last, start), figure: false });
    segments.push({ text: match[0], figure: true });
    last = start + match[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last), figure: false });
  return segments;
};

/** History pages arrive newest first; the conversation reads oldest first, without repeats. */
export const conversation = (pages: ChatHistory[]): ChatMessage[] => {
  const seen = new Set<string>();
  const messages: ChatMessage[] = [];
  for (const page of pages) {
    for (const message of page.messages) {
      if (!seen.has(message.id)) {
        seen.add(message.id);
        messages.push(message);
      }
    }
  }
  return messages.reverse();
};

/** i18n key and parameters of a reply's "from your current portfolio"-style tag. */
export const sourceTag = (tag: ChatSourceTag): { key: string; params: Record<string, string> } => ({
  key: `chat.source.${tag.kind}`,
  params: { ticker: tag.ticker ?? '', date: tag.date ?? '' },
});

/** One tag per source, in the order the reply used them. */
export const uniqueSources = (sources: ChatSourceTag[]): ChatSourceTag[] => {
  const seen = new Set<string>();
  return sources.filter((s) => {
    const key = `${s.kind}:${s.ticker ?? ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

/**
 * The page banner shows the disclaimer in the app's language; a reply in another language
 * (Roman Urdu, or Urdu after switching to English) repeats it in its own (PRD.md §8.5).
 */
export const replyDisclaimerKey = (
  replyLanguage: ChatLanguage,
  appLanguage: string,
): { key: string; lng?: 'en' | 'ur' } | null => {
  if (replyLanguage === 'ur-latn') return { key: 'chat.disclaimerRomanUrdu' };
  return replyLanguage === appLanguage ? null : { key: 'disclaimer', lng: replyLanguage };
};

/** `seconds`: how long to wait (the API's Retry-After), or null when it gave none. */
export type SendProblem =
  | { kind: 'rateLimited'; seconds: number | null }
  | { kind: 'unavailable' }
  | { kind: 'busy'; seconds: number | null }
  | { kind: 'failed' };

const waitSeconds = (detail: Record<string, unknown> | null): number | null => {
  const seconds = Math.ceil(Number(detail?.retry_after));
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
};

/**
 * What went wrong with a send. 429 is the user's own message limit; 503 `provider_busy` is the
 * AI provider's limit after any failover. Both carry the wait in the body (`retry_after`),
 * because browsers hide the Retry-After header from cross-origin pages.
 */
export const sendProblem = (
  status: number | null,
  detail: Record<string, unknown> | null,
): SendProblem => {
  if (status === 429) return { kind: 'rateLimited', seconds: waitSeconds(detail) };
  if (status === 503) {
    if (detail?.reason === 'not_configured') return { kind: 'unavailable' };
    if (detail?.reason === 'provider_busy') return { kind: 'busy', seconds: waitSeconds(detail) };
  }
  return { kind: 'failed' };
};

/** Whole seconds left until `until` (epoch ms), never below zero. */
export const secondsLeft = (until: number, now: number): number =>
  Math.max(0, Math.ceil((until - now) / 1000));

export const canSend = (
  text: string,
  sending: boolean,
  available: boolean,
  waiting = false,
): boolean =>
  available && !sending && !waiting && text.trim().length > 0 && text.length <= MAX_MESSAGE_CHARS;
