import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Briefcase,
  History,
  LineChart,
  ListChecks,
  MessageSquare,
  ShieldCheck,
} from 'lucide-react';
import '@fontsource-variable/bricolage-grotesque/wght.css';
import { useTranslation } from '@investiq/i18n';
import { buttonClasses } from '../../components/ui/Button';
import { LanguageToggle } from '../../components/LanguageToggle';
import { ThemeToggle } from '../../components/ThemeToggle';
import { Wordmark } from '../../components/Wordmark';
import { formatDate } from '../../lib/format';
import { Bloom } from './Bloom';
import { CostFlow } from './CostFlow';
import { loadBloomData, loadRiskExample, type BloomData, type RiskExample } from './landingData';
import { sectorCount } from './landingRules';
import { RiskDemo } from './RiskDemo';
import { ZoomSection } from './ZoomSection';

// The date of the test account behind the zoom section's screenshots (docs/screenshots/ui-design)
const SCREENSHOT_DATE = '2026-10-15';

const STEPS = [
  { key: 'profile', icon: ListChecks },
  { key: 'forecast', icon: LineChart },
  { key: 'portfolio', icon: Briefcase },
  { key: 'test', icon: History },
] as const;

const Section = ({
  id,
  title,
  lede,
  children,
}: {
  id: string;
  title: string;
  lede?: string;
  children: React.ReactNode;
}) => (
  <section aria-labelledby={id} className="mx-auto max-w-[1200px] px-4 py-16 sm:px-8 sm:py-24">
    <div className="mb-8 max-w-2xl space-y-4">
      <h2 id={id} className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
        {title}
      </h2>
      {lede && <p className="text-base text-muted sm:text-lg">{lede}</p>}
    </div>
    {children}
  </section>
);

