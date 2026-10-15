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
import { Button, buttonClasses } from '../../components/ui/Button';
import { Card, CardTitle } from '../../components/ui/Card';
import { donutColors } from '../../components/ui/Donut';
import { PageHeader } from '../../components/ui/PageHeader';
import { useThemeColors } from '../../lib/theme';
import {
  DisclaimerBanner,
  EmptyState,
  ErrorState,
  Notice,
  Skeleton,
} from '../../components/ui/Feedback';
import { formatDate, formatMoney, formatPctString } from '../../lib/format';
import { AllocationChart } from './AllocationChart';
import { HoldingRow } from './HoldingRow';
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
        <p className="mt-2">
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
            className="mt-4"
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
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
      <Skeleton className="h-64 w-full" />
      <div className="flex items-center gap-6 rounded-card border border-line p-6">
        <Skeleton className="h-44 w-44 shrink-0 rounded-full" />
        <div className="w-full space-y-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-4 w-full" />
          ))}
        </div>
      </div>
    </div>
    <div className="space-y-2 rounded-card border border-line p-4">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  </div>
);

export const PortfolioPage = () => {
  const { t } = useTranslation();
  const theme = useThemeColors();
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
  const colors = donutColors(portfolio?.holdings.length ?? 0, theme);
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
    <div className="flex flex-col gap-6">
      <PageHeader title={t('portfolio.title')} subtitle={t('portfolio.subtitle')} />

      {(current.isPending || profile.isPending) && <PageSkeleton />}

      {current.isError && !noPortfolio && (
        <ErrorState message={t('portfolio.error.load')} onRetry={() => void current.refetch()} />
      )}

      {noPortfolio && (
        <Card className="space-y-6">
          <EmptyState icon={Briefcase} title={t('portfolio.empty.title')}>
            {t('portfolio.empty.body')}
          </EmptyState>
          <div className="mx-auto max-w-lg">{form(t('portfolio.form.title'))}</div>
        </Card>
      )}

      {portfolio && (
        <>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
            <PortfolioSummary portfolio={portfolio} />
            <Card>
              <CardTitle className="mb-4">{t('portfolio.allocationTitle')}</CardTitle>
              <AllocationChart
                holdings={portfolio.holdings}
                center={
                  <>
                    <span className="text-2xl font-bold text-ink tabular-nums">
                      {portfolio.holdings.length}
                    </span>
                    <span className="text-xs text-muted">{t('landing.risk.companies')}</span>
                  </>
                }
              />
            </Card>
          </div>
          {exclude.isError && (
            <Notice tone="warning">{t(errorMessageKey(getErrorCode(exclude.error)))}</Notice>
          )}
          <Card padding="none">
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-4 py-4 sm:px-6">
              <CardTitle>
                {t('portfolio.holdingsTitle', { count: portfolio.holdings.length })}
              </CardTitle>
              <p className="text-xs text-muted">{t('portfolio.holdingsHint')}</p>
            </div>
            <div
              className="hidden grid-cols-[minmax(0,2fr)_repeat(4,minmax(0,1fr))_20px] gap-x-4 border-b border-line px-6 py-2 text-xs text-muted lg:grid"
              aria-hidden="true"
            >
              <span className="ps-6">{t('portfolio.columns.company')}</span>
              <span>{t('portfolio.columns.allocation')}</span>
              <span className="text-end">{t('portfolio.holding.totalCost')}</span>
              <span className="text-end">{t('portfolio.holding.breakEven')}</span>
              <span className="text-end">{t('portfolio.columns.exit')}</span>
            </div>
            <ul className="divide-y divide-line">
              {portfolio.holdings.map((holding, i) => (
                <HoldingRow
                  key={holding.ticker}
                  holding={holding}
                  color={colors[i]}
                  rates={portfolio.rates}
                  filerStatus={portfolio.filer_status}
                  excluding={exclude.isPending && exclude.variables?.ticker === holding.ticker}
                  onExclude={(ticker) => exclude.mutate({ id: portfolio.id, ticker })}
                />
              ))}
            </ul>
          </Card>
          <RollCheckPanel key={portfolio.id} portfolioId={portfolio.id} />
          <Link to="/backtest" className={`${buttonClasses('secondary')} self-start`}>
            <History className="h-4 w-4" aria-hidden="true" />
            {t('portfolio.backtestLink')}
          </Link>
          <Card>
            <details>
              <summary className="cursor-pointer text-base font-semibold text-ink">
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
