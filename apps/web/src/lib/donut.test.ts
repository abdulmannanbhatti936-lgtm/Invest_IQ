// Run with: npm test (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { donutArcs, seriesColors } from './donut.ts';

test('arcs follow the shares in order and fill the circle', () => {
  const arcs = donutArcs([50, 30, 20], 0);
  assert.deepEqual(
    arcs.map((a) => [a.start, a.length]),
    [
      [0, 0.5],
      [0.5, 0.3],
      [0.8, 0.2],
    ],
  );
});

test('allocation percentages are drawn as given, never rescaled differently per segment', () => {
  const arcs = donutArcs([14.73, 14.24, 12.86], 0);
  const total = 14.73 + 14.24 + 12.86;
  assert.ok(Math.abs(arcs[1].length - 14.24 / total) < 1e-12);
});

test('empty or zero input gives empty arcs, not NaN', () => {
  assert.deepEqual(donutArcs([0, 0]), [
    { start: 0, length: 0 },
    { start: 0, length: 0 },
  ]);
});

test('series colours run from the first stop to the last', () => {
  const colors = seriesColors(3, ['#000000', '#FFFFFF']);
  assert.deepEqual(colors, ['#000000', '#808080', '#FFFFFF']);
  assert.deepEqual(seriesColors(1, ['#123456', '#FFFFFF']), ['#123456']);
});
