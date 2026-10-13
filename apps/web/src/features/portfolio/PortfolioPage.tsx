import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Briefcase, History } from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  getErrorCode,
  getErrorDetail,
  getErrorStatus,
  portfolioApi,
  riskProfileApi,
} from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { GeneratePortfolioRequest, Portfolio } from '@investiq/shared-types';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { DisclaimerBanner, ErrorState, Notice, Skeleton } from '../../components/ui/Feedback';
import { formatDate, formatMoney, formatPctString } from '../../lib/format';
import { HoldingCard } from './HoldingCard';
import { PortfolioForm, type PortfolioFormInitial } from './PortfolioForm';
import { PortfolioSummary } from './PortfolioSummary';
import { RollCheckPanel } from './RollCheckPanel';
import { errorMessageKey, lowCapitalFrom } from './portfolioView';

const CURRENT = ['portfolio', 'current'];

const formInitial = (portfolio: Portfolio): PortfolioFormInitial => ({
  capital: portfolio.capital,
  filerStatus: portfolio.filer_status,
  shariahOnly: portfolio.shariah_only,
  commissionPct:
    portfolio.commission_pct === portfolio.rates.commission_floor_pct
      ? ''
      : portfolio.commission_pct,
});

/** The explanation shown instead of an unbalanced portfolio (FR28), or another API error. */
const GenerateError = ({
  error,
  lastRequest,
  onRetry,
}: {
  error: unknown;
  lastRequest: GeneratePortfolioRequest | null;
  onRetry: (body: GeneratePortfolioRequest) => void;
}) => {
  const { t, i18n } = useTranslation();
  const detail = getErrorDetail(error);
  const lowCapital = lowCapitalFrom(detail);
  if (lowCapital && lastRequest) {
    const category = t(`risk.${lowCapital.riskCategory}`);
    const capital = formatMoney(lastRequest.capital);
    return (
      <Notice tone="warning">
        <p className="font-semibold">{t('portfolio.lowCapital.title', { category })}</p>
        <p className="mt-1">
          {lowCapital.minimumCapital
            ? t('portfolio.lowCapital.body', {
                capital,
                category,
                count: lowCapital.minHoldings,
                pct: formatPctString(lowCapital.maxStockWeightPct),
                minimum: formatMoney(lowCapital.minimumCapital),
                date: formatDate(lowCapital.pricesAsOf, i18n.language),
              })
            : t('portfolio.lowCapital.noMinimum', { capital, category })}
        </p>
        {lowCapital.minimumCapital && (
          <Button
            variant="secondary"
            className="mt-3"
            onClick={() => onRetry({ ...lastRequest, capital: lowCapital.minimumCapital! })}
          >
            {t('portfolio.lowCapital.useMinimum', {
              minimum: formatMoney(lowCapital.minimumCapital),
            })}
          </Button>
        )}
      </Notice>
    );
  }
  const code = getErrorCode(error);
  const message =
    code === 'invalid_commission_rate'
      ? t('portfolio.form.commissionRange', {
          floor: formatPctString(detail?.commission_floor_pct as string | undefined),
          max: formatPctString(detail?.commission_max_pct as string | undefined),
        })
      : t(errorMessageKey(code));
  return <Notice tone="warning">{message}</Notice>;
};

const PageSkeleton = () => (
  <div className="space-y-6" aria-busy="true">
    <Skeleton className="h-40 w-full" />
    <div className="grid gap-6 lg:grid-cols-2">
      <Skeleton className="h-96 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  </div>
);

export const PortfolioPage = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [lastRequest, setLastRequest] = useState<GeneratePortfolioRequest | null>(null);
  const [excluded, setExcluded] = useState<string[] | null>(null);

  const profile = useQuery({ queryKey: ['risk-profile'], queryFn: riskProfileApi.get });
  const current = useQuery({
    queryKey: CURRENT,
    queryFn: portfolioApi.current,
    retry: (count, error) => getErrorStatus(error) !== 404 && count < 2,
  });
  const show = (portfolio: Portfolio) => {
    queryClient.setQueryData(CURRENT, portfolio);
    setExcluded(null);
  };
  const generate = useMutation({ mutationFn: portfolioApi.generate, onSuccess: show });
  const exclude = useMutation({
    mutationFn: ({ id, ticker }: { id: string; ticker: string }) =>
      portfolioApi.excludeStock(id, ticker),
    onSuccess: show,
  });

  const submit = (body: GeneratePortfolioRequest) => {
    setLastRequest(body);
    generate.mutate(body);
  };

  const portfolio = current.data;
  const category = profile.data?.category;
  const excludedNow = excluded ?? portfolio?.excluded_tickers ?? [];
  const noPortfolio = current.isError && getErrorStatus(current.error) === 404;

  const form = (title?: string) =>
    category && (
      <PortfolioForm
        key={portfolio?.id ?? 'new'}
        title={title}
        category={category}
        initial={portfolio ? formInitial(portfolio) : undefined}
        excluded={excludedNow}
        onIncludeAgain={(ticker) => setExcluded(excludedNow.filter((t) => t !== ticker))}
        onSubmit={submit}
        submitting={generate.isPending}
        serverError={
          generate.isError ? (
            <GenerateError error={generate.error} lastRequest={lastRequest} onRetry={submit} />
          ) : undefined
        }
      />
    );

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">{t('portfolio.title')}</h1>
        <p className="mt-1 text-sm text-gray-500">{t('portfolio.subtitle')}</p>
      </div>

      {(current.isPending || profile.isPending) && <PageSkeleton />}

      {current.isError && !noPortfolio && (
        <ErrorState message={t('portfolio.error.load')} onRetry={() => void current.refetch()} />
      )}

      {noPortfolio && (
        <Card className="space-y-8">
          <div className="flex flex-col items-center text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-blue-50">
              <Briefcase className="h-8 w-8 text-blue-600" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900">{t('portfolio.empty.title')}</h2>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-gray-500">
              {t('portfolio.empty.body')}
            </p>
          </div>
          <div className="mx-auto max-w-lg">{form(t('portfolio.form.title'))}</div>
        </Card>
      )}

      {portfolio && (
        <>
          <PortfolioSummary portfolio={portfolio} />
          {exclude.isError && (
            <Notice tone="warning">{t(errorMessageKey(getErrorCode(exclude.error)))}</Notice>
          )}
          <div className="grid gap-6 lg:grid-cols-2">
            {portfolio.holdings.map((holding) => (
              <HoldingCard
                key={holding.ticker}
                holding={holding}
                rates={portfolio.rates}
                filerStatus={portfolio.filer_status}
                excluding={exclude.isPending && exclude.variables?.ticker === holding.ticker}
                onExclude={(ticker) => exclude.mutate({ id: portfolio.id, ticker })}
              />
            ))}
          </div>
          <RollCheckPanel key={portfolio.id} portfolioId={portfolio.id} />
          <Link
            to="/backtest"
            className="inline-flex items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            <History className="h-4 w-4" />
            {t('portfolio.backtestLink')}
          </Link>
          <Card>
            <details>
              <summary className="cursor-pointer text-base font-semibold text-gray-900">
                {t('portfolio.form.rebuildTitle')}
              </summary>
              <div className="mt-6 max-w-lg">{form()}</div>
            </details>
          </Card>
        </>
      )}

      <DisclaimerBanner />
    </div>
  );
};
