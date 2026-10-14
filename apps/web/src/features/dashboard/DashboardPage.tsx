import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, ArrowRight, Briefcase, History, MessageSquare } from 'lucide-react';
import { getErrorStatus, portfolioApi, riskProfileApi } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { Portfolio } from '@investiq/shared-types';
import { useAuth } from '../auth/AuthContext';
import { RETAKE_PATH } from '../auth/guardRules';
import { RiskBadge } from '../onboarding/RiskBadge';
import { AllocationChart } from '../portfolio/AllocationChart';
import { ConfidencePill, SentimentBadge } from '../stocks/badges';
import { buttonClasses } from '../../components/ui/Button';
import { Card, CardTitle } from '../../components/ui/Card';
import { CompanyName } from '../../components/ui/CompanyName';
import { CountUp } from '../../components/ui/CountUp';
import { Delta } from '../../components/ui/Delta';
import {
  DisclaimerBanner,
  EmptyState,
  ErrorState,
  Figure,
  Skeleton,
} from '../../components/ui/Feedback';
import { PageHeader } from '../../components/ui/PageHeader';
import { formatDate, formatMoney, formatPctString } from '../../lib/format';
import { ratioToPct } from '../backtest/backtestView';

const HIGHLIGHTS = 4;

/** The holdings whose forecasts moved most, largest first (from the portfolio's own data). */
const highlights = (portfolio: Portfolio) =>
  [...portfolio.holdings]
    .sort(
      (a, b) =>
        Math.abs(Number(b.why.expected_change_pct)) - Math.abs(Number(a.why.expected_change_pct)),
    )
    .slice(0, HIGHLIGHTS);

const QUICK_LINKS = [
  { key: 'portfolio', to: '/portfolio', icon: Briefcase },
  { key: 'backtest', to: '/backtest', icon: History },
  { key: 'chat', to: '/chat', icon: MessageSquare },
] as const;

