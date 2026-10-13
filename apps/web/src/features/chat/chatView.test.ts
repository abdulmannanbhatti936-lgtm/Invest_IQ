// Run with: npm test (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { ChatHistory, ChatMessage } from '@investiq/shared-types';
import {
  canSend,
  conversation,
  figureSegments,
  messageDir,
  replyDisclaimerKey,
  secondsLeft,
  sendProblem,
  sourceTag,
  uniqueSources,
} from './chatView.ts';

const message = (id: string, role: ChatMessage['role'] = 'user'): ChatMessage => ({
  id,
  role,
  content: id,
  language: 'en',
  created_at: '2026-10-13T10:00:00Z',
  sources: [],
  figure_check: null,
});

const page = (ids: string[], next: string | null = null): ChatHistory => ({
  messages: ids.map((id) => message(id)),
  next_before: next,
  chat_available: true,
  unavailable_reason: null,
});

test('figures with their units are isolated from the text around them', () => {
  assert.deepEqual(figureSegments('آپ کی لاگت Rs. 99,887.21 ہے اور کمی -20.25% تھی'), [
    { text: 'آپ کی لاگت ', figure: false },
    { text: 'Rs. 99,887.21', figure: true },
    { text: ' ہے اور کمی ', figure: false },
    { text: '-20.25%', figure: true },
    { text: ' تھی', figure: false },
  ]);
  assert.deepEqual(figureSegments('No figures here.'), [
    { text: 'No figures here.', figure: false },
  ]);
  assert.deepEqual(figureSegments('PKR 1,00,000'), [{ text: 'PKR 1,00,000', figure: true }]);
});

test('only Urdu script replies are right to left', () => {
  assert.equal(messageDir('ur'), 'rtl');
  assert.equal(messageDir('en'), 'ltr');
  assert.equal(messageDir('ur-latn'), 'ltr');
});

test('pages read oldest first and an overlapping page adds no repeats', () => {
  const pages = [page(['m4', 'm3'], 'm3'), page(['m3', 'm2', 'm1'])];
  assert.deepEqual(
    conversation(pages).map((m) => m.id),
    ['m1', 'm2', 'm3', 'm4'],
  );
  assert.deepEqual(conversation([]), []);
});

test('source tags name the kind, stock and date, once each', () => {
  assert.deepEqual(sourceTag({ kind: 'prediction', ticker: 'HBL', date: '2026-10-07' }), {
    key: 'chat.source.prediction',
    params: { ticker: 'HBL', date: '2026-10-07' },
  });
  assert.deepEqual(
    uniqueSources([
      { kind: 'portfolio', date: '2026-10-13' },
      { kind: 'prediction', ticker: 'HBL', date: '2026-10-07' },
      { kind: 'portfolio', date: '2026-10-13' },
      { kind: 'prediction', ticker: 'OGDC', date: '2026-10-07' },
    ]).map((s) => `${s.kind}:${s.ticker ?? ''}`),
    ['portfolio:', 'prediction:HBL', 'prediction:OGDC'],
  );
});

test('a reply repeats the disclaimer only in a language the page banner does not use', () => {
  assert.equal(replyDisclaimerKey('en', 'en'), null);
  assert.equal(replyDisclaimerKey('ur', 'ur'), null);
  assert.deepEqual(replyDisclaimerKey('ur-latn', 'en'), { key: 'chat.disclaimerRomanUrdu' });
  assert.deepEqual(replyDisclaimerKey('ur-latn', 'ur'), { key: 'chat.disclaimerRomanUrdu' });
  assert.deepEqual(replyDisclaimerKey('ur', 'en'), { key: 'disclaimer', lng: 'ur' });
});

test('send failures map to what the screen should say', () => {
  assert.deepEqual(sendProblem(429, { retry_after: 300 }), { kind: 'rateLimited', seconds: 300 });
  assert.deepEqual(sendProblem(429, null), { kind: 'rateLimited', seconds: null });
  assert.deepEqual(sendProblem(503, { reason: 'not_configured' }), { kind: 'unavailable' });
  assert.deepEqual(sendProblem(503, { reason: 'provider_busy', retry_after: 7 }), {
    kind: 'busy',
    seconds: 7,
  });
  assert.deepEqual(sendProblem(503, { reason: 'provider_busy', retry_after: 2.3 }), {
    kind: 'busy',
    seconds: 3,
  });
  assert.deepEqual(sendProblem(503, { reason: 'provider_busy' }), { kind: 'busy', seconds: null });
  assert.deepEqual(sendProblem(503, { reason: 'provider_busy', retry_after: 'soon' }), {
    kind: 'busy',
    seconds: null,
  });
  assert.deepEqual(sendProblem(503, { reason: 'provider_error' }), { kind: 'failed' });
  assert.deepEqual(sendProblem(null, null), { kind: 'failed' });
});

test('the countdown counts whole seconds down to zero', () => {
  assert.equal(secondsLeft(10_000, 0), 10);
  assert.equal(secondsLeft(10_000, 9_001), 1);
  assert.equal(secondsLeft(10_000, 10_000), 0);
  assert.equal(secondsLeft(10_000, 12_000), 0);
});

test('nothing can be sent while waiting out a limit', () => {
  assert.equal(canSend('hi', false, true, true), false);
  assert.equal(canSend('hi', false, true, false), true);
});

test('a message can be sent only when it has text within the limit', () => {
  assert.equal(canSend('hi', false, true), true);
  assert.equal(canSend('   ', false, true), false);
  assert.equal(canSend('hi', true, true), false);
  assert.equal(canSend('hi', false, false), false);
  assert.equal(canSend('x'.repeat(1000), false, true), true);
  assert.equal(canSend('x'.repeat(1001), false, true), false);
});
