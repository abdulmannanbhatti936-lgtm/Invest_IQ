import { cleanupE2eUsers, clearE2eMarket } from './testDb.ts';

// Every account the tests created is deleted (with its portfolios and backtests), then the
// MOCK market; the printed counts prove the DB is clean
export default function globalTeardown() {
  console.log(`[e2e teardown] ${cleanupE2eUsers()}`);
  console.log(`[e2e teardown] ${clearE2eMarket()}`);
}
