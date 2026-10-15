import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { keepPreviousData, useQueries, useQuery } from '@tanstack/react-query';
import { ArrowDown, ArrowUp, ChevronRight, Search } from 'lucide-react';
import { getErrorStatus, stocksApi } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { Prediction } from '@investiq/shared-types';
import { Card } from '../../components/ui/Card';
import { CompanyName } from '../../components/ui/CompanyName';
import { Delta } from '../../components/ui/Delta';
import { EmptyState, ErrorState, Figure, Skeleton } from '../../components/ui/Feedback';
import { fieldClasses } from '../../components/ui/Input';
import { PageHeader } from '../../components/ui/PageHeader';
import { Select } from '../../components/ui/Select';
import { formatDate, formatPrice, formatSigned, ltr } from '../../lib/format';
import { ConfidencePill } from './badges';
import {
  DEFAULT_SORT,
  filterRows,
  nextSort,
  sectorsOf,
  sortRows,
  type ListForecast,
  type ListRow,
  type SortKey,
} from './stockListView';

const useDebounced = <T,>(value: T, ms: number): T => {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
};

const toForecast = (p: Prediction): ListForecast => ({
  expectedChangePct: p.expected_change_pct,
  confidence: p.confidence_score,
  threshold: p.low_confidence_threshold,
  low: p.low_confidence,
  signal: p.signal,
});

