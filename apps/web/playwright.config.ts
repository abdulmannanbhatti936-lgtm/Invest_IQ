// End-to-end smoke tests (Architecture.md §19). Run from the repo root or apps/web:
//   npm run e2e
// Starts its own API (on the *_test database) and web dev server on separate ports, so it can
// never reuse a dev server that points at the dev/demo database. Needs Postgres + Redis running
// (infra/docker-compose.yml) and the backend venv in services/api/venv (see README).
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

const WEB_DIR = dirname(fileURLToPath(import.meta.url));
export const API_DIR = join(WEB_DIR, '..', '..', 'services', 'api');
export const API_PYTHON = join(
  API_DIR,
  'venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
);
if (!existsSync(API_PYTHON)) {
  throw new Error(`Backend venv not found at ${API_PYTHON}. Set it up first (README → Backend).`);
}

const API_PORT = 8001;
const WEB_PORT = 5174;
const WEB_URL = `http://localhost:${WEB_PORT}`;

export default defineConfig({
  testDir: './e2e',
  // One worker: the tests share one test database and one API process
  workers: 1,
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  // Failure artefacts (git-ignored)
  outputDir: './e2e-results',
  reporter: [['list'], ['html', { outputFolder: './e2e-report', open: 'never' }]],
  use: {
    baseURL: WEB_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      // API on the test database (`tests.testdb serve` refuses anything not named *_test)
      command: `"${API_PYTHON}" -m tests.testdb serve --port ${API_PORT} --cors-origin ${WEB_URL} --cors-origin http://127.0.0.1:${WEB_PORT}`,
      cwd: API_DIR,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'ignore',
      stderr: 'pipe',
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort`,
      cwd: WEB_DIR,
      url: WEB_URL,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { VITE_API_URL: `http://127.0.0.1:${API_PORT}` },
    },
  ],
});
