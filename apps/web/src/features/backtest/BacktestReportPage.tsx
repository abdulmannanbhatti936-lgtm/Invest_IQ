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
import { formatDate, formatMoney, formatPctString, formatPp } from '../../lib/format';
import { BacktestChart } from './BacktestChart';
import { MetricsTable } from './MetricsTable';
import { gapPp, isLoss, ratioToPct } from './backtestView';

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
  return (
    <Card className="space-y-3">
      <p className="text-sm text-gray-500">{t('backtest.report.headline')}</p>
      <Figure
        className={`block text-4xl font-semibold ${
          isLoss(metrics.total_return) ? 'text-red-700' : 'text-gray-900'
        }`}
      >
        {signedPct(metrics.total_return)}
      </Figure>
      <p className="text-base text-gray-900">
        {t('backtest.report.growth', {
          capital: formatMoney(result.inputs.capital),
          end: formatMoney(costs.end_value_net),
        })}
      </p>
      <p className="text-sm text-gray-600">
        {t('backtest.report.beforeSale', {
          pct: signedPct(metrics.total_return_before_sale),
          value: formatMoney(costs.end_value_before_sale),
        })}
      </p>
      <div className="space-y-1 border-t border-gray-100 pt-3 text-sm text-gray-700">
        <p>
          {t('backtest.report.benchmarkLine', {
            pct: signedPct(result.benchmark.metrics.total_return),
          })}
        </p>
        <p>
          {kse.metrics
            ? t('backtest.report.kseLine', { pct: signedPct(kse.metrics.total_return) })
            : t(
                kse.status === 'not_covering_period'
                  ? 'backtest.report.kseNotCovering'
                  : 'backtest.report.kseAwaiting',
              )}
        </p>
      </div>
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
      <dl className="max-w-xl divide-y divide-gray-100 text-sm">
        {lines.map(([key, value]) => (
          <div key={key} className="flex justify-between gap-4 py-2">
            <dt className="text-gray-600">{t(key)}</dt>
            <dd>
              <Figure className="text-gray-900">{formatMoney(value)}</Figure>
            </dd>
          </div>
        ))}
        <div className="flex justify-between gap-4 py-2 font-semibold">
          <dt className="text-gray-900">{t('backtest.costs.endNet')}</dt>
          <dd>
            <Figure className="text-gray-900">{formatMoney(c.end_value_net)}</Figure>
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
            <tr className="border-b border-gray-200 text-xs text-gray-500">
              <th scope="col" className="py-2 pe-3 text-start font-medium">
                {t('backtest.holdings.company')}
              </th>
              <th scope="col" className="px-3 py-2 text-end font-medium">
                {t('backtest.holdings.bought')}
              </th>
              <th scope="col" className="px-3 py-2 text-end font-medium">
                {t('backtest.holdings.dividends')}
              </th>
              <th scope="col" className="px-3 py-2 text-end font-medium">
                {t('backtest.holdings.sold')}
              </th>
              <th scope="col" className="ps-3 py-2 text-end font-medium">
                {t('backtest.holdings.kept')}
              </th>
            </tr>
          </thead>
          <tbody>
            {result.portfolio.holdings.map((h) => (
              <tr key={h.ticker} className="border-b border-gray-100 align-top last:border-0">
                <th scope="row" className="py-3 pe-3 text-start font-normal">
                  <bdi dir="ltr" className="block font-medium text-gray-900">
                    {h.ticker}
                  </bdi>
                  <span className="block text-xs text-gray-500">{h.name}</span>
                </th>
                <td className="px-3 py-3 text-end">
                  <span className="block whitespace-nowrap tabular-nums">
                    {trade(h.shares_bought, h.buy_price)}
                  </span>
                  <span className="block text-xs text-gray-500">
                    {formatDate(h.buy_date, i18n.language)}
                  </span>
                </td>
                <td className="px-3 py-3 text-end">
                  <Figure>{formatMoney(h.dividends_net)}</Figure>
                </td>
                <td className="px-3 py-3 text-end">
                  <span className="block whitespace-nowrap tabular-nums">
                    {trade(h.shares_sold, h.sell_price)}
                  </span>
                  <span className="block text-xs text-gray-500">
                    {formatDate(h.sell_date, i18n.language)}
                  </span>
                </td>
                <td className="ps-3 py-3 text-end">
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
        <summary className="flex cursor-pointer list-none items-center gap-1 text-base font-semibold text-gray-900">
          {t('backtest.method.title')}
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
        </summary>
        <ul className="mt-4 list-disc space-y-2 ps-5 text-sm leading-relaxed text-gray-700">
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
              className="text-blue-600 underline hover:text-blue-700"
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
        className="inline-flex items-center gap-1 text-sm font-medium text-blue-600 hover:text-blue-700"
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
            <h1 className="text-2xl font-semibold text-gray-900">
              {t(
                result.kind === 'custom'
                  ? 'backtest.report.titleCustom'
                  : 'backtest.report.titlePortfolio',
              )}
            </h1>
            <p className="mt-1 text-sm text-gray-500">
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
            <p className="text-xs leading-relaxed text-gray-500">{t('backtest.benchmarkNote')}</p>
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
