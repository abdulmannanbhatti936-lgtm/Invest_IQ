// Theme choice as pure rules, importable by Node's test runner and by vite.config.ts.
// Kept separate from the design-tokens package import so this file has no dependencies.
export type ThemeChoice = 'dark' | 'light';

export const THEME_STORAGE_KEY = 'investiq.theme';

/** Dark unless the user chose light (team decision 2026-10-15: dark-first). */
export const parseTheme = (stored: string | null | undefined): ThemeChoice =>
  stored === 'light' ? 'light' : 'dark';

export const otherTheme = (theme: ThemeChoice): ThemeChoice =>
  theme === 'dark' ? 'light' : 'dark';
