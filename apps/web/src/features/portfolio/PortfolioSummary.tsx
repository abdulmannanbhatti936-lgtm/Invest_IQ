import { AlertTriangle, ChevronDown } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import type { Portfolio } from '@investiq/shared-types';
import { Card } from '../../components/ui/Card';
import { Figure, Notice } from '../../components/ui/Feedback';
import { formatDate, formatMoney } from '../../lib/format';

const Tile = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-lg bg-gray-50 p-4">
    <p className="text-xs text-gray-500">{label}</p>
    <Figure className="mt-1 block whitespace-nowrap text-lg font-semibold text-gray-900 sm:text-xl">
      {value}
    </Figure>
  </div>
);

export const PortfolioSummary = ({ portfolio }: { portfolio: Portfolio }) => {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const { totals, idle } = portfolio;
  const blocked = Object.entries(idle.blocked_by);
  const hasCash = Number(idle.amount) > 0;

  return (
    <Card className="space-y-6">
      <div className="space-y-2">
        <p className="text-base leading-relaxed text-gray-900">
          {t('portfolio.summary', {
            category: t(`risk.${portfolio.risk_category}`),
            cost: formatMoney(totals.cost),
            count: portfolio.holdings.length,
          })}{' '}
          {hasCash && t('portfolio.summaryCash', { cash: formatMoney(idle.amount) })}
        </p>
        <p className="text-xs text-gray-500">
          {t('portfolio.pricesAsOf', { date: formatDate(portfolio.prices_as_of, language) })}
          {' · '}
          {t('portfolio.ratesAsOf', { date: formatDate(portfolio.rates.checked_on, language) })}
          {' · '}
          {t('portfolio.generatedOn', { date: formatDate(portfolio.generated_at, language) })}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile label={t('portfolio.totals.gross')} value={formatMoney(totals.gross)} />
        <Tile label={t('portfolio.totals.charges')} value={formatMoney(totals.charges)} />
        <Tile label={t('portfolio.totals.cost')} value={formatMoney(totals.cost)} />
        <Tile label={t('portfolio.totals.cash')} value={formatMoney(totals.idle_cash)} />
      </div>

      {idle.flagged ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {t('portfolio.idle.flaggedTitle', { amount: formatMoney(idle.amount) })}
          </p>
          <ul className="mt-2 list-disc space-y-1 ps-5">
            {blocked.map(([ticker, reason]) => (
              <li key={ticker}>{t(`portfolio.idle.${reason}`, { ticker })}</li>
            ))}
          </ul>
          <p className="mt-2">{t('portfolio.idle.flaggedSuggestion')}</p>
        </div>
      ) : (
        hasCash && (
          <Notice>{t('portfolio.idle.small', { amount: formatMoney(idle.amount) })}</Notice>
        )
      )}

      {portfolio.excluded_tickers.length > 0 && (
        <p className="text-sm text-gray-600">
          {t('portfolio.excluded', { tickers: portfolio.excluded_tickers.join(', ') })}
        </p>
      )}

      <details className="group text-sm text-gray-600">
        <summary className="flex cursor-pointer list-none items-center gap-1 font-medium text-gray-800">
          {t('portfolio.notModelledTitle')}
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
        </summary>
        <ul className="mt-2 list-disc space-y-1 ps-5">
          {portfolio.rates.not_modelled.map((key) => (
            <li key={key}>{t(`portfolio.notModelled.${key}`)}</li>
          ))}
        </ul>
      </details>

      <Notice>{t('portfolio.guidance')}</Notice>
    </Card>
  );
};
