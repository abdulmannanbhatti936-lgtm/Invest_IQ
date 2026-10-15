import { useState } from 'react';
import { useTranslation } from '@investiq/i18n';
import type { PortfolioHolding } from '@investiq/shared-types';
import { Donut, donutColors, LegendSwatch } from '../../components/ui/Donut';
import { CompanyName } from '../../components/ui/CompanyName';
import { Figure } from '../../components/ui/Feedback';
import { formatPctString } from '../../lib/format';
import { useThemeColors } from '../../lib/theme';

/** A holding's share of the money, as the portfolio screen has always shown it (2 decimals). */
export const allocationLabel = (holding: PortfolioHolding) =>
  formatPctString(Number(holding.allocation_pct).toFixed(2));

/**
 * The portfolio's allocation: a donut of each holding's share of the money (the engine's own
 * allocation_pct) with a legend that carries the figures. Shared by the dashboard and the
 * portfolio screen.
 */
export const AllocationChart = ({
  holdings,
  center,
  size = 176,
  compact = false,
}: {
  holdings: PortfolioHolding[];
  center?: React.ReactNode;
  size?: number;
  /** Two-column legend without company names, for the dashboard */
  compact?: boolean;
}) => {
  const { t } = useTranslation();
  const theme = useThemeColors();
  const colors = donutColors(holdings.length, theme);
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center">
      <Donut
        size={size}
        label={t('portfolio.allocationChart', { count: holdings.length })}
        segments={holdings.map((h) => ({ key: h.ticker, value: Number(h.allocation_pct) }))}
        activeKey={hovered}
        center={center}
      />
      <ul
        className={`grid w-full gap-x-6 gap-y-2 text-sm ${compact ? 'grid-cols-2' : 'grid-cols-1'}`}
      >
        {holdings.map((h, i) => (
          <li
            key={h.ticker}
            className="flex min-w-0 items-center justify-between gap-2 rounded-control px-2"
            onMouseEnter={() => setHovered(h.ticker)}
            onMouseLeave={() => setHovered(null)}
          >
            <span className="flex min-w-0 items-center gap-2">
              <LegendSwatch color={colors[i]} />
              <span dir="ltr" className="font-semibold text-ink">
                {h.ticker}
              </span>
              {!compact && <CompanyName name={h.name} className="text-muted" />}
            </span>
            <Figure className="text-ink">{allocationLabel(h)}</Figure>
          </li>
        ))}
      </ul>
    </div>
  );
};
