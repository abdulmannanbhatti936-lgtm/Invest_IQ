import { useState, type ReactNode } from 'react';
import { ChevronDown, Info, MinusCircle } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import type { FilerStatus, PortfolioHolding, PortfolioRates } from '@investiq/shared-types';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { Figure } from '../../components/ui/Feedback';
import { formatDate, formatMoney, formatPctString, withSign } from '../../lib/format';
import { CHARGE_ORDER, isNegative } from './portfolioView';

/** One labelled figure on a line: label on the start side, value on the end side. */
export const Line = ({
  label,
  value,
  strong = false,
  note,
}: {
  label: ReactNode;
  value: ReactNode;
  strong?: boolean;
  note?: ReactNode;
}) => (
  <div
    className={`flex items-baseline justify-between gap-4 py-1 ${strong ? 'font-semibold' : ''}`}
  >
    <span className="text-gray-600">
      {label}
      {note && <span className="ms-2 text-xs text-amber-700">{note}</span>}
    </span>
    <Figure className={strong ? 'text-gray-900' : 'text-gray-800'}>{value}</Figure>
  </div>
);

const EstimateBadge = () => {
  const { t } = useTranslation();
  return <Badge variant="warning">{t('portfolio.estimate')}</Badge>;
};

const BuyBlock = ({ holding, rates }: { holding: PortfolioHolding; rates: PortfolioRates }) => {
  const { t } = useTranslation();
  return (
    <section className="space-y-1 text-sm">
      <h4 className="font-medium text-gray-900">{t('portfolio.holding.buyTitle')}</h4>
      <Line
        label={t('portfolio.holding.sharesAt', {
          shares: holding.shares,
          price: formatMoney(holding.price),
        })}
        value={formatMoney(holding.gross)}
      />
      <details className="group">
        <summary className="flex cursor-pointer list-none items-baseline justify-between gap-4 py-1">
          <span className="flex items-center gap-1 text-gray-600">
            {t('portfolio.holding.chargesTotal')}
            <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
            <span className="sr-only">{t('portfolio.holding.showCharges')}</span>
          </span>
          <Figure>{formatMoney(holding.charges.total)}</Figure>
        </summary>
        <div className="ms-3 border-s border-gray-200 ps-3 text-xs">
          {CHARGE_ORDER.map((key) => (
            <Line
              key={key}
              label={t(`portfolio.holding.charges.${key}`)}
              value={formatMoney(holding.charges[key])}
              note={rates.unverified.includes(key) ? t('portfolio.unconfirmed') : undefined}
            />
          ))}
        </div>
      </details>
      <div className="border-t border-gray-100 pt-1">
        <Line
          label={t('portfolio.holding.totalCost')}
          value={formatMoney(holding.total_cost)}
          strong
        />
      </div>
    </section>
  );
};

const ExitBlock = ({
  holding,
  filerStatus,
}: {
  holding: PortfolioHolding;
  filerStatus: FilerStatus;
}) => {
  const { t } = useTranslation();
  const exit = holding.forecast_exit;
  const loss = isNegative(exit.net_return);
  const noTax = Number(exit.cgt) === 0;
  return (
    <section className="space-y-1 rounded-lg bg-gray-50 p-4 text-sm">
      <div className="flex items-center justify-between gap-2">
        <h4 className="font-medium text-gray-900">{t('portfolio.holding.exitTitle')}</h4>
        <EstimateBadge />
      </div>
      <p className="text-xs leading-relaxed text-gray-600">
        {t('portfolio.holding.exitNote', { pct: formatPctString(holding.round_trip_pct) })}
      </p>
      <Line label={t('portfolio.holding.exitPrice')} value={formatMoney(exit.price)} />
      <Line label={t('portfolio.holding.saleValue')} value={formatMoney(exit.gross)} />
      <Line
        label={t('portfolio.holding.sellCharges')}
        value={`− ${formatMoney(exit.charges.total)}`}
      />
      {noTax ? (
        <p className="py-1 text-xs text-gray-600">{t('portfolio.holding.cgtNone')}</p>
      ) : (
        <Line label={t('portfolio.holding.cgt')} value={`− ${formatMoney(exit.cgt)}`} />
      )}
      {filerStatus === 'non_filer' && (
        <p className="text-xs text-gray-600">{t('portfolio.holding.cgtNonFiler')}</p>
      )}
      <div className="border-t border-gray-200 pt-1">
        <Line
          label={t('portfolio.holding.netResult')}
          value={
            <span className={loss ? 'text-red-700' : 'text-green-700'}>
              {loss ? '▼' : '▲'} {formatMoney(exit.net_return)} (
              {formatPctString(exit.net_return_pct, true)})
            </span>
          }
          strong
        />
      </div>
    </section>
  );
};

