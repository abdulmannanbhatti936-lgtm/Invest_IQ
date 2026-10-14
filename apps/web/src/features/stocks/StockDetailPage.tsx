import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import { getErrorStatus, stocksApi } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { HistoryPeriod, PricePoint } from '@investiq/shared-types';
import { Card, CardTitle } from '../../components/ui/Card';
import {
  DisclaimerBanner,
  ErrorState,
  Figure,
  Notice,
  Skeleton,
} from '../../components/ui/Feedback';
import { Delta } from '../../components/ui/Delta';
import { formatDate, formatPrice, formatSigned } from '../../lib/format';
import { KeyStats } from './KeyStats';
import { PredictionPanel } from './PredictionPanel';
import { PriceChart } from './PriceChart';
import { SentimentPanel } from './SentimentPanel';

const PERIODS: HistoryPeriod[] = ['1mo', '3mo', '6mo', '1y', '5y'];
const MIN_CHART_POINTS = 5;

const periodChange = (history: PricePoint[]): number | null => {
  if (history.length < 2) return null;
  const first = history[0].close;
  return ((history[history.length - 1].close - first) / first) * 100;
};

export const StockDetailPage = () => {
  const { ticker = '' } = useParams<{ ticker: string }>();
  const { t, i18n } = useTranslation();
  const [period, setPeriod] = useState<HistoryPeriod>('1y');

  const quote = useQuery({
    queryKey: ['quote', ticker],
    queryFn: () => stocksApi.getQuote(ticker),
    retry: (count, error) => getErrorStatus(error) !== 404 && count < 2,
  });
  const history = useQuery({
    queryKey: ['history', ticker, period],
    queryFn: () => stocksApi.getHistory(ticker, period),
  });
  const prediction = useQuery({
    queryKey: ['prediction', ticker],
    queryFn: () => stocksApi.getPrediction(ticker),
    retry: (count, error) => getErrorStatus(error) !== 404 && count < 2,
  });
  const sentiment = useQuery({
    queryKey: ['sentiment', ticker],
    queryFn: () => stocksApi.getSentiment(ticker),
    retry: (count, error) => getErrorStatus(error) !== 404 && count < 2,
  });

  const back = (
    <Link
      to="/stocks"
      className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-ink"
    >
      <ArrowLeft className="h-4 w-4 rtl:rotate-180" />
      {t('stockDetail.backToSearch')}
    </Link>
  );

  if (quote.isError) {
    const status = getErrorStatus(quote.error);
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        {back}
        {status === 404 ? (
          <Notice tone="warning">{t('stockDetail.notFound', { ticker })}</Notice>
        ) : (
          <ErrorState
            message={t(status === 503 ? 'stockDetail.unavailable' : 'common.errorGeneric')}
            onRetry={() => void quote.refetch()}
          />
        )}
      </div>
    );
  }

  const change = history.data ? periodChange(history.data) : null;
  const periodLabel = t(`stockDetail.periods.${period}`);
  const summary =
    change == null
      ? null
      : Math.abs(change) < 0.05
        ? t('stockDetail.summaryFlat', { period: periodLabel })
        : t(change > 0 ? 'stockDetail.summaryUp' : 'stockDetail.summaryDown', {
            pct: `${Math.abs(change).toFixed(1)}%`,
            period: periodLabel,
          });

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {back}

      {/* Header */}
      {quote.isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-32" />
          <Skeleton className="h-5 w-64" />
        </div>
      ) : (
        <div className="flex flex-col items-start justify-between gap-4 md:flex-row md:items-end">
          <div>
            <h1 className="text-3xl font-bold text-ink" dir="ltr">
              {quote.data.ticker}
            </h1>
            <p className="text-lg text-muted" dir="ltr">
              {quote.data.name}
            </p>
            {quote.data.sector && <p className="mt-2 text-sm text-muted">{quote.data.sector}</p>}
          </div>
          <div className="md:text-end">
            <p className="text-3xl font-bold text-ink">
              <Figure>{formatPrice(quote.data.price)}</Figure>
            </p>
            <p className="flex flex-wrap items-baseline gap-2 text-base md:justify-end">
              <span className="text-muted">{t('stockDetail.dayChange')}</span>
              {quote.data.change != null && quote.data.change_percent != null ? (
                <Delta value={quote.data.change}>
                  {`${formatSigned(quote.data.change)} (${formatSigned(quote.data.change_percent)}%)`}
                </Delta>
              ) : (
                <span className="text-muted">—</span>
              )}
            </p>
            <p className="mt-2 text-xs text-muted">
              {t('stockDetail.closeAsOf', {
                date: formatDate(quote.data.timestamp, i18n.language),
              })}
            </p>
          </div>
        </div>
      )}

      {/* Chart (Design.md §7.2: chart → key stats → prediction) */}
      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <div>
            <CardTitle>{t('stockDetail.chartTitle')}</CardTitle>
            {summary && <p className="mt-2 text-sm font-medium text-muted">{summary}</p>}
          </div>
          <div className="flex gap-2" role="group" aria-label={t('stockDetail.chartTitle')}>
            {PERIODS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPeriod(p)}
                aria-pressed={period === p}
                className={`rounded-control px-4 py-2 text-sm font-medium ${
                  period === p ? 'bg-primary text-inverse' : 'text-muted hover:bg-sunken'
                }`}
              >
                {t(`stockDetail.periodShort.${p}`)}
              </button>
            ))}
          </div>
        </div>
        {history.isPending ? (
          <Skeleton className="h-[360px] w-full" />
        ) : history.isError ? (
          <ErrorState
            message={t(
              getErrorStatus(history.error) === 503
                ? 'stockDetail.unavailable'
                : 'common.errorGeneric',
            )}
            onRetry={() => void history.refetch()}
          />
        ) : history.data.length < MIN_CHART_POINTS ? (
          // PRD.md FR10
          <Notice tone="warning">{t('stockDetail.insufficientHistory')}</Notice>
        ) : (
          <>
            <PriceChart history={history.data} prediction={prediction.data} />
            <p className="mt-4 text-xs text-muted">
              {t('stockDetail.chartAsOf', {
                date: formatDate(history.data[history.data.length - 1].timestamp, i18n.language),
              })}
              {' · '}
              {t('stockDetail.splitAdjusted')}
              {' · '}
              {t('stockDetail.delayNote')}
            </p>
          </>
        )}
      </Card>

      {quote.isPending ? <Skeleton className="h-40 w-full" /> : <KeyStats quote={quote.data} />}

      <PredictionPanel query={prediction} ticker={ticker} />

      <SentimentPanel query={sentiment} ticker={ticker.toUpperCase()} />

      <DisclaimerBanner />
    </div>
  );
};
