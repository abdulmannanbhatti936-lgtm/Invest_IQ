import type { ChargeKey, PortfolioErrorCode, RiskCategory } from '@investiq/shared-types';

/** Charge lines in contract-note order. */
export const CHARGE_ORDER: ChargeKey[] = [
  'commission',
  'sales_tax',
  'cdc_fee',
  'psx_trading_fee',
  'psx_regulatory_fee',
  'secp_levy',
  'nccpl_trade_fee',
  'nccpl_secp_fee',
];

export const isNegative = (value: string | null | undefined): boolean =>
  value != null && value.startsWith('-') && Number(value) !== 0;

const MONEY_PATTERN = /^\d{1,12}(\.\d{1,2})?$/;

/** i18n key for a problem with the capital field, or null when it can be sent. */
export const capitalError = (input: string): string | null => {
  const value = input.replace(/,/g, '').trim();
  if (!value) return 'portfolio.form.capitalRequired';
  if (!MONEY_PATTERN.test(value) || Number(value) <= 0) return 'portfolio.form.capitalInvalid';
  return null;
};

/** The format of the optional broker rate; the API checks it against the PSX range. */
export const commissionError = (input: string): string | null =>
  !input.trim() || /^\d+(\.\d{1,3})?$/.test(input.trim())
    ? null
    : 'portfolio.form.commissionInvalid';

export const cleanCapital = (input: string): string => input.replace(/,/g, '').trim();

export interface LowCapital {
  minimumCapital: string | null;
  minHoldings: number;
  maxStockWeightPct: string;
  riskCategory: RiskCategory;
  pricesAsOf: string;
}

/** The low-capital explanation (FR28) from a 422 `capital_below_minimum` detail. */
export const lowCapitalFrom = (detail: Record<string, unknown> | null): LowCapital | null => {
  if (!detail || detail.code !== 'capital_below_minimum') return null;
  return {
    minimumCapital: (detail.minimum_capital as string | null) ?? null,
    minHoldings: Number(detail.min_holdings),
    maxStockWeightPct: String(Number(detail.max_stock_weight_pct)),
    riskCategory: detail.risk_category as RiskCategory,
    pricesAsOf: String(detail.prices_as_of),
  };
};

const ERROR_KEYS: Partial<Record<PortfolioErrorCode, string>> = {
  too_few_eligible_stocks: 'portfolio.error.tooFewStocks',
  invalid_commission_rate: 'portfolio.error.commission',
  predictions_unavailable: 'portfolio.error.predictionsUnavailable',
  portfolio_archived: 'portfolio.error.archived',
  ticker_not_in_portfolio: 'portfolio.error.notInPortfolio',
};

export const errorMessageKey = (code: string | null | undefined): string =>
  ERROR_KEYS[code as PortfolioErrorCode] ?? 'common.errorGeneric';
