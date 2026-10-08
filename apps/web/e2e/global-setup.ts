import { cleanupE2eUsers } from './testDb.ts';

// Start from a clean slate even if an earlier run crashed before its teardown
export default function globalSetup() {
  console.log(`[e2e setup] ${cleanupE2eUsers()}`);
}
