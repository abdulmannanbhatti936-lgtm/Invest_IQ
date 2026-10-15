import { useEffect, useState } from 'react';
import { motion } from '@investiq/design-tokens';
import type { ThemeColors } from '@investiq/design-tokens';

/** Axis, grid and tooltip styling from the active theme, shared by every chart (Design §18). */
export const chartStyle = (c: ThemeColors) => ({
  grid: { stroke: c.border, strokeDasharray: '3 3', vertical: false },
  axis: {
    stroke: c.borderStrong,
    tick: { fontSize: 12, fill: c.textSecondary },
    tickLine: false,
  },
  tooltip: {
    contentStyle: {
      background: c.surface,
      border: `1px solid ${c.border}`,
      borderRadius: 10,
      color: c.textPrimary,
      fontSize: 13,
    },
    labelStyle: { color: c.textSecondary },
    itemStyle: { color: c.textPrimary },
    cursor: { stroke: c.borderStrong, strokeDasharray: '3 3' },
  },
});

/** Chart draw-in length: the app-wide cap (Design.md §11: nothing over 400 ms). */
export const DRAW_IN_MS = parseInt(motion.duration.max, 10);

/**
 * Charts draw in once, on their first load only; later data (another period, a refetch)
 * appears at once instead of re-animating (Design.md §11).
 */
export const useDrawInOnce = (ready: boolean): boolean => {
  const [animate, setAnimate] = useState(true);
  useEffect(() => {
    if (!ready || !animate) return;
    const id = window.setTimeout(() => setAnimate(false), DRAW_IN_MS + 100);
    return () => window.clearTimeout(id);
  }, [ready, animate]);
  return animate;
};
