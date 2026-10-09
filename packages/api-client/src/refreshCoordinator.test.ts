// Run with: npm test -w @investiq/api-client (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createRefreshCoordinator, LOCK_NAME, type LockManagerLike } from './refreshCoordinator.ts';

/** Fake token store + server: every exchange rotates the pair; reusing a token is recorded. */
const fakeSession = (exchangeDelayMs = 10) => {
  const state = { access: 'a0', refresh: 'r0', calls: [] as string[], reused: 0, n: 0 };
  const exchange = async (refreshToken: string) => {
    state.calls.push(refreshToken);
    await new Promise((resolve) => setTimeout(resolve, exchangeDelayMs));
    if (refreshToken !== state.refresh) {
      state.reused += 1;
      throw new Error('401 reuse');
    }
    state.n += 1;
    state.access = `a${state.n}`;
    state.refresh = `r${state.n}`;
    return state.access;
  };
  return {
    state,
    deps: {
      getRefreshToken: () => state.refresh,
      getAccessToken: () => state.access,
      exchange,
    },
  };
};

/** Minimal Web Locks stand-in: callbacks for the same name run one at a time. */
const fakeLocks = () => {
  const names: string[] = [];
  let tail: Promise<unknown> = Promise.resolve();
  const locks: LockManagerLike = {
    request: (name, callback) => {
      names.push(name);
      const result = tail.then(callback);
      tail = result.catch(() => undefined);
      return result;
    },
  };
  return { locks, names };
};

test('without Web Locks (React Native): concurrent 401s share one refresh', async () => {
  const { state, deps } = fakeSession();
  const refresh = createRefreshCoordinator(deps); // no `locks`
  const results = await Promise.all([refresh(), refresh(), refresh(), refresh()]);
  assert.deepEqual(state.calls, ['r0']); // exactly one exchange, never a reused token
  assert.equal(state.reused, 0);
  assert.deepEqual(results, ['a1', 'a1', 'a1', 'a1']);
});

test('without Web Locks: a later 401 refreshes again with the rotated token', async () => {
  const { state, deps } = fakeSession();
  const refresh = createRefreshCoordinator(deps);
  assert.equal(await refresh(), 'a1');
  assert.equal(await refresh(), 'a2');
  assert.deepEqual(state.calls, ['r0', 'r1']);
});

test('a failed exchange resolves to null and does not block the next attempt', async () => {
  const { deps } = fakeSession();
  let fail = true;
  const refresh = createRefreshCoordinator({
    ...deps,
    exchange: async (token) => {
      if (fail) throw new Error('network down');
      return deps.exchange(token);
    },
  });
  assert.equal(await refresh(), null);
  fail = false;
  assert.equal(await refresh(), 'a1');
});

test('no refresh token: no request, null', async () => {
  const { state, deps } = fakeSession();
  state.refresh = null as unknown as string;
  assert.equal(await createRefreshCoordinator(deps)(), null);
  assert.deepEqual(state.calls, []);
});

test('with Web Locks: two tabs sharing storage send the refresh token only once', async () => {
  const { state, deps } = fakeSession();
  const { locks, names } = fakeLocks();
  // Two coordinators = two tabs (separate in-process state), one shared store and lock manager
  const tabA = createRefreshCoordinator({ ...deps, locks });
  const tabB = createRefreshCoordinator({ ...deps, locks });
  const [a, b] = await Promise.all([tabA(), tabB()]);
  assert.deepEqual(state.calls, ['r0']); // tab B saw the rotated token and skipped its call
  assert.equal(state.reused, 0);
  assert.equal(a, 'a1');
  assert.equal(b, 'a1');
  assert.deepEqual(names, [LOCK_NAME, LOCK_NAME]);
});

test('without the lock, two tabs would reuse the token (why the lock exists)', async () => {
  const { state, deps } = fakeSession();
  const tabA = createRefreshCoordinator(deps);
  const tabB = createRefreshCoordinator(deps);
  await Promise.all([tabA(), tabB()]);
  assert.equal(state.reused, 1);
});