const DividendBlock = ({ holding, language }: { holding: PortfolioHolding; language: string }) => {
  const { t } = useTranslation();
  const dividends = holding.dividends;
  if (!dividends) {
    return <p className="text-sm text-gray-600">{t('portfolio.holding.dividendsNone')}</p>;
  }
  return (
    <section className="space-y-1 text-sm">
      <div className="flex items-center justify-between gap-2">
        <h4 className="font-medium text-gray-900">{t('portfolio.holding.dividendsTitle')}</h4>
        <EstimateBadge />
      </div>
      <p className="text-xs text-gray-600">
        {t('portfolio.holding.dividendsBasis', {
          perShare: dividends.per_share,
          start: formatDate(dividends.period_start, language),
          end: formatDate(dividends.period_end, language),
        })}
      </p>
      <Line label={t('portfolio.holding.dividendsGross')} value={formatMoney(dividends.gross)} />
      <Line
        label={t('portfolio.holding.wht', { pct: formatPctString(dividends.wht_rate_pct) })}
        value={`− ${formatMoney(dividends.wht)}`}
      />
      <Line label={t('portfolio.holding.dividendsNet')} value={formatMoney(dividends.net)} strong />
      <p className="text-xs text-gray-500">{t('portfolio.holding.dividendsSource')}</p>
      <p className="text-xs text-gray-500">{t('portfolio.holding.dividendsNote')}</p>
    </section>
  );
};

const WhyThisStock = ({ holding }: { holding: PortfolioHolding }) => {
  const { t } = useTranslation();
  const why = holding.why;
  return (
    <details className="rounded-lg border border-gray-100 p-4 text-sm">
      <summary className="flex cursor-pointer list-none items-center gap-2 font-medium text-gray-900">
        <Info className="h-4 w-4 text-gray-400" />
        {t('portfolio.holding.whyTitle')}
      </summary>
      <ul className="mt-3 space-y-2 leading-relaxed text-gray-700">
        <li>{t('portfolio.holding.whyRisk', { vol: formatPctString(why.volatility_pct) })}</li>
        <li>
          {t('portfolio.holding.whyForecast', {
            price: formatMoney(why.forecast_price),
            change: formatPctString(why.expected_change_pct, true),
          })}
          {why.low_confidence_reasons.length > 0 && (
            <span className="mt-1 block text-amber-800">
              {t('portfolio.holding.whyLowConfidence')}{' '}
              {why.low_confidence_reasons
                .map((reason) =>
                  t(`prediction.reason.${reason}`, {
                    threshold: Math.round(why.low_confidence_threshold * 100),
                    ticker: holding.ticker,
                  }),
                )
                .join(' ')}
            </span>
          )}
        </li>
        <li>
          {t('portfolio.holding.whySignal', { signal: t(`prediction.signal.${why.signal}`) })}
        </li>
        <li>
          {why.sentiment_label && why.counted_headlines > 0
            ? t('portfolio.holding.whyNews', {
                label: t(`sentiment.label.${why.sentiment_label}`),
                count: why.counted_headlines,
              })
            : t('portfolio.holding.whyNoNews')}
        </li>
        <li>{t('portfolio.holding.whyTilt', { pp: withSign(why.tilt_effect_pp) })}</li>
      </ul>
      <p className="mt-3 text-xs text-gray-500">{t('portfolio.holding.whyNote')}</p>
    </details>
  );
};

export const HoldingCard = ({
  holding,
  rates,
  filerStatus,
  onExclude,
  excluding,
}: {
  holding: PortfolioHolding;
  rates: PortfolioRates;
  filerStatus: FilerStatus;
  onExclude: (ticker: string) => void;
  excluding: boolean;
}) => {
  const { t, i18n } = useTranslation();
  const [confirming, setConfirming] = useState(false);
  return (
    <Card className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            <bdi dir="ltr">{holding.ticker}</bdi>
          </h3>
          <p className="text-sm text-gray-500">{holding.name}</p>
          {holding.sector && <p className="text-xs text-gray-400">{holding.sector}</p>}
        </div>
        <Badge variant="primary" className="text-sm">
          {t('portfolio.holding.allocation', {
            pct: formatPctString(Number(holding.allocation_pct).toFixed(2)),
          })}
        </Badge>
      </div>

      <div>
        <p className="text-sm text-gray-600">{t('portfolio.holding.breakEven')}</p>
        <Figure className="text-3xl font-semibold text-gray-900">
          {formatMoney(holding.break_even_price)}
        </Figure>
        <p className="mt-1 text-xs text-gray-500">
          {t('portfolio.holding.breakEvenChange', {
            pct: formatPctString(holding.break_even_change_pct),
            price: formatMoney(holding.price),
          })}
        </p>
        <p className="mt-1 text-xs text-gray-500">{t('portfolio.holding.breakEvenHelp')}</p>
      </div>

      <BuyBlock holding={holding} rates={rates} />
      <ExitBlock holding={holding} filerStatus={filerStatus} />
      <DividendBlock holding={holding} language={i18n.language} />
      <WhyThisStock holding={holding} />

      <div className="border-t border-gray-100 pt-4">
        {confirming ? (
          <div className="space-y-3">
            <p className="text-sm text-gray-800">
              {t('portfolio.holding.excludeConfirm', { ticker: holding.ticker })}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="destructive"
                isLoading={excluding}
                onClick={() => onExclude(holding.ticker)}
              >
                {t('portfolio.holding.excludeYes')}
              </Button>
              <Button variant="secondary" onClick={() => setConfirming(false)} disabled={excluding}>
                {t('portfolio.form.cancel')}
              </Button>
            </div>
          </div>
        ) : (
          <Button variant="secondary" onClick={() => setConfirming(true)}>
            <MinusCircle className="me-2 h-4 w-4" />
            {t('portfolio.holding.exclude')}
          </Button>
        )}
      </div>
    </Card>
  );
};
