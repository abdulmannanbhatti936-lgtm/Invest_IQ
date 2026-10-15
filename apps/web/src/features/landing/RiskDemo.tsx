import { useId, useState } from 'react';
import { useTranslation } from '@investiq/i18n';
import type { RiskCategory } from '@investiq/shared-types';
import { Donut, donutColors, LegendSwatch } from '../../components/ui/Donut';
import { Figure } from '../../components/ui/Feedback';
import { formatDate, formatPctString } from '../../lib/format';
import { useThemeColors } from '../../lib/theme';
import { RiskBadge } from '../onboarding/RiskBadge';
import type { RiskExample } from './landingData';

const PROFILES: RiskCategory[] = ['conservative', 'moderate', 'aggressive'];

/**
 * Risk demo: a three-stop slider that morphs the donut between the allocation engine's real,
 * dated output for each profile. Labelled as an example; it never shows a return.
 */
export const RiskDemo = ({ example }: { example: RiskExample }) => {
  const { t, i18n } = useTranslation();
  const theme = useThemeColors();
  const id = useId();
  const [step, setStep] = useState(1);
  const [hovered, setHovered] = useState<string | null>(null);
  const profile = PROFILES[step];
  const { holdings, cash_pct } = example.profiles[profile];
  const colors = donutColors(holdings.length, theme);

  return (
    <div className="grid items-center gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <div className="space-y-6">
        <div className="space-y-2">
          <label htmlFor={id} className="text-sm font-medium text-ink">
            {t('landing.risk.sliderLabel')}
          </label>
          <input
            id={id}
            type="range"
            min={0}
            max={2}
            step={1}
            value={step}
            onChange={(e) => setStep(Number(e.target.value))}
            aria-valuetext={t(`risk.${profile}`)}
            className="w-full accent-[var(--iq-primary)]"
          />
          <div className="flex justify-between text-sm">
            {PROFILES.map((p, i) => (
              <button
                key={p}
                type="button"
                onClick={() => setStep(i)}
                aria-pressed={i === step}
                className={`min-h-8 rounded-control px-2 ${
                  i === step ? 'font-semibold text-primary' : 'text-muted hover:text-ink'
                }`}
              >
                {t(`risk.${p}`)}
              </button>
            ))}
          </div>
        </div>
        <div className="space-y-2">
          <RiskBadge category={profile} />
          <p className="text-sm text-muted">{t(`landing.risk.rules.${profile}`)}</p>
        </div>
        <p className="inline-flex rounded-full border border-warning bg-warning-tint px-4 text-xs font-semibold text-warning">
          {t('landing.risk.exampleLabel', {
            date: formatDate(example.prices_as_of, i18n.language),
          })}
        </p>
      </div>

      <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
        <Donut
          size={208}
          label={t('landing.risk.donutLabel', {
            profile: t(`risk.${profile}`),
            count: holdings.length,
          })}
          segments={holdings.map((h, i) => ({ key: String(i), value: Number(h.allocation_pct) }))}
          activeKey={hovered}
          center={
            <>
              <span className="text-3xl font-bold text-ink tabular-nums">{holdings.length}</span>
              <span className="text-xs text-muted">{t('landing.risk.companies')}</span>
            </>
          }
        />
        <ul className="w-full max-w-xs space-y-2 text-sm">
          {holdings.map((h, i) => (
            <li
              key={`${profile}-${i}`}
              className="flex items-center justify-between gap-4 rounded-control px-2"
              onMouseEnter={() => setHovered(String(i))}
              onMouseLeave={() => setHovered(null)}
            >
              <span className="flex min-w-0 items-center gap-2">
                <LegendSwatch color={colors[i]} />
                <span dir="ltr" className="truncate text-ink">
                  {h.ticker && <strong className="font-semibold">{h.ticker} </strong>}
                  <span className={h.ticker ? 'text-muted' : ''}>
                    {h.ticker ? '· ' : ''}
                    {h.sector}
                  </span>
                </span>
              </span>
              <Figure className="text-ink">
                {formatPctString(Number(h.allocation_pct).toFixed(2))}
              </Figure>
            </li>
          ))}
          <li className="flex items-center justify-between gap-4 border-t border-line px-2 pt-2 text-muted">
            <span>{t('landing.risk.cash')}</span>
            <Figure>{formatPctString(Number(cash_pct).toFixed(2))}</Figure>
          </li>
        </ul>
      </div>
    </div>
  );
};
