import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowLeftRight,
  Check,
  ShieldCheck,
  Wallet,
} from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import type { AppNotification, NotificationType } from '@investiq/shared-types';
import { Badge } from '../../components/ui/Badge';
import { Button, buttonClasses } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { Delta } from '../../components/ui/Delta';
import { Figure } from '../../components/ui/Feedback';
import { formatDate, formatMoney, formatPctString } from '../../lib/format';
import { ConfidencePill, SentimentBadge } from '../stocks/badges';
import { isLowConfidence } from './notificationView';

const TYPE_ICON: Record<NotificationType, typeof Wallet> = {
  roll: ArrowLeftRight,
  sell: ArrowDownRight,
  buy: Wallet,
};

type Translate = ReturnType<typeof useTranslation>['t'];

/** The headline, from the same templates the push uses. */
export const notificationTitle = (n: AppNotification, t: Translate): string => {
  if (n.rule === 'sell_forecast') {
    return t('notifications.message.sell_forecast.title', { ticker: n.params.ticker });
  }
  if (n.rule === 'roll_suggested') {
    return t('notifications.message.roll_suggested.title', {
      ticker: n.params.ticker,
      to: n.params.replacement.ticker,
    });
  }
  return t('portfolio.idle.flaggedTitle', { amount: formatMoney(n.params.amount) });
};

/** The one-line reasoning summary; every figure is a stored value, only formatted. */
export const notificationSummary = (n: AppNotification, t: Translate, language: string): string => {
  if (n.rule === 'sell_forecast') {
    return t('notifications.message.sell_forecast.summary', {
      ticker: n.params.ticker,
      date: formatDate(n.params.as_of, language),
      from: t(`prediction.signal.${n.params.from_signal}`),
    });
  }
  if (n.rule === 'roll_suggested') {
    return t('notifications.message.roll_suggested.summary', {
      ticker: n.params.ticker,
      gap: formatPctString(n.params.relative_return_pct, true),
      days: n.params.trading_days,
      threshold: formatPctString(n.params.threshold_pct),
    });
  }
  return t('notifications.message.idle_cash.summary', { amount: formatMoney(n.params.amount) });
};

const Row = ({ label, children }: { label: string; children: ReactNode }) => (
  <div className="flex items-baseline justify-between gap-4 py-2">
    <dt className="text-muted">{label}</dt>
    <dd className="text-end font-medium text-ink">{children}</dd>
  </div>
);

const Money = ({ value }: { value: string | null | undefined }) => (
  <Figure>{formatMoney(value)}</Figure>
);

const Figures = ({ title, children }: { title: string; children: ReactNode }) => (
  <div className="rounded-control border border-line bg-sunken px-4 py-2">
    <p className="pt-2 text-sm font-semibold text-ink">{title}</p>
    <dl className="divide-y divide-line text-sm">{children}</dl>
  </div>
);

const Details = ({ n }: { n: AppNotification }) => {
  const { t } = useTranslation();
  if (n.rule === 'sell_forecast') {
    const { sale } = n.params;
    return (
      <div className="space-y-2">
        <p className="text-sm text-ink">
          {n.params.sentiment_label && n.params.counted_headlines > 0
            ? t('notifications.message.sell_forecast.news', {
                label: t(`sentiment.label.${n.params.sentiment_label}`),
              })
            : t('portfolio.holding.whyNoNews')}
        </p>
        <Figures
          title={t('notifications.message.sell_forecast.saleTitle', {
            shares: n.params.shares,
            price: formatMoney(n.params.price),
          })}
        >
          <Row label={t('portfolio.holding.saleValue')}>
            <Money value={sale.gross} />
          </Row>
          <Row label={t('portfolio.holding.sellCharges')}>
            <Money value={sale.charges_total} />
          </Row>
          <Row label={t('portfolio.holding.cgt')}>
            <Money value={sale.cgt} />
          </Row>
          {sale.net_return != null && (
            <Row label={t('portfolio.holding.netResult')}>
              <Delta value={sale.net_return}>{formatMoney(sale.net_return)}</Delta>
            </Row>
          )}
        </Figures>
        {n.params.filer_status === 'non_filer' && (
          <p className="text-xs text-muted">{t('portfolio.holding.cgtNonFiler')}</p>
        )}
      </div>
    );
  }
  if (n.rule === 'roll_suggested') {
    const { sale, purchase, replacement } = n.params;
    return (
      <div className="space-y-2">
        <p className="text-sm text-ink">
          {t('portfolio.roll.status.suggested', {
            to: replacement.ticker,
            benefit: formatMoney(n.params.expected_benefit),
            cost: formatMoney(n.params.switch_cost),
          })}
        </p>
        <Figures
          title={t('notifications.message.roll_suggested.buyTitle', { to: replacement.ticker })}
        >
          <Row label={t('portfolio.holding.saleValue')}>
            <Money value={sale.gross} />
          </Row>
          <Row label={t('portfolio.holding.sellCharges')}>
            <Money value={sale.charges_total} />
          </Row>
          <Row label={t('portfolio.holding.cgt')}>
            <Money value={sale.cgt} />
          </Row>
          <Row
            label={t('portfolio.holding.sharesAt', {
              shares: purchase.shares,
              price: formatMoney(replacement.price),
            })}
          >
            <Money value={purchase.gross} />
          </Row>
          <Row label={t('portfolio.holding.chargesTotal')}>
            <Money value={purchase.charges_total} />
          </Row>
          <Row label={t('notifications.message.roll_suggested.switchCost')}>
            <Money value={n.params.switch_cost} />
          </Row>
          <Row label={t('notifications.message.roll_suggested.expectedGain')}>
            <Money value={n.params.expected_benefit} />
          </Row>
        </Figures>
      </div>
    );
  }
  const blocked = Object.entries(n.params.blocked_by);
  return (
    <div className="space-y-2 text-sm text-ink">
      {blocked.length > 0 && (
        <ul className="list-disc space-y-2 ps-6">
          {blocked.map(([ticker, cap]) => (
            <li key={ticker}>{t(`portfolio.idle.${cap}`, { ticker })}</li>
          ))}
        </ul>
      )}
      <p className="text-muted">{t('portfolio.idle.flaggedSuggestion')}</p>
    </div>
  );
};

