// Geometry and colours for the allocation donut, as pure functions (tested in donut.test.ts).

export interface Arc {
  /** Where the segment starts and how long it is, as fractions of the full circle */
  start: number;
  length: number;
}

/** Segments in order around the circle; values are shares (any unit), never re-weighted. */
export const donutArcs = (values: number[], gap = 0.004): Arc[] => {
  const total = values.reduce((sum, v) => sum + Math.max(0, v), 0);
  if (total <= 0) return values.map(() => ({ start: 0, length: 0 }));
  let start = 0;
  return values.map((v) => {
    const share = Math.max(0, v) / total;
    const arc = { start, length: Math.max(0, share - (share > gap * 2 ? gap : 0)) };
    start += share;
    return arc;
  });
};

const hex = (c: string) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
const toHex = (rgb: number[]) =>
  `#${rgb
    .map((v) => Math.round(v).toString(16).padStart(2, '0'))
    .join('')
    .toUpperCase()}`;

/** `n` colours spread evenly along the given stops (the theme's series stops). */
export const seriesColors = (n: number, stops: string[]): string[] => {
  if (n <= 0) return [];
  if (n === 1) return [stops[0]];
  return Array.from({ length: n }, (_, i) => {
    const pos = (i / (n - 1)) * (stops.length - 1);
    const lo = Math.floor(pos);
    const hi = Math.min(stops.length - 1, lo + 1);
    const t = pos - lo;
    const [a, b] = [hex(stops[lo]), hex(stops[hi])];
    return toHex(a.map((v, k) => v + (b[k] - v) * t));
  });
};
