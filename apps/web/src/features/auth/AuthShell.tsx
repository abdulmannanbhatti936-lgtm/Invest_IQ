import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from '@investiq/i18n';
import { LanguageToggle } from '../../components/LanguageToggle';
import { ThemeToggle } from '../../components/ThemeToggle';
import { Wordmark } from '../../components/Wordmark';
import { DisclaimerBanner } from '../../components/ui/Feedback';
import { useTheme } from '../../lib/theme';

/**
 * Login, register and onboarding: the form on one side and, on wide screens, the product's
 * promise beside it over a still of the landing page's bloom.
 */
export const AuthShell = ({
  title,
  subtitle,
  children,
  showDisclaimer = false,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** PRD.md §8.5 disclaimer, shown from registration onwards (team decision 2026-10-09) */
  showDisclaimer?: boolean;
  /** Onboarding's question cards need more room than a login form */
  wide?: boolean;
}) => {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  return (
    <div className="flex min-h-screen bg-bg">
      <aside className="relative hidden w-[42%] max-w-xl overflow-hidden border-e border-line bg-surface lg:block">
        <img
          src={`/landing/bloom-${theme}.webp`}
          alt=""
          className={`absolute inset-0 h-full w-full object-cover opacity-70 ${
            i18n.dir() === 'rtl' ? '-scale-x-100' : ''
          }`}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-surface via-surface/70 to-transparent" />
        <div className="relative flex h-full flex-col justify-between p-12">
          <Link to="/" className="text-2xl">
            <Wordmark className="font-display" />
          </Link>
          <div className="space-y-4">
            <p className="font-display text-4xl leading-tight font-bold tracking-tight text-ink">
              {t('landing.hero.title')}
            </p>
            <p className="text-base text-muted">{t('landing.hero.lede')}</p>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between px-4 py-4 sm:px-8">
          <Link to="/" className="text-xl lg:invisible">
            <Wordmark />
          </Link>
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </header>
        <main className="flex flex-1 flex-col items-center justify-center gap-6 px-4 pb-12">
          <div className={`w-full space-y-8 ${wide ? 'max-w-2xl' : 'max-w-md'}`}>
            <div className="space-y-2">
              <h1 className="text-2xl font-bold tracking-tight text-ink sm:text-3xl">{title}</h1>
              {subtitle && <p className="text-sm text-muted">{subtitle}</p>}
            </div>
            {children}
          </div>
          {showDisclaimer && (
            <div className={`w-full ${wide ? 'max-w-2xl' : 'max-w-md'}`}>
              <DisclaimerBanner />
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
