import { execFileSync } from 'node:child_process';
import { API_DIR, API_PYTHON } from '../playwright.config.ts';

/** Deletes every E2E account (email `e2e_…@example.com`) from the *_test database. */
export const cleanupE2eUsers = (): string =>
  execFileSync(API_PYTHON, ['-m', 'tests.testdb', 'cleanup-e2e'], {
    cwd: API_DIR,
    encoding: 'utf-8',
  }).trim();

/** Removes the MOCK market the API seeded for the backtest test (tests/e2e_market.py). */
export const clearE2eMarket = (): string =>
  execFileSync(API_PYTHON, ['-m', 'tests.testdb', 'clear-e2e-market'], {
    cwd: API_DIR,
    encoding: 'utf-8',
  }).trim();
