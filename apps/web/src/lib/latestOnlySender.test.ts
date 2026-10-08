// Run with: npm test (Node's built-in test runner; no extra dependency)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createLatestOnlySender } from './latestOnlySender.ts';

const tick = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Fake server: each request takes `delays[i]` ms; the stored value is whatever arrives last. */
const fakeServer = (delays: number[]) => {
  let stored: number | null = null;
  const sent: number[] = [];
  let active = 0;
  let maxActive = 0;
  const request = async (step: number) => {
    const delay = delays[sent.length] ?? 0;
    sent.push(step);
    active += 1;
    maxActive = Math.max(maxActive, active);
    await tick(delay);
    stored = step;
    active -= 1;
  };
  return { request, sent, stored: () => stored, maxActive: () => maxActive };
};

test('two fast answers with a slow first request: the later step is what the server keeps', async () => {
  const server = fakeServer([60, 5]); // first save is slow, second is fast
  const sender = createLatestOnlySender(server.request);
  sender.send(1); // answer to question 1 -> resume at step 1
  sender.send(2); // answer to question 2 arrives while the first save is still running
  await tick(120);
  assert.equal(server.stored(), 2);
  assert.deepEqual(server.sent, [1, 2]);
  assert.equal(server.maxActive(), 1, 'never more than one request at a time');
});

test('intermediate saves are skipped: only the latest queued value is sent', async () => {
  const server = fakeServer([40, 5]);
  const sender = createLatestOnlySender(server.request);
  sender.send(1);
  sender.send(2);
  sender.send(3);
  sender.send(4);
  await tick(100);
  assert.deepEqual(server.sent, [1, 4]);
  assert.equal(server.stored(), 4);
});

test('without the sender, the same timing loses the later step (the bug being fixed)', async () => {
  const server = fakeServer([60, 5]);
  void server.request(1);
  void server.request(2);
  await tick(120);
  assert.equal(server.stored(), 1);
});

test('flush drops the waiting value and waits for the in-flight request', async () => {
  const server = fakeServer([40, 5]);
  const sender = createLatestOnlySender(server.request);
  sender.send(1);
  sender.send(2);
  await sender.flush();
  assert.deepEqual(server.sent, [1]);
  assert.equal(server.stored(), 1);
});

test('a failed request is reported and the next value is still sent', async () => {
  const results: boolean[] = [];
  let calls = 0;
  const sender = createLatestOnlySender(
    async () => {
      calls += 1;
      if (calls === 1) throw new Error('network down');
    },
    (ok) => results.push(ok),
  );
  sender.send(1);
  await sender.flush();
  sender.send(2);
  await sender.flush();
  assert.deepEqual(results, [false, true]);
});
