import { Globe } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import { setLanguage } from '../lib/language';

export const LanguageToggle = ({ className = '' }: { className?: string }) => {
  const { t, i18n } = useTranslation();
  const next = i18n.language === 'ur' ? 'en' : 'ur';
  return (
    <button
      type="button"
      onClick={() => setLanguage(next)}
      aria-label={t('common.switchLanguageLabel')}
      className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900 ${className}`}
    >
      <Globe className="h-4 w-4" />
      {t('common.switchLanguage')}
    </button>
  );
};
