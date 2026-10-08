// Token refresh coordination, kept free of axios/storage so it is unit-testable with fakes.
// Refresh tokens are single-use (the server rotates them and treats a second use as theft),
// so the same refresh token must never be sent twice:
//  - within one JS context (a browser tab, or the React Native app): concurrent callers share
//    one in-flight refresh (single-flight) — this works everywhere, Web Locks or not;
//  - across browser tabs sharing storage: the exchange also runs under a Web Lock, and is
//    skipped if another tab already rotated the token while this one waited.

export type LockManagerLike = {
  request: (name: string, callback: () => Promise<string | null>) => Promise<string | null>;
};

export interface RefreshDeps {
  getRefreshToken: () => string | null;
  getAccessToken: () => string | null;
  /** Calls the API with the refresh token, stores the new pair, returns the new access token. */
  exchange: (refreshToken: string) => Promise<string | null>;
  /** Web Locks if the platform has them (browsers); undefined on React Native. */
  locks?: LockManagerLike;
}

export const LOCK_NAME = 'investiq-token-refresh';

export const createRefreshCoordinator = (deps: RefreshDeps) => {
  let inFlight: Promise<string | null> | null = null;

  const refreshOnce = async (): Promise<string | null> => {
    const refreshToken = deps.getRefreshToken();
    if (!refreshToken) return null;
    const run = async (): Promise<string | null> => {
      // Another tab rotated the token while we waited for the lock: use its result
      if (deps.getRefreshToken() !== refreshToken) return deps.getAccessToken();
      try {
        return await deps.exchange(refreshToken);
      } catch {
        return null;
      }
    };
    return deps.locks ? deps.locks.request(LOCK_NAME, run) : run();
  };

  /** New access token, or null if the session can't be refreshed. */
  return (): Promise<string | null> => {
    inFlight ??= refreshOnce().finally(() => {
      inFlight = null;
    });
    return inFlight;
  };
};
