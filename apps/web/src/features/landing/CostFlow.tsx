import { useEffect, useRef, useState } from 'react';
import { useTranslation } from '@investiq/i18n';
import { Figure } from '../../components/ui/Feedback';
import { formatDate, formatMoney, ltr } from '../../lib/format';
import { COST_EXAMPLE } from './costExample';

/**
 * "What it really costs": Rs 100,000 runs down through each charge to what is bought and what is
 * left. The rows reveal in sequence once the section scrolls into view (landing page only).
 */
export const CostFlow = () => {
  const { t, i18n } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          observer.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const chargesPct = (Number(COST_EXAMPLE.chargesTotal) / Number(COST_EXAMPLE.capital)) * 100;
  // The charges are drawn ten times larger than their share so they can be seen at all
  const MAGNIFY = 10;
  const reveal = (i: number) => ({
    style: { transitionDelay: shown ? `${i * 70}ms` : '0ms' },
    className: `transition-[opacity,transform] duration-300 ease-enter ${
      shown ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'
    }`,
  });

  return (
    <div ref={ref} className="grid gap-8 lg:grid-cols-2">
      <div className="rounded-card border border-line bg-surface p-6 shadow-e1">
        <div className="flex items-baseline justify-between gap-4 border-b border-line pb-4">
          <span className="text-sm font-medium text-muted">{t('landing.costs.start')}</span>
          <Figure className="text-2xl font-bold text-ink">
            {formatMoney(COST_EXAMPLE.capital)}
          </Figure>
        </div>
        <ul className="divide-y divide-line">
          {COST_EXAMPLE.charges.map((c, i) => (
            <li
              key={c.key}
              style={reveal(i).style}
              className={`flex items-baseline justify-between gap-4 py-2 text-sm ${reveal(i).className}`}
            >
              <span className="text-muted">{t(`portfolio.holding.charges.${c.key}`)}</span>
              <Figure className="text-ink">− {formatMoney(c.amount)}</Figure>
            </li>
          ))}
        </ul>
        <div
          style={reveal(COST_EXAMPLE.charges.length).style}
          className={`space-y-2 border-t border-line pt-4 ${reveal(COST_EXAMPLE.charges.length).className}`}
        >
          <div className="flex items-baseline justify-between gap-4 text-sm font-semibold">
            <span className="text-ink">{t('landing.costs.chargesTotal')}</span>
            <Figure className="text-ink">{formatMoney(COST_EXAMPLE.chargesTotal)}</Figure>
          </div>
          <div className="flex items-baseline justify-between gap-4">
            <span className="text-sm font-semibold text-ink">{t('landing.costs.shares')}</span>
            <Figure className="text-xl font-bold text-primary">
              {formatMoney(COST_EXAMPLE.shares)}
            </Figure>
          </div>
          <div className="flex items-baseline justify-between gap-4 text-sm">
            <span className="text-muted">{t('landing.costs.cash')}</span>
            <Figure className="text-ink">{formatMoney(COST_EXAMPLE.cash)}</Figure>
          </div>
        </div>
      </div>

      <div className="flex flex-col justify-center gap-6">
        <div className="space-y-2">
          <div className="flex h-4 overflow-hidden rounded-full bg-sunken" aria-hidden="true">
            <div
              className="h-full bg-primary transition-[width] duration-700 ease-enter"
              style={{ width: shown ? `${100 - chargesPct * MAGNIFY}%` : '0%' }}
            />
            <div
              className="h-full bg-warning transition-[width] delay-500 duration-500 ease-enter"
              style={{ width: shown ? `${chargesPct * MAGNIFY}%` : '0%' }}
            />
          </div>
          <p className="text-sm text-muted">
            {t('landing.costs.magnified', { pct: ltr(`${chargesPct.toFixed(2)}%`) })}
          </p>
        </div>
        <p className="text-lg text-ink">{t('landing.costs.point')}</p>
        <p className="text-xs text-muted">
          {t('landing.costs.label', {
            date: formatDate(COST_EXAMPLE.pricesDate, i18n.language),
            version: COST_EXAMPLE.ratesVersion,
          })}
        </p>
      </div>
    </div>
  );
};
