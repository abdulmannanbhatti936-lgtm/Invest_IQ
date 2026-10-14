// Indus Night (Design.md §2, chosen 2026-10-15): dark is the default theme, light the full
// alternative. Every text/UI pair the components draw is checked for WCAG AA in colors.test.ts.
// The secondary (coral) and gradient stops are for the landing page and brand marks only; they
// never colour text or figures. Gains and losses are a colour-blind-tuned green and vermilion
// that differ in lightness as well as hue, always shown with ▲ / ▼ / — (Design.md §6.3).

export type ThemeName = 'dark' | 'light';

export const THEMES: readonly ThemeName[] = ['dark', 'light'];

export const DEFAULT_THEME: ThemeName = 'dark';

export interface ThemeColors {
  primary: string;
  primaryHover: string;
  primaryTint: string;
  secondary: string;
  success: string;
  successTint: string;
  danger: string;
  dangerTint: string;
  warning: string;
  warningTint: string;
  neutral: string;
  background: string;
  surface: string;
  surfaceSunken: string;
  border: string;
  borderStrong: string;
  textPrimary: string;
  textSecondary: string;
  textInverse: string;
  focusRing: string;
  chartPortfolio: string;
  chartRules: string;
  chartBenchmark: string;
  chartForecast: string;
  gradient1: string;
  gradient2: string;
  gradient3: string;
}

export const themes: Record<ThemeName, ThemeColors> = {
  dark: {
    primary: '#33C9DB',
    primaryHover: '#5FD6E4',
    primaryTint: '#0F3640',
    secondary: '#FF8466',
    success: '#86E6BA',
    successTint: '#113524',
    danger: '#EE6236',
    dangerTint: '#3D1A1C',
    warning: '#F5BC4A',
    warningTint: '#34290F',
    neutral: '#9DB6BC',
    background: '#07131A',
    surface: '#0E1F27',
    surfaceSunken: '#0A1920',
    border: '#1F3A44',
    borderStrong: '#5E7D86',
    textPrimary: '#E8F3F4',
    textSecondary: '#9DB6BC',
    textInverse: '#04161B',
    focusRing: '#33C9DB',
    chartPortfolio: '#33C9DB',
    chartRules: '#F5BC4A',
    chartBenchmark: '#8AA3AA',
    chartForecast: '#C4A5FF',
    gradient1: '#33C9DB',
    gradient2: '#7BE0C3',
    gradient3: '#FF8466',
  },
  light: {
    primary: '#0A6E80',
    primaryHover: '#08596A',
    primaryTint: '#E0F3F6',
    secondary: '#E8603F',
    success: '#0B5E3F',
    successTint: '#E2F4E8',
    danger: '#BF360C',
    dangerTint: '#FEF4F0',
    warning: '#875700',
    warningTint: '#FFF3D9',
    neutral: '#4B6168',
    background: '#F3F7F8',
    surface: '#FFFFFF',
    surfaceSunken: '#EAF1F2',
    border: '#D4E1E3',
    borderStrong: '#778C92',
    textPrimary: '#0B1D23',
    textSecondary: '#4B6168',
    textInverse: '#FFFFFF',
    focusRing: '#0A6E80',
    chartPortfolio: '#0A6E80',
    chartRules: '#B45309',
    chartBenchmark: '#6B7F85',
    chartForecast: '#6D4AB8',
    gradient1: '#0A8EA3',
    gradient2: '#2CC5D8',
    gradient3: '#FF8466',
  },
};

/** The default theme's colours, for apps without theme switching yet (mobile, Phase 10). */
export const colors = themes[DEFAULT_THEME];
