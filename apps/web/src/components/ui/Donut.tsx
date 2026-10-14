import { useEffect, useState, type ReactNode } from 'react';
import { donutArcs, seriesColors } from '../../lib/donut';
import { useThemeColors } from '../../lib/theme';

export interface DonutSegment {
  key: string;
  value: number;
}

const R = 42;
const C = 2 * Math.PI * R;

/**
 * Allocation donut drawn in SVG (no chart library, so the landing page can use it too). The
 * segments draw in once on first appearance and glide when the values change (the landing
 * page's risk demo); both are off under reduced motion via the global CSS rule. The legend
 * next to it carries the figures, so colour is never the only key (Design.md §9).
 */
export const Donut = ({
  segments,
  center,
  size = 176,
  label,
  activeKey,
}: {
  segments: DonutSegment[];
  center?: ReactNode;
  size?: number;
  /** Accessible summary of the chart */
  label: string;
  activeKey?: string | null;
}) => {
  const theme = useThemeColors();
  const colors = donutColors(segments.length, theme);
  const arcs = donutArcs(segments.map((s) => s.value));
  const [drawn, setDrawn] = useState(false);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setDrawn(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" role="img" aria-label={label} className="h-full w-full -rotate-90">
        <circle cx="50" cy="50" r={R} fill="none" stroke={theme.surfaceSunken} strokeWidth="12" />
        {arcs.map((arc, i) => (
          <circle
            key={segments[i].key}
            cx="50"
            cy="50"
            r={R}
            fill="none"
            stroke={colors[i]}
            strokeWidth={activeKey === segments[i].key ? 14 : 12}
            strokeDasharray={`${drawn ? arc.length * C : 0} ${C}`}
            strokeDashoffset={-arc.start * C}
            opacity={activeKey && activeKey !== segments[i].key ? 0.45 : 1}
            style={{
              transition:
                'stroke-dasharray 400ms var(--iq-ease-enter), stroke-dashoffset 400ms var(--iq-ease-enter), opacity 150ms, stroke-width 150ms',
            }}
          />
        ))}
      </svg>
      {center && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          {center}
        </div>
      )}
    </div>
  );
};

/** The donut's colours, exported so legends use exactly the same swatches. */
export const donutColors = (
  n: number,
  theme: { chartPortfolio: string; gradient2: string; chartForecast: string },
) => seriesColors(n, [theme.chartPortfolio, theme.gradient2, theme.chartForecast]);

export const LegendSwatch = ({ color }: { color: string }) => (
  <span
    className="inline-block h-2 w-2 shrink-0 rounded-full"
    style={{ backgroundColor: color }}
    aria-hidden="true"
  />
);
