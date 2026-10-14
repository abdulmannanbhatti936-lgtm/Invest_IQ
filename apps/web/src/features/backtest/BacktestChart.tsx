import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useTranslation } from '@investiq/i18n';
import type { BacktestResult } from '@investiq/shared-types';
import { ChartLegend } from '../../components/ui/ChartLegend';
import { chartStyle, DRAW_IN_MS, useDrawInOnce } from '../../lib/chartTheme';
import { formatCompact, formatDate, formatMoney, formatPrice } from '../../lib/format';
import { useThemeColors } from '../../lib/theme';
import { chartRows, type ChartRow } from './backtestView';

interface LineStyle {
  key: keyof Omit<ChartRow, 'date'>;
  label: string;
  color: string;
  width: number;
  dash?: string;
}

/**
 * Portfolio vs the stand-in benchmark (and the start-date rules and KSE-100 when present), in
 * rupees from the same capital. Every line differs in colour and dash pattern, and the legend
 * is always shown above the chart, not only on hover (Design.md §18).
 */
export const BacktestChart = ({ result }: { result: BacktestResult }) => {
  const { t, i18n } = useTranslation();
  const c = useThemeColors();
  const style = chartStyle(c);
  const animate = useDrawInOnce(true);
  const rows = chartRows(result.series);
  const hasRules = result.start_date_rules.status === 'available';
  const hasKse = result.kse100.status === 'available';

  const lines: LineStyle[] = [
    {
      key: 'portfolio',
      label: t(result.kind === 'custom' ? 'backtest.columns.custom' : 'backtest.columns.portfolio'),
      color: c.chartPortfolio,
      width: 2.5,
    },
    ...(hasRules
      ? [
          {
            key: 'startDateRules' as const,
            label: t('backtest.columns.startDateRules'),
            color: c.chartRules,
            width: 1.5,
            dash: '2 3',
          },
        ]
      : []),
    {
      key: 'benchmark',
      label: t('backtest.columns.benchmark'),
      color: c.chartBenchmark,
      width: 2,
      dash: '6 4',
    },
    ...(hasKse
      ? [
          {
            key: 'kse100' as const,
            label: t('backtest.columns.kse100'),
            color: c.textPrimary,
            width: 1.5,
          },
        ]
      : []),
  ];
  const last = result.series[result.series.length - 1];

  return (
    <div className="space-y-4">
      <ChartLegend
        items={lines.map((line) => ({
          key: line.key,
          label: line.label,
          color: line.color,
          kind: line.dash === '2 3' ? 'dotted' : line.dash ? 'dashed' : 'line',
        }))}
      />
      {/* Time always runs left-to-right, even in the Urdu layout */}
      <div dir="ltr">
        <p className="mb-2 ps-16 text-xs text-muted">{t('backtest.chart.axis')}</p>
        <div className="h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 16, left: 8, bottom: 4 }}>
              <CartesianGrid {...style.grid} />
              <XAxis
                dataKey="date"
                tickFormatter={(v: string) => formatDate(v, i18n.language)}
                tickMargin={8}
                minTickGap={48}
                {...style.axis}
              />
              <YAxis
                domain={['auto', 'auto']}
                tickFormatter={(v: number) => `Rs. ${formatCompact(v)}`}
                width={80}
                {...style.axis}
              />
              <Tooltip
                {...style.tooltip}
                labelFormatter={(v) => formatDate(String(v), i18n.language)}
                formatter={(value, name) => [formatPrice(Number(value)), name]}
              />
              {lines.map((line) => (
                <Line
                  key={line.key}
                  name={line.label}
                  type="linear"
                  dataKey={line.key}
                  stroke={line.color}
                  strokeWidth={line.width}
                  strokeDasharray={line.dash}
                  dot={false}
                  activeDot={{ r: 4 }}
                  isAnimationActive={animate}
                  animationDuration={DRAW_IN_MS}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <p className="text-sm text-muted">
        {t('backtest.chart.summary', {
          years: result.period.years,
          portfolio: formatMoney(last.portfolio),
          benchmark: formatMoney(last.benchmark),
        })}
      </p>
    </div>
  );
};
