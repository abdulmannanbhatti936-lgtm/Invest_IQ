import { useTranslation } from '@investiq/i18n';
import type { StockQuote } from '@investiq/shared-types';
import { Card, CardTitle } from '../../components/ui/Card';
import { Figure } from '../../components/ui/Feedback';
import { formatCompact, formatDate, formatPrice } from '../../lib/format';

/** Key statistics per PRD.md FR8. */
export const KeyStats = ({ quote }: { quote: StockQuote }) => {
  const { t, i18n } = useTranslation();
  const range =
    quote.low != null && quote.high != null
      ? `${formatPrice(quote.low)} – ${formatPrice(quote.high)}`
      : '—';
  const stats: [string, string][] = [
    ['previousClose', formatPrice(quote.previous_close)],
    ['open', formatPrice(quote.open)],
    ['dayRange', range],
    ['volume', formatCompact(quote.volume)],
    ['week52High', formatPrice(quote.fifty_two_week_high)],
    ['week52Low', formatPrice(quote.fifty_two_week_low)],
    ['marketCap', quote.market_cap != null ? `Rs. ${formatCompact(quote.market_cap)}` : '—'],
  ];

  return (
    <Card>
      <div className="mb-4 flex items-baseline justify-between">
        <CardTitle>{t('stockDetail.statsTitle')}</CardTitle>
        <span className="text-xs text-gray-400">
          {t('stockDetail.asOf', { date: formatDate(quote.timestamp, i18n.language) })}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-4">
        {stats.map(([key, value]) => (
          <div key={key}>
            <dt className="text-xs text-gray-500">{t(`stockDetail.stats.${key}`)}</dt>
            <dd className="mt-1 text-base font-medium">
              <Figure>{value}</Figure>
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
};
