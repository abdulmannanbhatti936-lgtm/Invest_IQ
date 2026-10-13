import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Briefcase } from 'lucide-react';
import {
  backtestApi,
  getErrorCode,
  getErrorDetail,
  getErrorStatus,
  portfolioApi,
} from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { BacktestResult, Portfolio, RunBacktestRequest } from '@investiq/shared-types';
import { Button } from '../../components/ui/Button';
import { Card, CardTitle } from '../../components/ui/Card';
import { DisclaimerBanner, ErrorState, Notice, Skeleton } from '../../components/ui/Feedback';
import { Select } from '../../components/ui/Select';
import { formatDate, formatMoney } from '../../lib/format';
import { CustomMixForm } from './CustomMixForm';
import { errorMessageKey, maxYearsFor, yearOptions } from './backtestView';

/** The API's reason a test could not run, with the stocks and dates it names. */
export const RunError = ({ error }: { error: unknown }) => {
  const { t, i18n } = useTranslation();
  const code = getErrorCode(error);
  const detail = getErrorDetail(error) ?? {};
  const params: Record<string, string> = {};
  if (code === 'insufficient_history') {
    const stocks = (detail.stocks as { ticker: string; first_date: string | null }[]) ?? [];
    params.date = formatDate(String(detail.required_start), i18n.language);
    params.stocks = stocks
      .map((s) =>
        s.first_date ? `${s.ticker} (${formatDate(s.first_date, i18n.language)})` : s.ticker,
      )
      .join(', ');
  }
  if (Array.isArray(detail.tickers)) params.tickers = (detail.tickers as string[]).join(', ');
  if (typeof detail.ticker === 'string') params.ticker = detail.ticker;
  return <Notice tone="warning">{t(errorMessageKey(code), params)}</Notice>;
};

const PortfolioRun = ({
  portfolio,
  maxYears,
  minYears,
  onRun,
  running,
  error,
}: {
  portfolio: Portfolio;
  maxYears: number | null;
  minYears: number;
  onRun: (years: number) => void;
  running: boolean;
  error: unknown;
}) => {
  const { t } = useTranslation();
  const options = yearOptions(minYears, maxYears);
  const [years, setYears] = useState(minYears);
  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-700">
        {t('backtest.landing.portfolioSummary', {
          category: t(`risk.${portfolio.risk_category}`),
          companies: portfolio.holdings.length,
          capital: formatMoney(portfolio.capital),
        })}
      </p>
      <div className="max-w-xs">
        <Select
          label={t('backtest.landing.period')}
          value={years}
          onChange={(e) => setYears(Number(e.target.value))}
        >
          {options.map((y) => (
            <option key={y} value={y}>
              {t('backtest.landing.yearsOption', { years: y })}
            </option>
          ))}
        </Select>
      </div>
      {error != null && <RunError error={error} />}
      <Button onClick={() => onRun(years)} isLoading={running} disabled={options.length === 0}>
        {running ? t('backtest.landing.running') : t('backtest.landing.run')}
      </Button>
    </div>
  );
};

export const BacktestPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [source, setSource] = useState<'portfolio' | 'custom' | null>(null);

  const universe = useQuery({ queryKey: ['backtest', 'universe'], queryFn: backtestApi.universe });
  const current = useQuery({
    queryKey: ['portfolio', 'current'],
    queryFn: portfolioApi.current,
    retry: (count, error) => getErrorStatus(error) !== 404 && count < 2,
  });
  const run = useMutation({
    mutationFn: backtestApi.run,
    onSuccess: (result: BacktestResult) => {
      queryClient.setQueryData(['backtest', result.id], result);
      navigate(`/backtest/${result.id}`);
    },
  });
  const start = (body: RunBacktestRequest, from: 'portfolio' | 'custom') => {
    setSource(from);
    run.mutate(body);
  };

  const noPortfolio = current.isError && getErrorStatus(current.error) === 404;
  const portfolio = current.data;
  const data = universe.data;

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">{t('backtest.title')}</h1>
        <p className="mt-1 text-sm text-gray-500">{t('backtest.subtitle')}</p>
      </div>

      {(universe.isPending || current.isPending) && (
        <div className="space-y-6" aria-busy="true">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-80 w-full" />
        </div>
      )}

      {universe.isError && (
        <ErrorState
          message={t('backtest.landing.loadError')}
          onRetry={() => void universe.refetch()}
        />
      )}

      {data && data.stocks.length === 0 && <Notice>{t('backtest.landing.noPrices')}</Notice>}

      {data && data.stocks.length > 0 && !current.isPending && (
        <>
          <Card className="space-y-4">
            <CardTitle>{t('backtest.landing.portfolioTitle')}</CardTitle>
            {portfolio && (
              <PortfolioRun
                portfolio={portfolio}
                minYears={data.min_years}
                maxYears={maxYearsFor(
                  data,
                  portfolio.holdings.map((h) => h.ticker),
                )}
                onRun={(years) => start({ years, portfolio_id: portfolio.id }, 'portfolio')}
                running={run.isPending && source === 'portfolio'}
                error={run.isError && source === 'portfolio' ? run.error : null}
              />
            )}
            {noPortfolio && (
              <div className="flex flex-col items-start gap-3">
                <div className="flex items-center gap-3 text-sm text-gray-600">
                  <Briefcase className="h-5 w-5 shrink-0 text-gray-400" />
                  {t('backtest.landing.noPortfolio')}
                </div>
                <Link
                  to="/portfolio"
                  className="text-sm font-medium text-blue-600 hover:text-blue-700"
                >
                  {t('backtest.landing.buildPortfolio')}
                </Link>
              </div>
            )}
            {current.isError && !noPortfolio && (
              <ErrorState
                message={t('portfolio.error.load')}
                onRetry={() => void current.refetch()}
              />
            )}
          </Card>

          <Card className="space-y-4">
            <div>
              <CardTitle>{t('backtest.landing.mixTitle')}</CardTitle>
              <p className="mt-1 text-sm text-gray-600">{t('backtest.landing.mixBody')}</p>
            </div>
            <CustomMixForm
              universe={data}
              onSubmit={(body) => start(body, 'custom')}
              submitting={run.isPending && source === 'custom'}
              serverError={
                run.isError && source === 'custom' ? <RunError error={run.error} /> : undefined
              }
            />
          </Card>
        </>
      )}

      <DisclaimerBanner />
    </div>
  );
};
