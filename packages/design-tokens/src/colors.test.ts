// Run with: npm test -w @investiq/design-tokens (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { THEMES, themes, type ThemeColors } from './colors.ts';

const linear = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const rgb = (hex: string) => [0, 2, 4].map((i) => parseInt(hex.slice(1 + i, 3 + i), 16) / 255);
const luminance = (hex: string) => {
  const [r, g, b] = rgb(hex).map(linear);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
/** WCAG 2.2 contrast ratio */
const contrast = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

type Key = keyof ThemeColors;
// Every pair a component draws: 4.5:1 for text, 3:1 for borders of inputs, focus rings and chart
// lines (WCAG 1.4.11)
const TEXT_PAIRS: [Key, Key][] = [
  ['textPrimary', 'background'],
  ['textPrimary', 'surface'],
  ['textPrimary', 'surfaceSunken'],
  ['textPrimary', 'warningTint'],
  ['textPrimary', 'primaryTint'],
  ['textSecondary', 'background'],
  ['textSecondary', 'surface'],
  ['textSecondary', 'surfaceSunken'],
  ['textInverse', 'primary'],
  ['textInverse', 'primaryHover'],
  ['primary', 'surface'],
  ['primary', 'background'],
  ['primary', 'primaryTint'],
  ['primary', 'surfaceSunken'],
  ['success', 'surface'],
  ['success', 'successTint'],
  ['success', 'surfaceSunken'],
  ['danger', 'surface'],
  ['danger', 'dangerTint'],
  ['danger', 'surfaceSunken'],
  ['warning', 'surface'],
  ['warning', 'warningTint'],
  ['neutral', 'surface'],
];
const UI_PAIRS: [Key, Key][] = [
  ['borderStrong', 'surface'],
  ['borderStrong', 'background'],
  ['focusRing', 'surface'],
  ['focusRing', 'background'],
  ['chartPortfolio', 'surface'],
  ['chartRules', 'surface'],
  ['chartBenchmark', 'surface'],
  ['chartForecast', 'surface'],
];

for (const name of THEMES) {
  const t = themes[name];
  test(`${name}: every text pair meets WCAG AA (4.5:1)`, () => {
    for (const [fg, bg] of TEXT_PAIRS) {
      const ratio = contrast(t[fg], t[bg]);
      assert.ok(ratio >= 4.5, `${fg} on ${bg}: ${ratio.toFixed(2)}`);
    }
  });

  test(`${name}: input borders, focus ring and chart lines meet 3:1`, () => {
    for (const [fg, bg] of UI_PAIRS) {
      const ratio = contrast(t[fg], t[bg]);
      assert.ok(ratio >= 3, `${fg} on ${bg}: ${ratio.toFixed(2)}`);
    }
  });

  test(`${name}: gains and losses also differ in lightness, not only hue`, () => {
    // A colour-blind reader separates them by lightness; both are always shown with ▲ / ▼ too
    const ratio = contrast(t.success, t.danger);
    assert.ok(ratio >= 1.25, `success vs danger lightness ratio ${ratio.toFixed(2)}`);
  });

  test(`${name}: the forecast series is not drawn in a gain or loss colour`, () => {
    assert.ok(![t.success, t.danger].includes(t.chartForecast));
    assert.notEqual(t.chartForecast, t.chartPortfolio);
  });
}

test('every token is a 6-digit hex colour in both themes', () => {
  for (const name of THEMES) {
    for (const [key, value] of Object.entries(themes[name])) {
      assert.match(value, /^#[0-9A-F]{6}$/, `${name}.${key}`);
    }
  }
  assert.deepEqual(Object.keys(themes.dark).sort(), Object.keys(themes.light).sort());
});
