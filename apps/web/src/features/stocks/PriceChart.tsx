import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useTranslation } from '@investiq/i18n';
import type { Prediction, PricePoint } from '@investiq/shared-types';
import { formatCompact, formatDate, formatPrice } from '../../lib/format';
import { forecastBand } from './predictionView';

interface ChartRow {
  date: string;
  close?: number;
  forecast?: number;
  band?: [number, number];
  volume?: number;
}

// Shared by the price and volume charts so hovering one highlights the same day in both
const SYNC_ID = 'stock-detail';

const nextBusinessDay = (iso: string): string => {
  const d = new Date(iso);
  do {
    d.setDate(d.getDate() + 1);
  } while (d.getDay() === 0 || d.getDay() === 6);
  return d.toISOString();
};

/**
 * Closing-price line plus the next-day forecast as a dashed continuation, so a forecast is
 * never drawn like real data, with a shaded band for the model's typical error on this stock
 * (Design.md §18), and daily volume below (FR8).
 */
export const PriceChart = ({
  history,
  prediction,
}: {
  history: PricePoint[];
  prediction?: Prediction;
}) => {
  const { t, i18n } = useTranslation();

  const rows: ChartRow[] = history.map((p) => ({
    date: p.timestamp,
    close: p.close,
    volume: p.volume,
  }));
  const band = prediction ? forecastBand(prediction) : null;
  if (prediction && rows.length > 0) {
    const last = rows[rows.length - 1];
    last.forecast = last.close; // joins the dashed line to the real one
    if (band && last.close != null) last.band = [last.close, last.close]; // band opens from 0
    rows.push({
      date: nextBusinessDay(last.date),
      forecast: prediction.forecast_price,
      band: band ?? undefined,
    });
  }

  return (
    // Time always runs left-to-right, even in the Urdu layout
    <div className="w-full" dir="ltr">
      <div className="h-[320px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={rows}
            syncId={SYNC_ID}
            margin={{ top: 5, right: 16, left: 8, bottom: 5 }}
          >
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
              formatter={(value, name) => [
                Array.isArray(value)
                  ? `${formatPrice(Number(value[0]))} – ${formatPrice(Number(value[1]))}`
                  : formatPrice(Number(value)),
                name,
              ]}
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
            {band && (
              <Area
                name={t('stockDetail.chartBand')}
                type="linear"
                dataKey="band"
                stroke="none"
                fill="#9333ea"
                fillOpacity={0.12}
                isAnimationActive={false}
                connectNulls
              />
            )}
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
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 ps-16 text-xs text-gray-500">{t('stockDetail.volumeTitle')}</p>
      <div className="h-[96px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} syncId={SYNC_ID} margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
            <XAxis dataKey="date" hide />
            <YAxis
              tick={{ fontSize: 11 }}
              tickFormatter={(v: number) => formatCompact(v)}
              stroke="#9ca3af"
              width={56}
            />
            <Tooltip
              labelFormatter={(v) => formatDate(String(v), i18n.language)}
              formatter={(value) => [formatCompact(Number(value)), t('stockDetail.stats.volume')]}
            />
            <Bar dataKey="volume" fill="#d1d5db" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
