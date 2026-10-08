import { cleanupE2eUsers } from './testDb.ts';

// Every account the tests created is deleted; the printed user count proves the DB is clean
export default function globalTeardown() {
  console.log(`[e2e teardown] ${cleanupE2eUsers()}`);
}
