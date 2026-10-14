import type { ReactNode } from 'react';

export interface LegendItem {
  key: string;
  label: ReactNode;
  color: string;
  /** How the series is drawn, so the key matches the chart without relying on colour alone */
  kind: 'line' | 'dashed' | 'dotted' | 'area' | 'point';
}

const Swatch = ({ color, kind }: { color: string; kind: LegendItem['kind'] }) =>
  kind === 'area' ? (
    <span className="h-3 w-4 rounded-sm" style={{ background: color, opacity: 0.25 }} />
  ) : kind === 'point' ? (
    <span className="h-2 w-2 rounded-full ring-2 ring-offset-0" style={{ background: color }} />
  ) : (
    <svg width="24" height="8" aria-hidden="true">
      <line
        x1="0"
        y1="4"
        x2="24"
        y2="4"
        stroke={color}
        strokeWidth="2.5"
        strokeDasharray={kind === 'dashed' ? '6 4' : kind === 'dotted' ? '2 3' : undefined}
      />
    </svg>
  );

/** A chart key that is always visible, never only on hover (Design.md §18). */
export const ChartLegend = ({ items }: { items: LegendItem[] }) => (
  <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">
    {items.map((item) => (
      <li key={item.key} className="flex items-center gap-2">
        <Swatch color={item.color} kind={item.kind} />
        <span>{item.label}</span>
      </li>
    ))}
  </ul>
);
