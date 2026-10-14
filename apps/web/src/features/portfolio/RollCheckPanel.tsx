import { useMutation } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { portfolioApi } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { RollHolding } from '@investiq/shared-types';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Card, CardTitle } from '../../components/ui/Card';
import { ErrorState } from '../../components/ui/Feedback';
import { formatDate, formatMoney, formatPctString } from '../../lib/format';

const STATUS_VARIANT: Record<RollHolding['status'], 'neutral' | 'warning' | 'primary'> = {
  too_early: 'neutral',
  not_triggered: 'neutral',
  no_replacement: 'warning',
  costs_exceed_benefit: 'warning',
  suggested: 'primary',
};

export const RollCheckPanel = ({ portfolioId }: { portfolioId: string }) => {
  const { t, i18n } = useTranslation();
  const check = useMutation({ mutationFn: () => portfolioApi.rollCheck(portfolioId) });
  const result = check.data;

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl">
          <CardTitle>{t('portfolio.roll.title')}</CardTitle>
          <p className="mt-2 text-sm text-muted">{t('portfolio.roll.intro')}</p>
        </div>
        <Button variant="secondary" isLoading={check.isPending} onClick={() => check.mutate()}>
          <RefreshCw className="me-2 h-4 w-4" />
          {t('portfolio.roll.button')}
        </Button>
      </div>

      {check.isError && (
        <ErrorState message={t('common.errorGeneric')} onRetry={() => check.mutate()} />
      )}

      {result && (
        <div className="space-y-4">
          <p className="text-xs text-muted">
            {t('portfolio.roll.benchmark', {
              count: result.benchmark.stock_count,
              date: formatDate(result.benchmark.since, i18n.language),
              pct: formatPctString(result.benchmark.return_pct, true),
            })}{' '}
            {t('portfolio.roll.checkedAt', { date: formatDate(result.checked_at, i18n.language) })}
          </p>
          <ul className="divide-y divide-line">
            {result.holdings.map((holding) => (
              <li key={holding.ticker} className="flex flex-wrap items-baseline gap-4 py-2 text-sm">
                <Badge variant={STATUS_VARIANT[holding.status]}>
                  <bdi dir="ltr">{holding.ticker}</bdi>
                </Badge>
                <span className="text-ink">
                  {t(`portfolio.roll.status.${holding.status}`, {
                    days: holding.trading_days,
                    required: result.required_trading_days,
                    relative: formatPctString(holding.relative_return_pct, true),
                    threshold: formatPctString(holding.threshold_pct),
                    to: holding.replacement?.ticker,
                    cost: formatMoney(holding.switch_cost),
                    benefit: formatMoney(holding.expected_benefit),
                  })}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
};
