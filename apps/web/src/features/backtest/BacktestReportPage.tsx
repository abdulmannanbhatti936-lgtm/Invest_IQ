import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, ChevronDown } from 'lucide-react';
import { backtestApi, getErrorStatus } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { BacktestResult } from '@investiq/shared-types';
import { Card, CardTitle } from '../../components/ui/Card';
import {
  DisclaimerBanner,
  ErrorState,
  Figure,
  Notice,
  Skeleton,
} from '../../components/ui/Feedback';
import { CountUp } from '../../components/ui/CountUp';
import { Delta } from '../../components/ui/Delta';
import { formatDate, formatMoney, formatPctString, formatPp } from '../../lib/format';
import { BacktestChart } from './BacktestChart';
import { MetricsTable } from './MetricsTable';
import { gapPp, ratioToPct } from './backtestView';

const signedPct = (ratio: string) => formatPctString(ratioToPct(ratio), true);

const ReportSkeleton = () => (
  <div className="space-y-6" aria-busy="true">
    <Skeleton className="h-40 w-full" />
    <Skeleton className="h-80 w-full" />
    <Skeleton className="h-64 w-full" />
  </div>
);

const Headline = ({ result }: { result: BacktestResult }) => {
  const { t } = useTranslation();
  const { metrics, costs } = result.portfolio;
  const kse = result.kse100;
  const total = metrics.total_return;
  return (
    <Card className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <div className="space-y-4">
        <p className="text-sm text-muted">{t('backtest.report.headline')}</p>
        {/* Gains ▲ and losses ▼ with their colour, never colour alone (Design.md §6.3) */}
        <Delta value={ratioToPct(total)} className="text-4xl sm:text-5xl">
          <CountUp
            value={Number(ratioToPct(total))}
            format={(n) => formatPctString(n.toFixed(2), true)}
            exact={signedPct(total)}
          />
        </Delta>
        <p className="text-base text-ink">
          {t('backtest.report.growth', {
            capital: formatMoney(result.inputs.capital),
            end: formatMoney(costs.end_value_net),
          })}
        </p>
        <p className="text-sm text-muted">
          {t('backtest.report.beforeSale', {
            pct: signedPct(metrics.total_return_before_sale),
            value: formatMoney(costs.end_value_before_sale),
          })}
        </p>
      </div>
      <dl className="space-y-4 rounded-control border border-line bg-sunken p-4 text-sm">
        <div className="space-y-2">
          <dt className="text-muted">{t('backtest.report.benchmarkName')}</dt>
          <dd>
            <Delta value={ratioToPct(result.benchmark.metrics.total_return)} className="text-xl">
              {signedPct(result.benchmark.metrics.total_return)}
            </Delta>
          </dd>
        </div>
        <div className="space-y-2 border-t border-line pt-4">
          <dt className="text-muted">{t('backtest.columns.kse100')}</dt>
          <dd className="text-ink">
            {kse.metrics ? (
              <Delta value={ratioToPct(kse.metrics.total_return)} className="text-xl">
                {signedPct(kse.metrics.total_return)}
              </Delta>
            ) : (
              t(
                kse.status === 'not_covering_period'
                  ? 'backtest.report.kseNotCovering'
                  : 'backtest.report.kseAwaiting',
              )
            )}
          </dd>
        </div>
      </dl>
    </Card>
  );
};

const GapNote = ({ result }: { result: BacktestResult }) => {
  const { t, i18n } = useTranslation();
  const rules = result.start_date_rules;
  if (rules.status === 'not_applicable') return null;
  if (rules.status === 'available' && rules.metrics) {
    const pp = gapPp(result.portfolio.metrics.total_return, rules.metrics.total_return);
    return <Notice>{t('backtest.gap.available', { pp: formatPp(pp) })}</Notice>;
  }
  return (
    <Notice>
      {t(
        rules.reason === 'capital_too_low' ? 'backtest.gap.capitalTooLow' : 'backtest.gap.tooFew',
        { date: formatDate(result.period.start, i18n.language) },
      )}
    </Notice>
  );
};

const CostsCard = ({ result }: { result: BacktestResult }) => {
  const { t } = useTranslation();
  const c = result.portfolio.costs;
  const lines: [string, string][] = [
    ['backtest.costs.capital', result.inputs.capital],
    ['backtest.costs.buyCharges', c.buy_charges],
    ['backtest.costs.idleCash', c.idle_cash],
    ['backtest.costs.dividends', c.dividends_gross],
    ['backtest.costs.wht', c.wht],
    ['backtest.costs.endBeforeSale', c.end_value_before_sale],
    ['backtest.costs.sellCharges', c.sell_charges],
    ['backtest.costs.cgt', c.cgt],
  ];
  return (
    <Card>
      <CardTitle className="mb-4">{t('backtest.costs.title')}</CardTitle>
      <dl className="max-w-xl divide-y divide-line text-sm">
        {lines.map(([key, value]) => (
          <div key={key} className="flex justify-between gap-4 py-2">
            <dt className="text-muted">{t(key)}</dt>
            <dd>
              <Figure className="text-ink">{formatMoney(value)}</Figure>
            </dd>
          </div>
        ))}
        <div className="flex justify-between gap-4 py-2 font-semibold">
          <dt className="text-ink">{t('backtest.costs.endNet')}</dt>
          <dd>
            <Figure className="text-ink">{formatMoney(c.end_value_net)}</Figure>
          </dd>
        </div>
      </dl>
    </Card>
  );
};

