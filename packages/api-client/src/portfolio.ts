import type { GeneratePortfolioRequest, Portfolio, RollCheckResult } from '@investiq/shared-types';
import { apiClient } from './client';

export const portfolioApi = {
  /** Builds a new recommended portfolio and archives the previous one. Guidance only. */
  generate: async (body: GeneratePortfolioRequest): Promise<Portfolio> => {
    const { data } = await apiClient.post<Portfolio>('/portfolio/generate', body);
    return data;
  },

  /** Rejects with a 404 `no_active_portfolio` before the first one is generated. */
  current: async (): Promise<Portfolio> => {
    const { data } = await apiClient.get<Portfolio>('/portfolio/current');
    return data;
  },

  rollCheck: async (portfolioId: string): Promise<RollCheckResult> => {
    const { data } = await apiClient.post<RollCheckResult>(
      `/portfolio/${encodeURIComponent(portfolioId)}/roll-check`,
    );
    return data;
  },

  /** Returns the regenerated portfolio without `ticker` (the old one is archived). */
  excludeStock: async (portfolioId: string, ticker: string): Promise<Portfolio> => {
    const { data } = await apiClient.patch<Portfolio>(
      `/portfolio/${encodeURIComponent(portfolioId)}/exclude-stock`,
      { ticker },
    );
    return data;
  },
};
