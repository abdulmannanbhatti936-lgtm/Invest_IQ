import { Globe } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import { setLanguage } from '../lib/language';

export const toggleClasses =
  'inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-sm font-medium text-muted transition-colors duration-150 hover:bg-sunken hover:text-ink';

export const LanguageToggle = ({ className = '' }: { className?: string }) => {
  const { t, i18n } = useTranslation();
  const next = i18n.language === 'ur' ? 'en' : 'ur';
  return (
    <button
      type="button"
      onClick={() => setLanguage(next)}
      aria-label={t('common.switchLanguageLabel')}
      className={`${toggleClasses} ${className}`}
    >
      <Globe className="h-4 w-4" aria-hidden="true" />
      {/* On English pages this four-letter label is the only Urdu on screen: drawn in the system
          font so it does not download the 156 KB Nastaleeq font (Design.md §3 deviation) */}
      <span lang={next} className={next === 'ur' ? 'iq-system-font' : ''}>
        {t('common.switchLanguage')}
      </span>
    </button>
  );
};