const StrengthBadges = ({ n }: { n: AppNotification }) => {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap items-center gap-2">
      {n.strength === 'strong' && (
        <Badge variant="primary">
          <ShieldCheck className="h-4 w-4" aria-hidden="true" />
          {t('notifications.strength.strong')}
        </Badge>
      )}
      {n.strength === 'watch' && (
        <Badge variant="warning">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          {t('notifications.strength.watch')}
        </Badge>
      )}
      {n.rule === 'sell_forecast' && (
        <ConfidencePill
          value={Number(n.params.confidence_score)}
          threshold={n.params.low_confidence_threshold}
          low={isLowConfidence(n)}
        />
      )}
      {n.rule === 'sell_forecast' && n.params.sentiment_label && n.params.counted_headlines > 0 && (
        <SentimentBadge label={n.params.sentiment_label} />
      )}
    </div>
  );
};

/**
 * One suggestion (Design.md §7.5): the action, the reasoning, the figures behind it and a link
 * to the screen that shows the reason, never a dead end. `compact` is the bell's version.
 */
export const NotificationCard = ({
  n,
  compact = false,
  onOpen,
  onMarkRead,
  marking = false,
}: {
  n: AppNotification;
  compact?: boolean;
  onOpen: (n: AppNotification) => void;
  onMarkRead?: (n: AppNotification) => void;
  marking?: boolean;
}) => {
  const { t, i18n } = useTranslation();
  const Icon = TYPE_ICON[n.type];
  const title = notificationTitle(n, t);
  const header = (
    <div className="flex items-start gap-4">
      <span
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-tint text-primary"
        aria-hidden="true"
      >
        <Icon className="h-4 w-4 rtl:-scale-x-100" />
      </span>
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className={`text-ink ${compact ? 'text-sm' : 'text-base'} font-semibold`}>
            {!n.read && (
              <span className="me-2 inline-block h-2 w-2 rounded-full bg-primary align-middle">
                <span className="sr-only">{t('notifications.unread')}</span>
              </span>
            )}
            {title}
          </h3>
          <span className="text-xs text-muted tabular-nums">
            {formatDate(n.sent_at, i18n.language)}
          </span>
        </div>
        <p className={`text-sm text-muted ${compact ? 'line-clamp-2' : ''}`}>
          {notificationSummary(n, t, i18n.language)}
        </p>
      </div>
    </div>
  );

  if (compact) {
    return (
      <Link
        to={n.link}
        onClick={() => onOpen(n)}
        className={`block rounded-control px-4 py-4 transition-colors hover:bg-sunken ${
          n.read ? '' : 'bg-primary-tint/40'
        }`}
      >
        {header}
      </Link>
    );
  }

  return (
    <Card className="space-y-4" data-notification-id={n.id}>
      {header}
      <StrengthBadges n={n} />
      {n.strength === 'watch' && (
        <p className="text-xs text-muted">{t('notifications.watchHelp')}</p>
      )}
      <Details n={n} />
      {n.data_as_of && (
        <p className="text-xs text-muted">
          {t('notifications.dataAsOf', { date: formatDate(n.data_as_of, i18n.language) })}
        </p>
      )}
      <p className="border-t border-line pt-4 text-xs text-muted">{t('notifications.advisory')}</p>
      <div className="flex flex-wrap gap-2">
        <Link to={n.link} onClick={() => onOpen(n)} className={buttonClasses('primary')}>
          {t('notifications.seeReason')}
        </Link>
        {!n.read && onMarkRead && (
          <Button variant="secondary" isLoading={marking} onClick={() => onMarkRead(n)}>
            <Check className="h-4 w-4" aria-hidden="true" />
            {t('notifications.markRead')}
          </Button>
        )}
      </div>
    </Card>
  );
};