const HoldingsCard = ({ result }: { result: BacktestResult }) => {
  const { t, i18n } = useTranslation();
  const trade = (shares: number, price: string) =>
    t('backtest.holdings.trade', { shares, price: formatMoney(price) });
  return (
    <Card>
      <CardTitle className="mb-4">{t('backtest.holdings.title')}</CardTitle>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-line text-xs text-muted">
              <th scope="col" className="py-2 pe-4 text-start font-medium">
                {t('backtest.holdings.company')}
              </th>
              <th scope="col" className="px-4 py-2 text-end font-medium">
                {t('backtest.holdings.bought')}
              </th>
              <th scope="col" className="px-4 py-2 text-end font-medium">
                {t('backtest.holdings.dividends')}
              </th>
              <th scope="col" className="px-4 py-2 text-end font-medium">
                {t('backtest.holdings.sold')}
              </th>
              <th scope="col" className="ps-4 py-2 text-end font-medium">
                {t('backtest.holdings.kept')}
              </th>
            </tr>
          </thead>
          <tbody>
            {result.portfolio.holdings.map((h) => (
              <tr key={h.ticker} className="border-b border-line align-top last:border-0">
                <th scope="row" className="py-4 pe-4 text-start font-normal">
                  <bdi dir="ltr" className="block font-medium text-ink">
                    {h.ticker}
                  </bdi>
                  <span className="block text-xs text-muted">{h.name}</span>
                </th>
                <td className="px-4 py-4 text-end">
                  <span className="block whitespace-nowrap tabular-nums">
                    {trade(h.shares_bought, h.buy_price)}
                  </span>
                  <span className="block text-xs text-muted">
                    {formatDate(h.buy_date, i18n.language)}
                  </span>
                </td>
                <td className="px-4 py-4 text-end">
                  <Figure>{formatMoney(h.dividends_net)}</Figure>
                </td>
                <td className="px-4 py-4 text-end">
                  <span className="block whitespace-nowrap tabular-nums">
                    {trade(h.shares_sold, h.sell_price)}
                  </span>
                  <span className="block text-xs text-muted">
                    {formatDate(h.sell_date, i18n.language)}
                  </span>
                </td>
                <td className="ps-4 py-4 text-end">
                  <Figure className="font-medium">{formatMoney(h.sale_net)}</Figure>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};

const MethodCard = ({ result }: { result: BacktestResult }) => {
  const { t, i18n } = useTranslation();
  const rf = result.risk_free;
  const yieldPct = (ratio: string | null) =>
    ratio == null ? '—' : formatPctString(ratioToPct(ratio));
  return (
    <Card>
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-2 text-base font-semibold text-ink">
          {t('backtest.method.title')}
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
        </summary>
        <ul className="mt-4 list-disc space-y-2 ps-6 text-sm leading-relaxed text-ink">
          <li>{t('backtest.method.buyHold')}</li>
          <li>{t('backtest.method.rates', { version: result.assumptions.rates_version })}</li>
          <li>{t('backtest.method.dividends')}</li>
          <li>
            {t('backtest.method.prices', {
              date: formatDate(result.assumptions.prices_as_of, i18n.language),
              days: result.assumptions.carried_forward_days,
            })}
          </li>
          <li>
            {t('backtest.method.riskFree', {
              start: yieldPct(rf.yield_at_start),
              low: yieldPct(rf.lowest_yield),
              high: yieldPct(rf.highest_yield),
            })}{' '}
            <a
              href={rf.source_url}
              className="text-primary underline hover:text-primary"
              target="_blank"
              rel="noreferrer"
            >
              {t('backtest.method.source')}
            </a>
          </li>
          <li>{t('backtest.method.annualise')}</li>
          <li>{t('backtest.method.winRate')}</li>
        </ul>
      </details>
    </Card>
  );
};

export const BacktestReportPage = () => {
  const { id = '' } = useParams();
  const { t, i18n } = useTranslation();
  const query = useQuery({
    queryKey: ['backtest', id],
    queryFn: () => backtestApi.get(id),
    retry: (count, error) => getErrorStatus(error) !== 404 && count < 2,
  });
  const result = query.data;

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <Link
        to="/backtest"
        className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-primary"
      >
        <ArrowLeft className="h-4 w-4 rtl:rotate-180" />
        {t('backtest.report.newTest')}
      </Link>

      {query.isPending && <ReportSkeleton />}
      {query.isError && (
        <ErrorState
          message={t(
            getErrorStatus(query.error) === 404 ? 'backtest.error.notFound' : 'backtest.error.load',
          )}
          onRetry={getErrorStatus(query.error) === 404 ? undefined : () => void query.refetch()}
        />
      )}

      {result && (
        <>
          <div>
            <h1 className="text-2xl font-semibold text-ink">
              {t(
                result.kind === 'custom'
                  ? 'backtest.report.titleCustom'
                  : 'backtest.report.titlePortfolio',
              )}
            </h1>
            <p className="mt-2 text-sm text-muted">
              {t('backtest.report.period', {
                start: formatDate(result.period.start, i18n.language),
                end: formatDate(result.period.end, i18n.language),
                years: result.period.years,
                days: result.period.trading_days,
              })}
            </p>
          </div>

          <Notice tone="warning">
            {t(
              result.kind === 'custom'
                ? 'backtest.report.hindsightCustom'
                : 'backtest.report.hindsightPortfolio',
            )}
          </Notice>

          <Headline result={result} />

          <Card className="space-y-4">
            <CardTitle>{t('backtest.chart.title')}</CardTitle>
            <BacktestChart result={result} />
          </Card>

          <Card className="space-y-4">
            <MetricsTable result={result} />
            <GapNote result={result} />
            <p className="text-xs leading-relaxed text-muted">{t('backtest.benchmarkNote')}</p>
          </Card>

          <CostsCard result={result} />
          <HoldingsCard result={result} />

          <MethodCard result={result} />
        </>
      )}

      <DisclaimerBanner />
    </div>
  );
};
