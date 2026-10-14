import type { UseQueryResult } from '@tanstack/react-query';
import { ExternalLink } from 'lucide-react';
import { getErrorDetail, getErrorStatus } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { SentimentHeadline, StockSentiment } from '@investiq/shared-types';
import { Card } from '../../components/ui/Card';
import { ErrorState, Notice, Skeleton } from '../../components/ui/Feedback';
import { formatDate, formatPct } from '../../lib/format';
import { SentimentBadge } from './badges';
import { lastUpdated, weightShare } from './sentimentView';

const HeadlineItem = ({
  headline,
  sentiment,
}: {
  headline: SentimentHeadline;
  sentiment: StockSentiment;
}) => {
  const { t, i18n } = useTranslation();
  const share = weightShare(headline, sentiment);
  const date = formatDate(headline.published_at, i18n.language);
  return (
    <li className="py-4">
      <a
        href={headline.url}
        target="_blank"
        rel="noopener noreferrer"
        className="group inline-flex items-start gap-2 font-medium text-ink hover:text-primary"
        aria-label={`${headline.headline}. ${t('sentiment.openSource', { source: headline.source_name, date })}`}
      >
        {/* Headlines are in English as published; they keep their own direction in RTL */}
        <bdi dir="ltr">{headline.headline}</bdi>
        <ExternalLink
          className="mt-2 h-3.5 w-3.5 shrink-0 text-muted group-hover:text-primary"
          aria-hidden="true"
        />
      </a>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted">
        <span>
          {headline.source_name} · {date}
        </span>
        {headline.label ? (
          <SentimentBadge label={headline.label} probability={headline.label_probability} />
        ) : (
          <span>{t('sentiment.pending')}</span>
        )}
        {share != null && <span>{t('sentiment.share', { pct: formatPct(share) })}</span>}
        {headline.scorer === 'vader' && <span>{t('sentiment.scoredByVader')}</span>}
      </div>
    </li>
  );
};

const HeadlineList = ({
  headlines,
  sentiment,
}: {
  headlines: SentimentHeadline[];
  sentiment: StockSentiment;
}) => (
  <ul className="divide-y divide-line">
    {headlines.map((h) => (
      <HeadlineItem key={`${h.source}:${h.url}`} headline={h} sentiment={sentiment} />
    ))}
  </ul>
);

const Drivers = ({ sentiment }: { sentiment: StockSentiment }) => {
  const { t } = useTranslation();
  const listed = sentiment.headlines;
  const after = sentiment.after_close_headlines;
  if (!listed.length && !after.length) return null;
  return (
    // Open by default: the headlines are the reason the badge says what it says (PRD FR21)
    <details open className="rounded-control bg-sunken p-4 text-sm">
      <summary className="cursor-pointer font-medium text-ink">
        {t('sentiment.driversTitle')}
      </summary>
      <p className="mt-2 text-xs text-muted">{t('sentiment.probabilityNote')}</p>
      {listed.length > 0 && <HeadlineList headlines={listed} sentiment={sentiment} />}
      {after.length > 0 && (
        <div className="mt-4">
          <p className="font-medium text-ink">{t('sentiment.afterCloseTitle')}</p>
          <p className="text-xs text-muted">{t('sentiment.afterCloseNote')}</p>
          <HeadlineList headlines={after} sentiment={sentiment} />
        </div>
      )}
    </details>
  );
};

const StaleNotice = ({ sentiment }: { sentiment: StockSentiment }) => {
  const { t, i18n } = useTranslation();
  if (!sentiment.freshness.stale) return null;
  const updated = lastUpdated(sentiment);
  return (
    <Notice tone="warning">
      {updated
        ? t('sentiment.stale', { date: formatDate(updated, i18n.language) })
        : t('sentiment.staleNever')}
    </Notice>
  );
};

const Summary = ({ sentiment }: { sentiment: StockSentiment }) => {
  const { t, i18n } = useTranslation();
  const date = sentiment.as_of_date ? formatDate(sentiment.as_of_date, i18n.language) : '—';
  if (!sentiment.label) {
    return (
      <Notice>
        {t('sentiment.noNews', {
          ticker: sentiment.ticker,
          days: sentiment.window_trading_days,
          date,
        })}
      </Notice>
    );
  }
  return (
    <div className="space-y-2">
      <SentimentBadge label={sentiment.label} large />
      <p className="text-sm text-muted">
        {t('sentiment.basis', {
          count: sentiment.counted_headlines,
          days: sentiment.window_trading_days,
          date,
          halfLife: sentiment.half_life_trading_days,
        })}
      </p>
    </div>
  );
};

export const SentimentPanel = ({
  query,
  ticker,
}: {
  query: UseQueryResult<StockSentiment>;
  ticker: string;
}) => {
  const { t } = useTranslation();

  const body = () => {
    if (query.isPending) {
      return (
        <div className="space-y-4">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-72" />
          <Skeleton className="h-24 w-full" />
        </div>
      );
    }
    if (query.isError) {
      // Scoped to this panel: the rest of the page keeps working (Design.md §12.3)
      if (getErrorStatus(query.error) === 404) {
        return (
          <Notice>
            <p className="font-medium text-ink">{t('sentiment.notCoveredTitle')}</p>
            <p className="mt-2">
              {t('sentiment.notCovered', {
                ticker,
                stocks: getErrorDetail(query.error)?.covered_stock_count,
              })}
            </p>
          </Notice>
        );
      }
      return <ErrorState message={t('sentiment.loadError')} onRetry={() => void query.refetch()} />;
    }
    const sentiment = query.data;
    return (
      <div className="space-y-4">
        <StaleNotice sentiment={sentiment} />
        <Summary sentiment={sentiment} />
        <Drivers sentiment={sentiment} />
        <p className="text-xs text-muted">{t('sentiment.note')}</p>
      </div>
    );
  };

  return (
    <Card>
      <h2 className="text-lg font-semibold text-ink">{t('sentiment.title')}</h2>
      <p className="mt-2 mb-6 text-sm text-muted">{t('sentiment.subtitle', { ticker })}</p>
      {body()}
    </Card>
  );
};
