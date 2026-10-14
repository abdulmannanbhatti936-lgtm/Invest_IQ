// Run with: npm test (Node's built-in test runner)
// The Urdu fonts must never take punctuation that English text uses: Noto Naskh drew U+2011
// (non-breaking hyphen) low, so "low‑confidence" in an English chat reply read as
// "low_confidence" (UI audit 2026-10-15).
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const css = readFileSync(new URL('../index.css', import.meta.url), 'utf-8');

const fontFaces = [...css.matchAll(/@font-face\s*{([^}]*)}/g)].map((m) => m[1]);

const rangesOf = (block: string): [number, number][] => {
  const match = block.match(/unicode-range:([^;]*);/);
  if (!match) return [[0, 0x10ffff]];
  return match[1].split(',').map((part) => {
    const [lo, hi] = part.trim().replace(/^U\+/i, '').split('-');
    return [parseInt(lo, 16), parseInt(hi ?? lo, 16)];
  });
};

const covers = (block: string, codePoint: number) =>
  rangesOf(block).some(([lo, hi]) => codePoint >= lo && codePoint <= hi);

test('index.css declares the Urdu font faces with unicode ranges', () => {
  assert.ok(fontFaces.length >= 3);
  for (const face of fontFaces) assert.match(face, /unicode-range/);
});

test('no Urdu font face covers hyphens, dashes or Latin letters and digits', () => {
  const english = [0x2d, 0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x41, 0x61, 0x30, 0x25];
  for (const face of fontFaces) {
    for (const codePoint of english) {
      assert.ok(!covers(face, codePoint), `U+${codePoint.toString(16)} in ${face.slice(0, 60)}`);
    }
  }
});

test('Urdu letters are still covered', () => {
  for (const face of fontFaces) assert.ok(covers(face, 0x06a9), 'ک');
});
