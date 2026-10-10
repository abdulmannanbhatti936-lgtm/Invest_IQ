import type {
  HistoryPeriod,
  Prediction,
  PricePoint,
  StockQuote,
  StockSentiment,
  StockSummary,
} from '@investiq/shared-types';
import { apiClient } from './client';

const path = (ticker: string) => `/stocks/${encodeURIComponent(ticker)}`;

export const stocksApi = {
  /** Search by ticker, company name or sector; an empty query lists the catalog. */
  search: async (q: string): Promise<StockSummary[]> => {
    const { data } = await apiClient.get<{ results: StockSummary[] }>('/stocks/search', {
      params: { q },
    });
    return data.results;
  },

  getQuote: async (ticker: string): Promise<StockQuote> => {
    const { data } = await apiClient.get<StockQuote>(path(ticker));
    return data;
  },

  getHistory: async (ticker: string, period: HistoryPeriod = '1y'): Promise<PricePoint[]> => {
    const { data } = await apiClient.get<PricePoint[]>(`${path(ticker)}/history`, {
      params: { period },
    });
    return data;
  },

  /** Rejects with a 404 whose detail.code explains why there is no prediction. */
  getPrediction: async (ticker: string): Promise<Prediction> => {
    const { data } = await apiClient.get<Prediction>(`${path(ticker)}/prediction`);
    return data;
  },

  /** News sentiment and the headlines behind it; a 404 `not_covered` outside the tracked stocks. */
  getSentiment: async (ticker: string): Promise<StockSentiment> => {
    const { data } = await apiClient.get<StockSentiment>(`${path(ticker)}/sentiment`);
    return data;
  },
};