export const DashboardPage = () => {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const date = (iso: string) => formatDate(iso, i18n.language);

  const profile = useQuery({ queryKey: ['risk-profile'], queryFn: riskProfileApi.get });
  const portfolio = useQuery({
    queryKey: ['portfolio', 'current'],
    queryFn: portfolioApi.current,
    retry: (count, error) => getErrorStatus(error) !== 404 && count < 2,
  });
  const noPortfolio = portfolio.isError && getErrorStatus(portfolio.error) === 404;
  const firstName = user?.full_name.split(' ')[0] ?? '';

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('dashboard.welcome', { name: firstName })}
        subtitle={t('dashboard.subtitle')}
      />

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Risk profile */}
        <Card className="flex flex-col gap-4">
          <CardTitle className="text-sm font-medium text-muted">
            {t('dashboard.riskTitle')}
          </CardTitle>
          {profile.isPending ? (
            <div className="space-y-2">
              <Skeleton className="h-8 w-32" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          ) : profile.isError ? (
            <ErrorState message={t('common.errorGeneric')} onRetry={() => profile.refetch()} />
          ) : (
            <>
              <span className="self-start">
                <RiskBadge category={profile.data.category} size="lg" />
              </span>
              <p className="text-sm text-ink">{t(`risk.description.${profile.data.category}`)}</p>
              <div className="mt-auto flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-muted">
                  {t('dashboard.updated', { date: date(profile.data.updated_at) })}
                </p>
                <Link to={RETAKE_PATH} className={buttonClasses('ghost')}>
                  {t('dashboard.retake')}
                </Link>
              </div>
            </>
          )}
        </Card>

        {/* Portfolio */}
        <Card className="lg:col-span-2">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
            <CardTitle>{t('dashboard.portfolioTitle')}</CardTitle>
            {portfolio.data && (
              <Link to="/portfolio" className={buttonClasses('secondary')}>
                {t('dashboard.viewPortfolio')}
                <ArrowRight className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
              </Link>
            )}
          </div>
          {portfolio.isPending ? (
            <div className="flex items-center gap-6">
              <Skeleton className="h-44 w-44 shrink-0 rounded-full" />
              <div className="w-full space-y-2">
                {[0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-4 w-full" />
                ))}
              </div>
            </div>
          ) : noPortfolio ? (
            <EmptyState
              icon={Briefcase}
              title={t('dashboard.portfolioEmptyTitle')}
              action={
                <Link to="/portfolio" className={buttonClasses('primary')}>
                  {t('dashboard.buildPortfolio')}
                </Link>
              }
            >
              {t('dashboard.portfolioEmptyBody')}
            </EmptyState>
          ) : portfolio.isError ? (
            <ErrorState message={t('common.errorGeneric')} onRetry={() => portfolio.refetch()} />
          ) : (
            <div className="space-y-6">
              <dl className="grid grid-cols-3 gap-4">
                {[
                  { label: t('portfolio.totals.cost'), value: portfolio.data.totals.cost },
                  { label: t('portfolio.totals.cash'), value: portfolio.data.totals.idle_cash },
                ].map(({ label, value }) => (
                  <div key={label} className="space-y-1">
                    <dt className="text-xs text-muted">{label}</dt>
                    <dd className="text-lg font-semibold text-ink sm:text-xl">
                      <Figure>
                        <CountUp
                          value={Number(value)}
                          format={(n) => formatMoney(n.toFixed(2))}
                          exact={formatMoney(value)}
                        />
                      </Figure>
                    </dd>
                  </div>
                ))}
                <div className="space-y-1">
                  <dt className="text-xs text-muted">{t('dashboard.holdings')}</dt>
                  <dd className="text-lg font-semibold text-ink tabular-nums sm:text-xl">
                    {portfolio.data.holdings.length}
                  </dd>
                </div>
              </dl>
              <AllocationChart holdings={portfolio.data.holdings} size={160} compact />
              <p className="text-xs text-muted">
                {t('dashboard.builtOn', {
                  date: date(portfolio.data.generated_at),
                  asOf: date(portfolio.data.prices_as_of),
                })}
              </p>
            </div>
          )}
        </Card>
      </div>

      {portfolio.data && (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Latest backtest */}
          <Card className="flex flex-col gap-4">
            <CardTitle className="text-sm font-medium text-muted">
              {t('dashboard.backtestTitle')}
            </CardTitle>
            {portfolio.data.latest_backtest ? (
              <>
                <div className="space-y-1">
                  <Delta value={portfolio.data.latest_backtest.total_return} className="text-3xl">
                    {formatPctString(ratioToPct(portfolio.data.latest_backtest.total_return), true)}
                  </Delta>
                  <p className="text-xs text-muted">
                    {t('backtest.report.headline')} ·{' '}
                    {t('dashboard.backtestPeriod', {
                      start: date(portfolio.data.latest_backtest.period_start),
                      end: date(portfolio.data.latest_backtest.period_end),
                      years: portfolio.data.latest_backtest.years,
                    })}
                  </p>
                </div>
                <p className="flex gap-2 rounded-control border border-warning bg-warning-tint p-2 text-xs text-ink">
                  <AlertTriangle
                    className="mt-1 h-4 w-4 shrink-0 text-warning"
                    aria-hidden="true"
                  />
                  {t('dashboard.hindsightShort')}
                </p>
                <Link
                  to={`/backtest/${portfolio.data.latest_backtest.id}`}
                  className={`${buttonClasses('ghost')} mt-auto self-start`}
                >
                  {t('dashboard.openReport')}
                  <ArrowRight className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
                </Link>
              </>
            ) : (
              <>
                <p className="text-sm text-muted">{t('dashboard.backtestNone')}</p>
                <Link to="/backtest" className={`${buttonClasses('secondary')} self-start`}>
                  {t('portfolio.backtestLink')}
                </Link>
              </>
            )}
          </Card>

          {/* Forecast and news highlights */}
          <Card className="lg:col-span-2" padding="none">
            <div className="space-y-1 p-4 sm:p-6 sm:pb-4">
              <CardTitle>{t('dashboard.highlightsTitle')}</CardTitle>
              <p className="text-xs text-muted">
                {t('dashboard.highlightsNote', { date: date(portfolio.data.prices_as_of) })}
              </p>
            </div>
            <ul className="divide-y divide-line border-t border-line">
              {highlights(portfolio.data).map((h) => (
                <li key={h.ticker}>
                  <Link
                    to={`/stocks/${h.ticker}`}
                    className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 px-4 py-2 transition-colors hover:bg-sunken sm:grid-cols-[minmax(0,1.4fr)_auto_auto_auto] sm:px-6"
                  >
                    <span className="min-w-0">
                      <span dir="ltr" className="block font-semibold text-ink">
                        {h.ticker}
                      </span>
                      <span className="block text-xs text-muted">
                        <CompanyName name={h.name} />
                      </span>
                    </span>
                    <Delta value={h.why.expected_change_pct} className="justify-self-end text-sm">
                      {formatPctString(h.why.expected_change_pct, true)}
                    </Delta>
                    <span className="col-span-2 flex flex-wrap gap-2 sm:col-span-1">
                      <ConfidencePill
                        value={Number(h.why.confidence_score)}
                        threshold={h.why.low_confidence_threshold}
                        low={h.why.low_confidence_reasons.length > 0}
                      />
                    </span>
                    <span className="hidden sm:block">
                      {h.why.sentiment_label ? (
                        <SentimentBadge label={h.why.sentiment_label} />
                      ) : (
                        <span className="text-xs text-muted">{t('dashboard.noNews')}</span>
                      )}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}

      <nav aria-label={t('dashboard.quickTitle')} className="grid gap-4 sm:grid-cols-3">
        {QUICK_LINKS.map(({ key, to, icon: Icon }) => (
          <Link
            key={key}
            to={to}
            className="group flex items-start gap-4 rounded-card border border-line bg-surface p-4 shadow-e1 transition-[transform,box-shadow] duration-150 ease-enter hover:-translate-y-0.5 hover:shadow-e2"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-tint text-primary">
              <Icon className="h-5 w-5" aria-hidden="true" />
            </span>
            <span className="min-w-0 space-y-1">
              <span className="block font-semibold text-ink">
                {t(`dashboard.quick.${key}.title`)}
              </span>
              <span className="block text-sm text-muted">{t(`dashboard.quick.${key}.body`)}</span>
            </span>
          </Link>
        ))}
      </nav>

      <DisclaimerBanner />
    </div>
  );
};