/** KSE-100 list: search, sector filter, sort, with the last close and any forecast (FR9). */
export const StocksPage = () => {
  const { t, i18n } = useTranslation();
  const [query, setQuery] = useState('');
  const [sector, setSector] = useState('');
  const [forecastOnly, setForecastOnly] = useState(false);
  const [sort, setSort] = useState(DEFAULT_SORT);
  const debounced = useDebounced(query.trim(), 300);

  // Empty query = browse the whole catalog (PRD.md FR9)
  const results = useQuery({
    queryKey: ['stock-search', debounced],
    queryFn: () => stocksApi.search(debounced),
    placeholderData: keepPreviousData,
    staleTime: 60 * 60 * 1000,
  });

  // Forecasts only for the stocks the model covers; same cache as the stock detail screen
  const covered = (results.data ?? []).filter((s) => s.forecast_covered).map((s) => s.ticker);
  const predictions = useQueries({
    queries: covered.map((ticker) => ({
      queryKey: ['prediction', ticker],
      queryFn: () => stocksApi.getPrediction(ticker),
      retry: (count: number, error: unknown) => getErrorStatus(error) !== 404 && count < 2,
      staleTime: 10 * 60 * 1000,
    })),
  });
  const forecasts = new Map(
    predictions.flatMap((q, i) => (q.data ? [[covered[i], toForecast(q.data)] as const] : [])),
  );

  const rows: ListRow[] = (results.data ?? []).map((s) => ({
    ...s,
    forecast: forecasts.get(s.ticker) ?? null,
  }));
  const sectors = useMemo(() => sectorsOf(results.data ?? []), [results.data]);
  const visible = sortRows(filterRows(rows, { sector, forecastOnly }), sort.key, sort.dir);
  const date = (iso: string) => formatDate(iso, i18n.language);

  const SortHeader = ({ k, label, end = false }: { k: SortKey; label: string; end?: boolean }) => {
    const active = sort.key === k;
    const Arrow = sort.dir === 'asc' ? ArrowUp : ArrowDown;
    return (
      <th
        scope="col"
        aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
        className={`px-4 py-2 font-medium ${end ? 'text-end' : 'text-start'}`}
      >
        <button
          type="button"
          onClick={() => setSort(nextSort(sort, k))}
          className={`inline-flex min-h-8 items-center gap-2 rounded-control hover:text-ink ${
            active ? 'text-ink' : ''
          }`}
        >
          {label}
          {active && <Arrow className="h-4 w-4" aria-hidden="true" />}
        </button>
      </th>
    );
  };

  const ForecastCell = ({ row }: { row: ListRow }) =>
    row.forecast ? (
      <span className="flex flex-wrap items-center justify-end gap-2">
        <Delta value={row.forecast.expectedChangePct} className="text-sm">
          {ltr(`${formatSigned(row.forecast.expectedChangePct)}%`)}
        </Delta>
        <ConfidencePill
          value={row.forecast.confidence}
          threshold={row.forecast.threshold}
          low={row.forecast.low}
        />
      </span>
    ) : row.forecast_covered ? (
      <Skeleton className="ms-auto h-6 w-32" />
    ) : (
      <span className="block text-end text-xs text-muted">{t('stocks.noForecast')}</span>
    );

  return (
    <div className="space-y-6">
      <PageHeader title={t('stocks.title')} subtitle={t('stocks.subtitle')} />

      <div className="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto] md:items-end">
        <div className="flex flex-col gap-2">
          <label htmlFor="stock-search" className="text-sm font-medium text-ink">
            {t('stocks.searchLabel')}
          </label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute start-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
              aria-hidden="true"
            />
            <input
              id="stock-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('stocks.searchPlaceholder')}
              className={`h-10 ps-10 ${fieldClasses(false)}`}
            />
          </div>
        </div>
        <Select
          label={t('stocks.sectorFilter')}
          value={sector}
          onChange={(e) => setSector(e.target.value)}
        >
          <option value="">{t('stocks.allSectors')}</option>
          {sectors.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <label className="flex min-h-10 items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={forecastOnly}
            onChange={(e) => setForecastOnly(e.target.checked)}
            className="h-4 w-4 accent-[var(--iq-primary)]"
          />
          {t('stocks.forecastOnly')}
        </label>
      </div>

      {results.isPending ? (
        <Card padding="none">
          {Array.from({ length: 8 }, (_, i) => (
            <div key={i} className="flex items-center gap-4 border-b border-line px-4 py-4">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 flex-1" />
              <Skeleton className="h-4 w-24" />
            </div>
          ))}
        </Card>
      ) : results.isError ? (
        <ErrorState message={t('stocks.loadError')} onRetry={() => void results.refetch()} />
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState icon={Search} title={t('stocks.noResultsTitle')}>
            {t('stocks.noResults', { query: debounced })}
          </EmptyState>
        </Card>
      ) : (
        <Card padding="none" className={results.isPlaceholderData ? 'opacity-60' : ''}>
          <p className="border-b border-line px-4 py-2 text-xs text-muted" role="status">
            {t('stocks.resultCount', { count: visible.length })}
          </p>

          {/* Wide screens: a sortable table */}
          <table className="hidden w-full table-fixed text-sm md:table">
            <thead className="border-b border-line text-xs text-muted">
              <tr>
                <SortHeader k="ticker" label={t('stocks.columns.company')} />
                <SortHeader k="sector" label={t('stocks.columns.sector')} />
                <SortHeader k="close" label={t('stocks.columns.close')} end />
                <SortHeader k="forecast" label={t('stocks.columns.forecast')} end />
                <th className="w-10" aria-hidden="true" />
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {visible.map((row) => (
                <tr key={row.ticker} className="group relative transition-colors hover:bg-sunken">
                  <td className="w-[34%] px-4 py-2">
                    <Link
                      to={`/stocks/${encodeURIComponent(row.ticker)}`}
                      className="block after:absolute after:inset-0"
                    >
                      <span dir="ltr" className="block font-semibold text-ink">
                        {row.ticker}
                      </span>
                      <CompanyName name={row.name} className="text-xs text-muted" />
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    {row.sector && <CompanyName name={row.sector} className="text-muted" />}
                  </td>
                  <td className="px-4 py-2 text-end">
                    <Figure className="block font-semibold text-ink">
                      {formatPrice(row.last_close)}
                    </Figure>
                    {row.last_close_date && (
                      <span className="block text-xs text-muted">{date(row.last_close_date)}</span>
                    )}
                  </td>
                  <td className="w-[30%] px-4 py-2">
                    <ForecastCell row={row} />
                  </td>
                  <td className="px-2 text-muted">
                    <ChevronRight className="h-4 w-4 rtl:rotate-180" aria-hidden="true" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Phones: compact rows */}
          <ul className="divide-y divide-line md:hidden">
            {visible.map((row) => (
              <li key={row.ticker}>
                <Link
                  to={`/stocks/${encodeURIComponent(row.ticker)}`}
                  className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-2 px-4 py-2 transition-colors hover:bg-sunken"
                >
                  <span className="min-w-0">
                    <span dir="ltr" className="block font-semibold text-ink">
                      {row.ticker}
                    </span>
                    <CompanyName name={row.name} className="text-xs text-muted" />
                  </span>
                  <span className="text-end">
                    <Figure className="block font-semibold text-ink">
                      {formatPrice(row.last_close)}
                    </Figure>
                    {row.last_close_date && (
                      <span className="block text-xs text-muted">{date(row.last_close_date)}</span>
                    )}
                  </span>
                  {row.sector && (
                    <CompanyName name={row.sector} className="self-center text-xs text-muted" />
                  )}
                  <ForecastCell row={row} />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
};
