import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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
