import { apiClient } from './client';

export interface StockQuote {
  ticker: string;
  name: string;
  sector?: string;
  current_price: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  previous_close: number;
  timestamp: string;
}

export interface StockSearchResponse {
  results: StockQuote[];
}

export interface PricePointResponse {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PredictionResponse {
  stock_id: string;
  predicted_price: number;
  signal: 'BUY' | 'SELL' | 'HOLD';
  confidence_score: number;
  model_version: string;
  timestamp: string;
}

export const stocksApi = {
  search: async (q: string): Promise<StockSearchResponse> => {
    const { data } = await apiClient.get(`/stocks/search?q=${q}`);
    return data;
  },
  
  getQuote: async (ticker: string): Promise<StockQuote> => {
    const { data } = await apiClient.get(`/stocks/${ticker}`);
    return data;
  },
  
  getHistory: async (ticker: string, period: string = '1y'): Promise<PricePointResponse[]> => {
    const { data } = await apiClient.get(`/stocks/${ticker}/history?period=${period}`);
    return data;
  },
  
  getPrediction: async (ticker: string): Promise<PredictionResponse> => {
    const { data } = await apiClient.get(`/stocks/${ticker}/prediction`);
    return data;
  }
};
