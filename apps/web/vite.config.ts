import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { themes } from '../../packages/design-tokens/src/colors.ts';
import { cssVariables, themeCss } from '../../packages/design-tokens/src/css.ts';
import { motion } from '../../packages/design-tokens/src/motion.ts';
import { elevation } from '../../packages/design-tokens/src/shadows.ts';
import { THEME_STORAGE_KEY } from './src/lib/themeRules.ts';

/**
 * Puts the design tokens' theme variables and the saved theme choice into <head>, so the first
 * paint already has the right colours (no flash of the other theme before the app loads).
 */
const themeHead = (): Plugin => ({
  name: 'investiq-theme-head',
  transformIndexHtml: () => [
    {
      tag: 'style',
      attrs: { id: 'iq-theme' },
      children: themeCss(
        cssVariables(themes.dark, elevation.dark, motion),
        cssVariables(themes.light, elevation.light, motion),
      ),
      injectTo: 'head-prepend',
    },
    {
      tag: 'script',
      children: `try{var t=localStorage.getItem('${THEME_STORAGE_KEY}');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}`,
      injectTo: 'head-prepend',
    },
  ],
});

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), themeHead()],
  resolve: {
    // Deduplicate React (monorepo hoisting fix for Vite 8 / rolldown)
    dedupe: ['react', 'react-dom', 'react/jsx-runtime', 'react/jsx-dev-runtime'],
    // Point workspace packages to their TypeScript source directly
    // so we avoid the stale CommonJS dist builds
    alias: {
      '@investiq/api-client': path.resolve(__dirname, '../../packages/api-client/src/index.ts'),
      '@investiq/design-tokens': path.resolve(
        __dirname,
        '../../packages/design-tokens/src/index.ts',
      ),
      '@investiq/shared-types': path.resolve(__dirname, '../../packages/shared-types/src/index.ts'),
      '@investiq/i18n': path.resolve(__dirname, '../../packages/i18n/src/index.ts'),
    },
  },
});
