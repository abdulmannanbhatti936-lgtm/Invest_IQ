import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { ChevronRight, Search } from 'lucide-react';
import { stocksApi } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import { Card } from '../../components/ui/Card';
import { ErrorState, Notice, Skeleton } from '../../components/ui/Feedback';

const useDebounced = <T,>(value: T, ms: number): T => {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
};

export const StocksPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const debounced = useDebounced(query.trim(), 300);

  // Empty query = browse the whole catalog (PRD.md FR9)
  const results = useQuery({
    queryKey: ['stock-search', debounced],
    queryFn: () => stocksApi.search(debounced),
    placeholderData: keepPreviousData,
    staleTime: 60 * 60 * 1000,
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-col items-start justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('stocks.title')}</h1>
          <p className="text-sm text-gray-500">{t('stocks.subtitle')}</p>
        </div>
        <div className="w-full md:w-96">
          <label htmlFor="stock-search" className="mb-1.5 block text-sm font-medium text-gray-700">
            {t('stocks.searchLabel')}
          </label>
          <div className="relative">
            <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              id="stock-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('stocks.searchPlaceholder')}
              className="h-10 w-full rounded-md border border-gray-300 bg-white ps-9 pe-3 text-sm placeholder:text-gray-400 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
        </div>
      </div>

      {results.isPending ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : results.isError ? (
        <ErrorState message={t('stocks.loadError')} onRetry={() => void results.refetch()} />
      ) : results.data.length === 0 ? (
        <Notice>{t('stocks.noResults', { query: debounced })}</Notice>
      ) : (
        <>
          <p className="text-xs text-gray-500">
            {t('stocks.resultCount', { count: results.data.length })}
          </p>
          <div
            className={`grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3 ${
              results.isPlaceholderData ? 'opacity-60' : ''
            }`}
          >
            {results.data.map((stock) => (
              <Card
                key={stock.ticker}
                className="p-4 transition-colors hover:border-blue-300"
                onClick={() => navigate(`/stocks/${encodeURIComponent(stock.ticker)}`)}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-lg font-bold" dir="ltr">
                      {stock.ticker}
                    </h3>
                    <p className="truncate text-sm text-gray-600" title={stock.name}>
                      {stock.name}
                    </p>
                    {stock.sector && (
                      <p className="mt-1 truncate text-xs text-gray-400">{stock.sector}</p>
                    )}
                  </div>
                  <ChevronRight className="h-5 w-5 shrink-0 text-gray-300 rtl:rotate-180" />
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
};
