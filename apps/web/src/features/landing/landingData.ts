// The landing page's data, generated from our own database and snapshot by
// `python -m services.landing_examples` (services/api) and committed with its date.
//
// VITE_LANDING_TICKERS=false builds the page with sector names only (bloom and risk demo), for a
// public deployment before PSX answers the data request (Memory.md §4). The flag is replaced at
// build time, so the unused files are not even in the bundle.
import type { RiskCategory } from '@investiq/shared-types';

export const SHOW_TICKERS = import.meta.env.VITE_LANDING_TICKERS !== 'false';

export interface BloomCompany {
  ticker?: string;
  sector: string;
}

export interface BloomData {
  snapshot: string;
  companies: BloomCompany[];
}

export interface RiskExample {
  forecast_companies: number;
  history_start: string | null;
  capital: string;
  filer_status: string;
  prices_as_of: string;
  model_version: string;
  rates_version: string;
  profiles: Record<
    RiskCategory,
    {
      holdings: { ticker?: string; sector: string; allocation_pct: string }[];
      cash_pct: string;
    }
  >;
}

export const loadBloomData = (): Promise<BloomData> =>
  (SHOW_TICKERS ? import('./data/bloom-companies.json') : import('./data/bloom-sectors.json')).then(
    (m) => m.default as BloomData,
  );

export const loadRiskExample = (): Promise<RiskExample> =>
  (SHOW_TICKERS
    ? import('./data/risk-examples.json')
    : import('./data/risk-examples-sectors.json')
  ).then((m) => m.default as RiskExample);
