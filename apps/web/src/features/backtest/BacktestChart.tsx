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
import { formatCompact, formatDate, formatMoney, formatPrice } from '../../lib/format';
import { chartRows, type ChartRow } from './backtestView';

interface LineStyle {
  key: keyof Omit<ChartRow, 'date'>;
  label: string;
  color: string;
  width: number;
  dash?: string;
}

/** A short sample of the line as drawn, so the legend matches it without colour alone. */
const Swatch = ({ style }: { style: LineStyle }) => (
  <svg width="28" height="10" aria-hidden="true" className="shrink-0">
    <line
      x1="0"
      y1="5"
      x2="28"
      y2="5"
      stroke={style.color}
      strokeWidth={style.width}
      strokeDasharray={style.dash}
    />
  </svg>
);

/**
 * Portfolio vs the stand-in benchmark (and the start-date rules and KSE-100 when present), in
 * rupees from the same capital. Every line differs in colour and dash pattern, and the legend
 * is always shown above the chart, not only on hover (Design.md §18).
 */
export const BacktestChart = ({ result }: { result: BacktestResult }) => {
  const { t, i18n } = useTranslation();
  const rows = chartRows(result.series);
  const hasRules = result.start_date_rules.status === 'available';
  const hasKse = result.kse100.status === 'available';

  const lines: LineStyle[] = [
    {
      key: 'portfolio',
      label: t(result.kind === 'custom' ? 'backtest.columns.custom' : 'backtest.columns.portfolio'),
      color: '#2563eb',
      width: 2.5,
    },
    ...(hasRules
      ? [
          {
            key: 'startDateRules' as const,
            label: t('backtest.columns.startDateRules'),
            color: '#d97706',
            width: 1.5,
            dash: '2 3',
          },
        ]
      : []),
    {
      key: 'benchmark',
      label: t('backtest.columns.benchmark'),
      color: '#6b7280',
      width: 2,
      dash: '6 4',
    },
    ...(hasKse
      ? [
          {
            key: 'kse100' as const,
            label: t('backtest.columns.kse100'),
            color: '#111827',
            width: 1.5,
          },
        ]
      : []),
  ];
  const last = result.series[result.series.length - 1];

  return (
    <div className="space-y-3">
      <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-gray-700">
        {lines.map((style) => (
          <li key={style.key} className="flex items-center gap-2">
            <Swatch style={style} />
            {style.label}
          </li>
        ))}
      </ul>
      {/* Time always runs left-to-right, even in the Urdu layout */}
      <div dir="ltr">
        <p className="mb-2 ps-16 text-xs text-gray-500">{t('backtest.chart.axis')}</p>
        <div className="h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 5, right: 16, left: 8, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
              <XAxis
                dataKey="date"
                tickFormatter={(v: string) => formatDate(v, i18n.language)}
                tick={{ fontSize: 12 }}
                tickMargin={10}
                minTickGap={48}
                stroke="#9ca3af"
              />
              <YAxis
                domain={['auto', 'auto']}
                tick={{ fontSize: 12 }}
                tickFormatter={(v: number) => formatCompact(v)}
                stroke="#9ca3af"
                width={56}
              />
              <Tooltip
                labelFormatter={(v) => formatDate(String(v), i18n.language)}
                formatter={(value, name) => [formatPrice(Number(value)), name]}
              />
              {lines.map((style) => (
                <Line
                  key={style.key}
                  name={style.label}
                  type="linear"
                  dataKey={style.key}
                  stroke={style.color}
                  strokeWidth={style.width}
                  strokeDasharray={style.dash}
                  dot={false}
                  activeDot={{ r: 4 }}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <p className="text-sm text-gray-600">
        {t('backtest.chart.summary', {
          years: result.period.years,
          portfolio: formatMoney(last.portfolio),
          benchmark: formatMoney(last.benchmark),
        })}
      </p>
    </div>
  );
};
