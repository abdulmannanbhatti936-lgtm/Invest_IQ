import { Moon, Sun } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import { setTheme, useTheme } from '../lib/theme';
import { otherTheme } from '../lib/themeRules';
import { toggleClasses } from './LanguageToggle';

/** Dark by default; the choice is remembered on this device (team decision 2026-10-15). */
export const ThemeToggle = ({ className = '' }: { className?: string }) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const next = otherTheme(theme);
  const Icon = next === 'light' ? Sun : Moon;
  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={t(`common.theme.switchTo.${next}`)}
      title={t(`common.theme.switchTo.${next}`)}
      className={`${toggleClasses} ${className}`}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      <span className="hidden sm:inline">{t(`common.theme.name.${next}`)}</span>
    </button>
  );
};
