// Sorting and filtering for the stock list, as pure functions (stockListView.test.ts).

export interface ListForecast {
  expectedChangePct: number;
  confidence: number;
  threshold: number;
  low: boolean;
  signal: 'BUY' | 'SELL' | 'HOLD';
}

export interface ListRow {
  ticker: string;
  name: string;
  sector: string | null;
  last_close?: number | null;
  last_close_date?: string | null;
  forecast_covered?: boolean | null;
  forecast?: ListForecast | null;
}

export type SortKey = 'ticker' | 'sector' | 'close' | 'forecast';
export type SortDir = 'asc' | 'desc';

export const DEFAULT_SORT: { key: SortKey; dir: SortDir } = { key: 'ticker', dir: 'asc' };

/** A new header click: the same column flips direction, another column starts ascending. */
export const nextSort = (current: { key: SortKey; dir: SortDir }, key: SortKey) =>
  current.key === key
    ? { key, dir: current.dir === 'asc' ? ('desc' as const) : ('asc' as const) }
    : { key, dir: 'asc' as const };

const value = (row: ListRow, key: SortKey): string | number | null => {
  switch (key) {
    case 'ticker':
      return row.ticker;
    case 'sector':
      return row.sector;
    case 'close':
      return row.last_close ?? null;
    case 'forecast':
      return row.forecast?.expectedChangePct ?? null;
  }
};

/** Missing values (no close, no forecast) always sort last, whatever the direction. */
export const sortRows = (rows: ListRow[], key: SortKey, dir: SortDir): ListRow[] =>
  [...rows].sort((a, b) => {
    const va = value(a, key);
    const vb = value(b, key);
    if (va === null && vb === null) return a.ticker.localeCompare(b.ticker);
    if (va === null) return 1;
    if (vb === null) return -1;
    const order =
      typeof va === 'number' && typeof vb === 'number'
        ? va - vb
        : String(va).localeCompare(String(vb));
    return (dir === 'asc' ? order : -order) || a.ticker.localeCompare(b.ticker);
  });

export const filterRows = (
  rows: ListRow[],
  { sector, forecastOnly }: { sector: string; forecastOnly: boolean },
): ListRow[] =>
  rows.filter(
    (r) => (sector === '' || r.sector === sector) && (!forecastOnly || r.forecast_covered),
  );

export const sectorsOf = (rows: ListRow[]): string[] =>
  [...new Set(rows.map((r) => r.sector).filter((s): s is string => Boolean(s)))].sort();
