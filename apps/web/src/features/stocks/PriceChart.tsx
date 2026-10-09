import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useTranslation } from '@investiq/i18n';
import type { Prediction, PricePoint } from '@investiq/shared-types';
import { formatDate, formatPrice } from '../../lib/format';

interface ChartRow {
  date: string;
  close?: number;
  forecast?: number;
}

const nextBusinessDay = (iso: string): string => {
  const d = new Date(iso);
  do {
    d.setDate(d.getDate() + 1);
  } while (d.getDay() === 0 || d.getDay() === 6);
  return d.toISOString();
};

/**
 * Closing-price line plus the next-day forecast as a dashed continuation, so a
 * forecast is never drawn like real data (Design.md §18).
 */
export const PriceChart = ({
  history,
  prediction,
}: {
  history: PricePoint[];
  prediction?: Prediction;
}) => {
  const { t, i18n } = useTranslation();

  const rows: ChartRow[] = history.map((p) => ({ date: p.timestamp, close: p.close }));
  if (prediction && rows.length > 0) {
    const last = rows[rows.length - 1];
    last.forecast = last.close; // joins the dashed line to the real one
    rows.push({ date: nextBusinessDay(last.date), forecast: prediction.forecast_price });
  }

  return (
    // Time always runs left-to-right, even in the Urdu layout
    <div className="h-[360px] w-full" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 5, right: 16, left: 8, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
          <XAxis
            dataKey="date"
            tickFormatter={(v: string) => formatDate(v, i18n.language)}
            tick={{ fontSize: 12 }}
            tickMargin={10}
            minTickGap={40}
            stroke="#9ca3af"
          />
          <YAxis
            domain={['auto', 'auto']}
            tick={{ fontSize: 12 }}
            tickFormatter={(v: number) => v.toFixed(0)}
            stroke="#9ca3af"
            width={56}
          />
          <Tooltip
            labelFormatter={(v) => formatDate(String(v), i18n.language)}
            formatter={(value, name) => [formatPrice(Number(value)), name]}
          />
          <Legend />
          <Line
            name={t('stockDetail.chartActual')}
            type="monotone"
            dataKey="close"
            stroke="#2563eb"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 5 }}
            connectNulls={false}
          />
          {prediction && (
            <Line
              name={t('stockDetail.chartForecast')}
              type="linear"
              dataKey="forecast"
              stroke="#9333ea"
              strokeWidth={2}
              strokeDasharray="6 4"
              dot={{ r: 3 }}
              connectNulls
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};