/** The public landing page at "/" for visitors who are not logged in (UI round, 2026-10-15). */
export const LandingPage = () => {
  const { t, i18n } = useTranslation();
  const [bloom, setBloom] = useState<BloomData | null>(null);
  const [example, setExample] = useState<RiskExample | null>(null);

  useEffect(() => {
    loadBloomData().then(setBloom);
    loadRiskExample().then(setExample);
  }, []);

  const date = (iso: string) => formatDate(iso, i18n.language);
  const withTickers = Boolean(bloom?.companies[0]?.ticker);

  return (
    <div className="min-h-screen bg-bg text-ink">
      <section className="relative isolate min-h-svh overflow-hidden" aria-labelledby="hero-title">
        <div className="absolute inset-0 -z-10">
          {bloom && <Bloom companies={bloom.companies} />}
        </div>
        {/* Keeps the copy readable over the bloom (AA contrast): fades from the text side */}
        <div
          className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-bg from-50% via-bg/80 via-65% to-transparent to-90% sm:bg-gradient-to-r sm:from-bg sm:from-30% sm:via-bg/85 sm:via-45% sm:to-transparent sm:to-70% rtl:sm:bg-gradient-to-l"
          aria-hidden="true"
        />
        <header className="mx-auto flex max-w-[1200px] items-center justify-between px-4 py-4 sm:px-8 sm:py-6">
          <Wordmark className="font-display text-2xl" />
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </header>

        <div className="pointer-events-none mx-auto max-w-[1200px] px-4 pt-8 pb-24 sm:px-8 sm:pt-16">
          <div className="pointer-events-auto max-w-xl space-y-6">
            <p className="inline-flex items-center gap-2 rounded-full border border-line bg-surface/60 px-4 text-sm text-muted backdrop-blur">
              <span className="h-2 w-2 rounded-full bg-gradient-2" aria-hidden="true" />
              {t('landing.hero.eyebrow')}
            </p>
            <h1
              id="hero-title"
              className="font-display text-5xl leading-[1.02] font-bold tracking-tight text-ink sm:text-7xl"
            >
              {t('landing.hero.title')}
            </h1>
            <p className="text-lg text-muted">{t('landing.hero.lede')}</p>
            <div className="flex flex-wrap gap-4">
              <Link to="/register" className={buttonClasses('primary', 'lg')}>
                {t('landing.hero.start')}
              </Link>
              <Link to="/login" className={buttonClasses('secondary', 'lg')}>
                {t('landing.hero.login')}
              </Link>
            </div>
            {bloom && (
              <p className="max-w-md text-xs text-muted">
                {t(withTickers ? 'landing.hero.source' : 'landing.hero.sourceSectors', {
                  count: bloom.companies.length,
                  sectors: sectorCount(bloom.companies),
                  date: date(bloom.snapshot),
                })}
              </p>
            )}
          </div>
        </div>
      </section>

      <ZoomSection builtOn={date(SCREENSHOT_DATE)} />

      {example && (
        <Section id="risk-title" title={t('landing.risk.title')} lede={t('landing.risk.lede')}>
          <RiskDemo example={example} />
        </Section>
      )}

      <div className="bg-sunken">
        <Section id="costs-title" title={t('landing.costs.title')} lede={t('landing.costs.lede')}>
          <CostFlow />
        </Section>
      </div>

      <Section id="how-title" title={t('landing.how.title')}>
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(({ key, icon: Icon }, i) => (
            <li
              key={key}
              className="group rounded-card border border-line bg-surface p-6 shadow-e1 transition-[transform,box-shadow] duration-150 hover:-translate-y-0.5 hover:shadow-e2"
            >
              <div className="mb-4 flex items-center gap-4">
                <span className="relative flex h-12 w-12 items-center justify-center rounded-full bg-primary-tint text-primary">
                  <Icon className="h-6 w-6" aria-hidden="true" />
                  <span
                    className="iq-orbit absolute inset-0 rounded-full border border-dashed border-primary"
                    aria-hidden="true"
                  />
                </span>
                <span className="font-display text-sm font-semibold text-muted tabular-nums">
                  {String(i + 1).padStart(2, '0')}
                </span>
              </div>
              <h3 className="mb-2 text-lg font-semibold text-ink">
                {t(`landing.how.steps.${key}.title`)}
              </h3>
              <p className="text-sm text-muted">{t(`landing.how.steps.${key}.body`)}</p>
            </li>
          ))}
        </ol>
      </Section>

      <section
        aria-labelledby="honesty-title"
        className="border-y border-line bg-surface px-4 py-16 sm:px-8"
      >
        <div className="mx-auto max-w-[1200px] space-y-8">
          <h2
            id="honesty-title"
            className="flex items-center gap-4 font-display text-2xl font-bold text-ink"
          >
            <ShieldCheck className="h-6 w-6 text-primary" aria-hidden="true" />
            {t('landing.honesty.title')}
          </h2>
          <ul className="grid gap-6 md:grid-cols-3">
            {(['forecasts', 'advisory', 'trades'] as const).map((key) => (
              <li key={key} className="space-y-2">
                <h3 className="font-semibold text-ink">{t(`landing.honesty.${key}.title`)}</h3>
                <p className="text-sm text-muted">{t(`landing.honesty.${key}.body`)}</p>
              </li>
            ))}
          </ul>
          {bloom && example && (
            <p className="text-sm text-muted">
              {t('landing.honesty.facts', {
                companies: bloom.companies.length,
                snapshot: date(bloom.snapshot),
                forecast: example.forecast_companies,
                since: example.history_start ? date(example.history_start) : '—',
              })}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-4">
            <Link to="/register" className={buttonClasses('primary', 'lg')}>
              {t('landing.hero.start')}
            </Link>
            <span className="inline-flex items-center gap-2 text-sm text-muted">
              <MessageSquare className="h-4 w-4" aria-hidden="true" />
              {t('landing.honesty.languages')}
            </span>
          </div>
        </div>
      </section>

      <footer className="mx-auto max-w-[1200px] space-y-4 px-4 py-8 text-sm text-muted sm:px-8">
        <p>{t('disclaimer')}</p>
        <p className="flex flex-wrap items-center gap-2">
          <Wordmark />
          <span>{t('landing.footer')}</span>
        </p>
      </footer>
    </div>
  );
};
