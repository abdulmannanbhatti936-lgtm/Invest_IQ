// Run with: npm test (Node's built-in test runner)
// Design.md §4: every margin, padding and gap is a multiple of 8 px. Tailwind's spacing unit is
// 4 px, so only even steps (0, 2, 4, 6, ...) and "px" hairlines are allowed in the app's code.
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const SRC = fileURLToPath(new URL('..', import.meta.url));

const files = (dir: string): string[] =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path);
    return path.endsWith('.tsx') ? [path] : [];
  });

const SPACING =
  /(?:^|[\s"'`:])-?(?:p|px|py|pt|pb|ps|pe|m|mx|my|mt|mb|ms|me|gap|gap-x|gap-y|space-x|space-y)-(\d+(?:\.\d+)?)(?![\w.\-/[])/g;

test('every spacing utility in apps/web/src is on the 8 px scale', () => {
  const offScale: string[] = [];
  for (const file of files(SRC)) {
    for (const match of readFileSync(file, 'utf-8').matchAll(SPACING)) {
      const step = Number(match[1]);
      if (step % 2 !== 0) offScale.push(`${file.slice(SRC.length)}: ${match[0].trim()}`);
    }
  }
  assert.deepEqual(offScale, []);
});
