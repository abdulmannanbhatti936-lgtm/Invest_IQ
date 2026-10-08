import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import type { TokenPair } from '@investiq/shared-types';

export const DEFAULT_API_URL = 'http://127.0.0.1:8000';

export const apiClient = axios.create({
  baseURL: DEFAULT_API_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 20000,
});

/** Where tokens live is platform-specific (localStorage on web, memory/secure store on mobile). */
export interface TokenStorage {
  getAccessToken(): string | null;
  getRefreshToken(): string | null;
  setTokens(tokens: TokenPair): void;
  clear(): void;
}

const memoryStorage = (): TokenStorage => {
  let access: string | null = null;
  let refresh: string | null = null;
  return {
    getAccessToken: () => access,
    getRefreshToken: () => refresh,
    setTokens: (t) => {
      access = t.access_token;
      refresh = t.refresh_token;
    },
    clear: () => {
      access = null;
      refresh = null;
    },
  };
};

let storage: TokenStorage = memoryStorage();
let onSessionExpired: (() => void) | null = null;

export const configureApi = (options: {
  baseURL?: string;
  tokenStorage?: TokenStorage;
  onSessionExpired?: () => void;
}) => {
  if (options.baseURL) apiClient.defaults.baseURL = options.baseURL;
  if (options.tokenStorage) storage = options.tokenStorage;
  if (options.onSessionExpired) onSessionExpired = options.onSessionExpired;
};

export const tokens = {
  set: (pair: TokenPair) => storage.setTokens(pair),
  clear: () => storage.clear(),
  hasSession: () => !!storage.getAccessToken(),
};

apiClient.interceptors.request.use((config) => {
  const token = storage.getAccessToken();
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On a 401, exchange the refresh token once and retry; concurrent 401s share one refresh.
let refreshing: Promise<string | null> | null = null;

const refreshAccessToken = async (): Promise<string | null> => {
  const refreshToken = storage.getRefreshToken();
  if (!refreshToken) return null;
  try {
    const { data } = await axios.post<TokenPair>(`${apiClient.defaults.baseURL}/auth/refresh`, {
      refresh_token: refreshToken,
    });
    storage.setTokens(data);
    return data.access_token;
  } catch {
    return null;
  }
};

apiClient.interceptors.response.use(undefined, async (error: AxiosError) => {
  const original = error.config as
    (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
  const isAuthCall = original?.url?.startsWith('/auth/');
  if (error.response?.status !== 401 || !original || original._retried || isAuthCall) {
    throw error;
  }
  original._retried = true;
  refreshing ??= refreshAccessToken().finally(() => {
    refreshing = null;
  });
  const newToken = await refreshing;
  if (!newToken) {
    storage.clear();
    onSessionExpired?.();
    throw error;
  }
  original.headers.Authorization = `Bearer ${newToken}`;
  return apiClient(original);
});

/** Best-effort human-readable message from an API error. */
export const getErrorMessage = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object' && 'message' in detail) return String(detail.message);
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  }
  return fallback;
};

/** The `detail.code` of a structured API error, if any. */
export const getErrorCode = (error: unknown): string | null => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (detail && typeof detail === 'object' && 'code' in detail) return String(detail.code);
  }
  return null;
};

/** Field-level problems from a FastAPI 422 response: the field name and the server's message. */
export const getValidationErrors = (error: unknown): { field: string; message: string }[] => {
  if (!axios.isAxiosError(error) || error.response?.status !== 422) return [];
  const detail = error.response.data?.detail;
  if (!Array.isArray(detail)) return [];
  return detail.map((item: { loc?: unknown[]; msg?: unknown }) => ({
    field: String(item.loc?.[item.loc.length - 1] ?? ''),
    message: String(item.msg ?? ''),
  }));
};

export const getErrorStatus = (error: unknown): number | null =>
  axios.isAxiosError(error) ? (error.response?.status ?? null) : null;
