import type { ReactNode } from 'react';
import { useTranslation } from '@investiq/i18n';
import { LanguageToggle } from '../../components/LanguageToggle';
import { DisclaimerBanner } from '../../components/ui/Feedback';

/** Centered card layout shared by the login, register and onboarding screens. */
export const AuthShell = ({
  title,
  subtitle,
  children,
  showDisclaimer = false,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** PRD.md §8.5 disclaimer, shown from registration onwards (team decision 2026-10-09) */
  showDisclaimer?: boolean;
}) => {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      <header className="flex items-center justify-between px-6 py-4">
        <span className="text-xl font-bold tracking-tight text-blue-700">
          {t('common.appName')}
        </span>
        <LanguageToggle />
      </header>
      <main className="flex flex-1 flex-col items-center justify-center gap-6 px-4 pb-12">
        <div className="w-full max-w-md space-y-8 rounded-xl border border-gray-100 bg-white p-8 shadow-sm">
          <div className="text-center">
            <h1 className="text-3xl font-bold tracking-tight text-gray-900">{title}</h1>
            {subtitle && <p className="mt-2 text-sm text-gray-600">{subtitle}</p>}
          </div>
          {children}
        </div>
        {showDisclaimer && (
          <div className="w-full max-w-md">
            <DisclaimerBanner />
          </div>
        )}
      </main>
    </div>
  );
};
