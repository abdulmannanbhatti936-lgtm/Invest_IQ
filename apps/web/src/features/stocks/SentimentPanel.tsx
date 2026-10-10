import type { UseQueryResult } from '@tanstack/react-query';
import { ExternalLink, Frown, Meh, Smile } from 'lucide-react';
import { getErrorDetail, getErrorStatus } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { SentimentHeadline, SentimentLabel, StockSentiment } from '@investiq/shared-types';
import { Badge } from '../../components/ui/Badge';
import { Card } from '../../components/ui/Card';
import { ErrorState, Figure, Notice, Skeleton } from '../../components/ui/Feedback';
import { formatDate, formatPct } from '../../lib/format';
import { formatScore, lastUpdated, splitHeadlines, weightShare } from './sentimentView';

// Mood icons, never the arrow icons of the buy/sell/hold signal (Design.md §17)
const SENTIMENT_BADGE: Record<
  SentimentLabel,
  { variant: 'success' | 'danger' | 'neutral'; icon: typeof Smile }
> = {
  positive: { variant: 'success', icon: Smile },
  negative: { variant: 'danger', icon: Frown },
  neutral: { variant: 'neutral', icon: Meh },
};

const SentimentBadge = ({ label, large = false }: { label: SentimentLabel; large?: boolean }) => {
  const { t } = useTranslation();
  const { variant, icon: Icon } = SENTIMENT_BADGE[label];
  return (
    <Badge variant={variant} className={`gap-1 ${large ? 'text-sm' : ''}`}>
      <Icon className={large ? 'h-4 w-4' : 'h-3.5 w-3.5'} aria-hidden="true" />
      {t(`sentiment.label.${label}`)}
    </Badge>
  );
};

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
    <li className="py-3">
      <a
        href={headline.url}
        target="_blank"
        rel="noopener noreferrer"
        className="group inline-flex items-start gap-1 font-medium text-gray-900 hover:text-blue-700"
        aria-label={`${headline.headline}. ${t('sentiment.openSource', { source: headline.source_name, date })}`}
      >
        {/* Headlines are in English as published; they keep their own direction in RTL */}
        <bdi dir="ltr">{headline.headline}</bdi>
        <ExternalLink
          className="mt-1 h-3.5 w-3.5 shrink-0 text-gray-400 group-hover:text-blue-700"
          aria-hidden="true"
        />
      </a>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
        <span>
          {headline.source_name} · {date}
        </span>
        {headline.label ? (
          <SentimentBadge label={headline.label} />
        ) : (
          <span>{t('sentiment.pending')}</span>
        )}
        {headline.score != null && <Figure>{formatScore(headline.score)}</Figure>}
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
  <ul className="divide-y divide-gray-100">
    {headlines.map((h) => (
      <HeadlineItem key={`${h.source}:${h.url}`} headline={h} sentiment={sentiment} />
    ))}
  </ul>
);

const Drivers = ({ sentiment }: { sentiment: StockSentiment }) => {
  const { t } = useTranslation();
  const { counted, context } = splitHeadlines(sentiment);
  const after = sentiment.after_close_headlines;
  if (!counted.length && !context.length && !after.length) return null;
  return (
    // Open by default: the headlines are the reason the badge says what it says (PRD FR21)
    <details open className="rounded-lg bg-gray-50 p-4 text-sm">
      <summary className="cursor-pointer font-medium text-gray-900">
        {t('sentiment.driversTitle')}
      </summary>
      {counted.length > 0 && <HeadlineList headlines={counted} sentiment={sentiment} />}
      {after.length > 0 && (
        <div className="mt-4">
          <p className="font-medium text-gray-900">{t('sentiment.afterCloseTitle')}</p>
          <p className="text-xs text-gray-500">{t('sentiment.afterCloseNote')}</p>
          <HeadlineList headlines={after} sentiment={sentiment} />
        </div>
      )}
      {context.length > 0 && (
        <div className="mt-4">
          <p className="font-medium text-gray-900">{t('sentiment.contextTitle')}</p>
          <p className="text-xs text-gray-500">{t('sentiment.contextNote')}</p>
          <HeadlineList headlines={context} sentiment={sentiment} />
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
  if (!sentiment.label || sentiment.score == null) {
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
      <div className="flex flex-wrap items-center gap-3">
        <SentimentBadge label={sentiment.label} large />
        <span className="text-sm text-gray-700">
          {t('sentiment.score', { score: formatScore(sentiment.score) })}
        </span>
      </div>
      <p className="text-sm text-gray-600">
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
        <div className="space-y-3">
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
            <p className="font-medium text-gray-900">{t('sentiment.notCoveredTitle')}</p>
            <p className="mt-1">
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
        <p className="text-xs text-gray-500">{t('sentiment.note')}</p>
      </div>
    );
  };

  return (
    <Card>
      <h2 className="text-lg font-semibold text-gray-900">{t('sentiment.title')}</h2>
      <p className="mt-1 mb-5 text-sm text-gray-500">{t('sentiment.subtitle', { ticker })}</p>
      {body()}
    </Card>
  );
};
