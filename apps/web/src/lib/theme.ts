import { useSyncExternalStore } from 'react';
import { themes, type ThemeColors } from '@investiq/design-tokens';
import { parseTheme, THEME_STORAGE_KEY, type ThemeChoice } from './themeRules';

// The saved choice is applied before the app loads by an inline script (vite.config.ts); this
// module keeps <html data-theme> and the stored value in step afterwards (Rules.md §4.3).
const listeners = new Set<() => void>();

const read = (): ThemeChoice => parseTheme(document.documentElement.dataset.theme);

export const setTheme = (theme: ThemeChoice) => {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Storage blocked: the choice lasts until the page is reloaded
  }
  listeners.forEach((notify) => notify());
};

const subscribe = (notify: () => void) => {
  listeners.add(notify);
  return () => listeners.delete(notify);
};

export const useTheme = (): ThemeChoice => useSyncExternalStore(subscribe, read, () => 'dark');

/** The active theme's colours, for drawing APIs that need concrete values (charts, WebGL). */
export const useThemeColors = (): ThemeColors => themes[useTheme()];
