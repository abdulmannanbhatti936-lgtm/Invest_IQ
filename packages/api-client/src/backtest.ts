import type { BacktestResult, BacktestUniverse, RunBacktestRequest } from '@investiq/shared-types';
import { apiClient } from './client';

export const backtestApi = {
  /** Runs and stores a backtest of a stored portfolio or the user's own mix (past prices). */
  run: async (body: RunBacktestRequest): Promise<BacktestResult> => {
    const { data } = await apiClient.post<BacktestResult>('/backtest/run', body);
    return data;
  },

  get: async (id: string): Promise<BacktestResult> => {
    const { data } = await apiClient.get<BacktestResult>(`/backtest/${encodeURIComponent(id)}`);
    return data;
  },

  /** Stocks a custom mix may use, each with its whole years of price history. */
  universe: async (): Promise<BacktestUniverse> => {
    const { data } = await apiClient.get<BacktestUniverse>('/backtest/universe');
    return data;
  },
};
