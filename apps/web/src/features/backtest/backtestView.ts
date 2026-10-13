import type {
  BacktestErrorCode,
  BacktestSeriesPoint,
  BacktestUniverse,
  Ratio,
} from '@investiq/shared-types';

// The API sends returns as fractions with at most 6 decimals ("0.235491" = +23.5491%). They
// are shifted and rounded as decimal strings (in millionths), so a figure on screen is the
// API's figure rounded half up, never a recalculation in floating point.
const MICRO = 6;

const toMicro = (value: string): number => {
  const negative = value.trim().startsWith('-');
  const [whole, fraction = ''] = value.trim().replace(/^[-+]/, '').split('.');
  const micro = Number(whole) * 10 ** MICRO + Number(fraction.padEnd(MICRO, '0').slice(0, MICRO));
  return negative ? -micro : micro;
};

/** Rounds an integer count of 10^-scale units half up (away from zero) to `digits` decimals. */
const roundUnits = (units: number, scale: number, digits: number): string => {
  const step = 10 ** (scale - digits);
  const rounded = Math.round(Math.abs(units) / step) * (units < 0 ? -1 : 1);
  const text = (Math.abs(rounded) / 10 ** digits).toFixed(digits);
  return rounded < 0 ? `-${text}` : text;
};

/** "0.235491" -> "23.55" (percent, `digits` decimals). */
export const ratioToPct = (ratio: Ratio, digits = 2): string =>
  roundUnits(toMicro(ratio), MICRO - 2, digits);

/** A plain decimal string rounded half up, e.g. a Sharpe ratio "1.167685" -> "1.17". */
export const roundDecimal = (value: string, digits = 2): string =>
  roundUnits(toMicro(value), MICRO, digits);

/** Percentage points between two returns, e.g. the gap hindsight adds: a - b. */
export const gapPp = (a: Ratio, b: Ratio, digits = 2): string =>
  roundUnits(toMicro(a) - toMicro(b), MICRO - 2, digits);

export const isLoss = (ratio: Ratio | null | undefined): boolean =>
  ratio != null && toMicro(ratio) < 0;

/** Whole-year choices from the three-year minimum (FR30) up to the history available. */
export const yearOptions = (minYears: number, maxYears: number | null): number[] =>
  maxYears == null || maxYears < minYears
    ? []
    : Array.from({ length: maxYears - minYears + 1 }, (_, i) => minYears + i);

/** The most whole years every one of `tickers` has; null if any is not in the universe. */
export const maxYearsFor = (universe: BacktestUniverse, tickers: string[]): number | null => {
  const years = tickers.map((t) => universe.stocks.find((s) => s.ticker === t)?.max_years);
  return years.length === 0 || years.some((y) => y == null)
    ? null
    : Math.min(...(years as number[]));
};

export interface MixRow {
  ticker: string;
  weight: string;
}

const WEIGHT_PATTERN = /^\d{1,3}(\.\d{1,2})?$/;

/** Sum of the weights in hundredths of a percent, so 33.33 + 33.33 + 33.34 is exactly 100. */
const totalHundredths = (rows: MixRow[]): number =>
  rows.reduce((sum, row) => {
    const [whole, fraction = ''] = row.weight.trim().split('.');
    return sum + Number(whole || 0) * 100 + Number(fraction.padEnd(2, '0'));
  }, 0);

export const mixTotal = (rows: MixRow[]): string => (totalHundredths(rows) / 100).toFixed(2);

/** i18n keys for everything that stops a mix from being sent; empty when it can be run. */
export const mixProblems = (rows: MixRow[]): string[] => {
  const problems: string[] = [];
  const tickers = rows.map((r) => r.ticker).filter(Boolean);
  if (tickers.length === 0 || tickers.length !== rows.length)
    problems.push('backtest.mix.needStock');
  if (new Set(tickers).size !== tickers.length) problems.push('backtest.mix.duplicate');
  const weightsValid = rows.every((r) => {
    const w = r.weight.trim();
    return WEIGHT_PATTERN.test(w) && Number(w) > 0 && Number(w) <= 100;
  });
  if (!weightsValid) problems.push('backtest.mix.weightInvalid');
  else if (totalHundredths(rows) !== 10000) problems.push('backtest.mix.total');
  return problems;
};

const ERROR_KEYS: Partial<Record<BacktestErrorCode, string>> = {
  insufficient_history: 'backtest.error.insufficientHistory',
  weight_too_small: 'backtest.error.weightTooSmall',
  weights_not_100: 'backtest.mix.total',
  duplicate_stocks: 'backtest.mix.duplicate',
  unknown_stock: 'backtest.error.unknownStock',
  split_not_supported: 'backtest.error.splitNotSupported',
  risk_free_unavailable: 'backtest.error.riskFree',
  portfolio_not_found: 'backtest.error.portfolioNotFound',
  backtest_not_found: 'backtest.error.notFound',
};

export const errorMessageKey = (code: string | null | undefined): string =>
  ERROR_KEYS[code as BacktestErrorCode] ?? 'common.errorGeneric';

export interface ChartRow {
  date: string;
  portfolio: number;
  startDateRules?: number;
  benchmark: number;
  kse100?: number;
}

/** Rupee values as numbers for drawing only; every figure shown as text uses the strings. */
export const chartRows = (series: BacktestSeriesPoint[]): ChartRow[] =>
  series.map((p) => ({
    date: p.date,
    portfolio: Number(p.portfolio),
    ...(p.start_date_rules != null ? { startDateRules: Number(p.start_date_rules) } : {}),
    benchmark: Number(p.benchmark),
    ...(p.kse100 != null ? { kse100: Number(p.kse100) } : {}),
  }));
