import type { TokenStorage } from '@investiq/api-client';

const ACCESS = 'investiq.access_token';
const REFRESH = 'investiq.refresh_token';

const read = (key: string): string | null => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};

const write = (key: string, value: string | null) => {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Storage blocked (private mode etc.) — the session just won't survive a reload
  }
};

export const localTokenStorage: TokenStorage = {
  getAccessToken: () => read(ACCESS),
  getRefreshToken: () => read(REFRESH),
  setTokens: (t) => {
    write(ACCESS, t.access_token);
    write(REFRESH, t.refresh_token);
  },
  clear: () => {
    write(ACCESS, null);
    write(REFRESH, null);
  },
};
