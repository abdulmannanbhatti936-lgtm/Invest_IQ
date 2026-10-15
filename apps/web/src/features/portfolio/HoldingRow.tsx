import { useState, type ReactNode } from 'react';
import { ChevronDown, Info, MinusCircle } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import type { FilerStatus, PortfolioHolding, PortfolioRates } from '@investiq/shared-types';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { CompanyName } from '../../components/ui/CompanyName';
import { Delta } from '../../components/ui/Delta';
import { Figure } from '../../components/ui/Feedback';
import { formatDate, formatMoney, formatPctString, withSign } from '../../lib/format';
import { allocationLabel } from './AllocationChart';
import { CHARGE_ORDER } from './portfolioView';

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
    className={`flex items-baseline justify-between gap-4 py-2 ${strong ? 'font-semibold' : ''}`}
  >
    <span className="text-muted">
      {label}
      {note && <span className="ms-2 text-xs text-warning">{note}</span>}
    </span>
    <Figure className={strong ? 'text-ink' : 'text-ink'}>{value}</Figure>
  </div>
);

const EstimateBadge = () => {
  const { t } = useTranslation();
  return <Badge variant="warning">{t('portfolio.estimate')}</Badge>;
};

const BuyBlock = ({ holding, rates }: { holding: PortfolioHolding; rates: PortfolioRates }) => {
  const { t } = useTranslation();
  return (
    <section className="space-y-2 text-sm">
      <h4 className="font-medium text-ink">{t('portfolio.holding.buyTitle')}</h4>
      <Line
        label={t('portfolio.holding.sharesAt', {
          shares: holding.shares,
          price: formatMoney(holding.price),
        })}
        value={formatMoney(holding.gross)}
      />
      <details className="group">
        <summary className="flex cursor-pointer list-none items-baseline justify-between gap-4 py-2">
          <span className="flex items-center gap-2 text-muted">
            {t('portfolio.holding.chargesTotal')}
            <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
            <span className="sr-only">{t('portfolio.holding.showCharges')}</span>
          </span>
          <Figure>{formatMoney(holding.charges.total)}</Figure>
        </summary>
        <div className="ms-4 border-s border-line ps-4 text-xs">
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
      <div className="border-t border-line pt-2">
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
  const noTax = Number(exit.cgt) === 0;
  return (
    <section className="space-y-2 rounded-control bg-sunken p-4 text-sm">
      <div className="flex items-center justify-between gap-2">
        <h4 className="font-medium text-ink">{t('portfolio.holding.exitTitle')}</h4>
        <EstimateBadge />
      </div>
      <p className="text-xs leading-relaxed text-muted">
        {t('portfolio.holding.exitNote', { pct: formatPctString(holding.round_trip_pct) })}
      </p>
      <Line label={t('portfolio.holding.exitPrice')} value={formatMoney(exit.price)} />
      <Line label={t('portfolio.holding.saleValue')} value={formatMoney(exit.gross)} />
      <Line
        label={t('portfolio.holding.sellCharges')}
        value={`− ${formatMoney(exit.charges.total)}`}
      />
      {noTax ? (
        <p className="py-2 text-xs text-muted">{t('portfolio.holding.cgtNone')}</p>
      ) : (
        <Line label={t('portfolio.holding.cgt')} value={`− ${formatMoney(exit.cgt)}`} />
      )}
      {filerStatus === 'non_filer' && (
        <p className="text-xs text-muted">{t('portfolio.holding.cgtNonFiler')}</p>
      )}
      <div className="border-t border-line pt-2">
        <Line
          label={t('portfolio.holding.netResult')}
          value={
            <Delta value={exit.net_return}>
              {formatMoney(exit.net_return)} ({formatPctString(exit.net_return_pct, true)})
            </Delta>
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
    return <p className="text-sm text-muted">{t('portfolio.holding.dividendsNone')}</p>;
  }
  return (
    <section className="space-y-2 text-sm">
      <div className="flex items-center justify-between gap-2">
        <h4 className="font-medium text-ink">{t('portfolio.holding.dividendsTitle')}</h4>
        <EstimateBadge />
      </div>
      <p className="text-xs text-muted">
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
      <p className="text-xs text-muted">{t('portfolio.holding.dividendsSource')}</p>
      <p className="text-xs text-muted">{t('portfolio.holding.dividendsNote')}</p>
    </section>
  );
};

const WhyThisStock = ({ holding }: { holding: PortfolioHolding }) => {
  const { t } = useTranslation();
  const why = holding.why;
  return (
    <details className="rounded-control border border-line p-4 text-sm">
      <summary className="flex cursor-pointer list-none items-center gap-2 font-medium text-ink">
        <Info className="h-4 w-4 text-muted" aria-hidden="true" />
        {t('portfolio.holding.whyTitle')}
      </summary>
      <ul className="mt-4 space-y-2 leading-relaxed text-ink">
        <li>{t('portfolio.holding.whyRisk', { vol: formatPctString(why.volatility_pct) })}</li>
        <li>
          {t('portfolio.holding.whyForecast', {
            price: formatMoney(why.forecast_price),
            change: formatPctString(why.expected_change_pct, true),
          })}
          {why.low_confidence_reasons.length > 0 && (
            <span className="mt-2 block text-warning">
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
      <p className="mt-4 text-xs text-muted">{t('portfolio.holding.whyNote')}</p>
    </details>
  );
};

/**
 * One holding as a compact row (Design.md §7.3): company, share of the money, total cost,
 * break-even price and the forecast-exit result, expanding to the full cost breakdown, the
 * forecast exit, dividends and "why this stock". Every figure is the engine's own.
 */
export const HoldingRow = ({
  holding,
  rates,
  filerStatus,
  onExclude,
  excluding,
  color,
}: {
  holding: PortfolioHolding;
  rates: PortfolioRates;
  filerStatus: FilerStatus;
  onExclude: (ticker: string) => void;
  excluding: boolean;
  /** The holding's donut colour, so the row and the chart match */
  color: string;
}) => {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const panelId = `holding-${holding.ticker}`;
  const exit = holding.forecast_exit;
  return (
    <li className={open ? 'bg-sunken/40' : ''}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(!open)}
        className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 px-4 py-4 text-start transition-colors hover:bg-sunken sm:px-6 lg:grid-cols-[minmax(0,2fr)_repeat(4,minmax(0,1fr))_auto]"
      >
        <span className="flex min-w-0 items-center gap-4">
          <span className="h-8 w-1 shrink-0 rounded-full" style={{ backgroundColor: color }} />
          <span className="min-w-0">
            <span dir="ltr" className="block font-semibold text-ink">
              {holding.ticker}
            </span>
            <CompanyName name={holding.name} className="text-xs text-muted" />
          </span>
        </span>
        <span className="text-end lg:text-start">
          <Figure className="font-semibold text-ink">{allocationLabel(holding)}</Figure>
          <span className="block text-xs text-muted lg:hidden">
            {t('portfolio.columns.allocation')}
          </span>
        </span>
        <Cell label={t('portfolio.holding.totalCost')} value={formatMoney(holding.total_cost)} />
        <Cell
          label={t('portfolio.holding.breakEven')}
          value={formatMoney(holding.break_even_price)}
        />
        <span className="col-span-2 flex items-baseline justify-between gap-2 lg:col-span-1 lg:block lg:text-end">
          <span className="text-xs text-muted lg:hidden">{t('portfolio.columns.exit')}</span>
          <Delta value={exit.net_return} className="text-sm">
            {formatPctString(exit.net_return_pct, true)}
          </Delta>
        </span>
        <ChevronDown
          className={`hidden h-5 w-5 text-muted transition-transform duration-150 lg:block ${
            open ? 'rotate-180' : ''
          }`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div id={panelId} className="space-y-6 px-4 pb-6 sm:px-6">
          {holding.sector && <CompanyName name={holding.sector} className="text-xs text-muted" />}
          <p className="text-xs text-muted">
            {t('portfolio.holding.breakEvenChange', {
              pct: formatPctString(holding.break_even_change_pct),
              price: formatMoney(holding.price),
            })}{' '}
            {t('portfolio.holding.breakEvenHelp')}
          </p>
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-6">
              <BuyBlock holding={holding} rates={rates} />
              <DividendBlock holding={holding} language={i18n.language} />
            </div>
            <div className="space-y-6">
              <ExitBlock holding={holding} filerStatus={filerStatus} />
              <WhyThisStock holding={holding} />
            </div>
          </div>
          <div className="border-t border-line pt-4">
            {confirming ? (
              <div className="space-y-4">
                <p className="text-sm text-ink">
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
                  <Button
                    variant="secondary"
                    onClick={() => setConfirming(false)}
                    disabled={excluding}
                  >
                    {t('portfolio.form.cancel')}
                  </Button>
                </div>
              </div>
            ) : (
              <Button variant="secondary" onClick={() => setConfirming(true)}>
                <MinusCircle className="h-4 w-4" aria-hidden="true" />
                {t('portfolio.holding.exclude')}
              </Button>
            )}
          </div>
        </div>
      )}
    </li>
  );
};

/** A figure in the row; on narrow screens its label sits next to it. */
const Cell = ({ label, value }: { label: string; value: string }) => (
  <span className="col-span-2 flex items-baseline justify-between gap-2 lg:col-span-1 lg:block lg:text-end">
    <span className="text-xs text-muted lg:hidden">{label}</span>
    <Figure className="text-sm text-ink">{value}</Figure>
  </span>
);
