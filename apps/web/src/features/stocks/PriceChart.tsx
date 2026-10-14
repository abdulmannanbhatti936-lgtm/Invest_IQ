import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useTranslation } from '@investiq/i18n';
import type { Prediction, PricePoint } from '@investiq/shared-types';
import { ChartLegend } from '../../components/ui/ChartLegend';
import { Figure } from '../../components/ui/Feedback';
import { chartStyle, DRAW_IN_MS, useDrawInOnce } from '../../lib/chartTheme';
import { formatCompact, formatDate, formatPct, formatPrice, ltr } from '../../lib/format';
import { useThemeColors } from '../../lib/theme';
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
 * Closing-price line plus the next-day forecast as a dashed continuation ending in a marked
 * point, so a forecast is never drawn like real data; a shaded band for the model's typical
 * error on this stock; the forecast day shaded; the key always visible with the forecast's
 * confidence (Design.md §18); daily volume below (FR8). Draws in once, on first load.
 */
export const PriceChart = ({
  history,
  prediction,
}: {
  history: PricePoint[];
  prediction?: Prediction;
}) => {
  const { t, i18n } = useTranslation();
  const c = useThemeColors();
  const style = chartStyle(c);
  const animate = useDrawInOnce(history.length > 0);

  const rows: ChartRow[] = history.map((p) => ({
    date: p.timestamp,
    close: p.close,
    volume: p.volume,
  }));
  const band = prediction ? forecastBand(prediction) : null;
  let lastDate: string | null = null;
  let forecastDate: string | null = null;
  if (prediction && rows.length > 0) {
    const last = rows[rows.length - 1];
    last.forecast = last.close; // joins the dashed line to the real one
    if (band && last.close != null) last.band = [last.close, last.close]; // band opens from 0
    lastDate = last.date;
    forecastDate = nextBusinessDay(last.date);
    rows.push({
      date: forecastDate,
      forecast: prediction.forecast_price,
      band: band ?? undefined,
    });
  }

  const legend = [
    {
      key: 'close',
      label: t('stockDetail.chartActual'),
      color: c.chartPortfolio,
      kind: 'line' as const,
    },
    ...(prediction
      ? [
          {
            key: 'forecast',
            color: c.chartForecast,
            kind: 'dashed' as const,
            label: (
              <>
                {t('stockDetail.chartForecast')}:{' '}
                <Figure className="font-semibold text-ink">
                  {formatPrice(prediction.forecast_price)}
                </Figure>{' '}
                (
                {t(
                  prediction.low_confidence
                    ? 'stockDetail.forecastConfidenceLow'
                    : 'stockDetail.forecastConfidence',
                  { pct: ltr(formatPct(prediction.confidence_score)) },
                )}
                )
              </>
            ),
          },
        ]
      : []),
    ...(band
      ? [
          {
            key: 'band',
            label: t('stockDetail.chartBand'),
            color: c.chartForecast,
            kind: 'area' as const,
          },
        ]
      : []),
  ];

  const date = (v: string) => formatDate(v, i18n.language);

  return (
    <div className="space-y-4">
      <ChartLegend items={legend} />
      {/* Time always runs left-to-right, even in the Urdu layout */}
      <div className="w-full" dir="ltr">
        <p className="mb-2 ps-16 text-xs text-muted">{t('stockDetail.priceAxis')}</p>
        <div className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={rows}
              syncId={SYNC_ID}
              margin={{ top: 8, right: 8, left: 8, bottom: 4 }}
            >
              <CartesianGrid {...style.grid} />
              {lastDate && forecastDate && (
                <ReferenceArea
                  x1={lastDate}
                  x2={forecastDate}
                  shape={(p: { x?: number; y?: number; width?: number; height?: number }) => (
                    <rect
                      x={p.x}
                      y={p.y}
                      width={p.width}
                      height={p.height}
                      fill={c.chartForecast}
                      fillOpacity={0.08}
                    />
                  )}
                />
              )}
              <XAxis
                dataKey="date"
                tickFormatter={date}
                tickMargin={8}
                minTickGap={48}
                padding={{ right: 24 }}
                {...style.axis}
              />
              <YAxis
                domain={['auto', 'auto']}
                tickFormatter={(v: number) => `Rs. ${v.toFixed(0)}`}
                width={72}
                {...style.axis}
              />
              <Tooltip
                {...style.tooltip}
                labelFormatter={(v) => date(String(v))}
                formatter={(value, name) => [
                  Array.isArray(value)
                    ? `${formatPrice(Number(value[0]))} – ${formatPrice(Number(value[1]))}`
                    : formatPrice(Number(value)),
                  name,
                ]}
              />
              {band && (
                <Area
                  name={t('stockDetail.chartBand')}
                  type="linear"
                  dataKey="band"
                  stroke="none"
                  fill={c.chartForecast}
                  fillOpacity={0.18}
                  isAnimationActive={false}
                  connectNulls
                />
              )}
              <Line
                name={t('stockDetail.chartActual')}
                type="linear"
                dataKey="close"
                stroke={c.chartPortfolio}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                connectNulls={false}
                isAnimationActive={animate}
                animationDuration={DRAW_IN_MS}
              />
              {prediction && (
                <Line
                  name={t('stockDetail.chartForecast')}
                  type="linear"
                  dataKey="forecast"
                  stroke={c.chartForecast}
                  strokeWidth={2.5}
                  strokeDasharray="6 4"
                  // The forecast day gets a large ringed point; the joining point stays plain
                  dot={(props: { cx?: number; cy?: number; index?: number }) =>
                    props.index === rows.length - 1 ? (
                      <g key="forecast-point">
                        <circle
                          cx={props.cx}
                          cy={props.cy}
                          r={9}
                          fill={c.chartForecast}
                          opacity={0.25}
                        />
                        <circle
                          cx={props.cx}
                          cy={props.cy}
                          r={5}
                          fill={c.chartForecast}
                          stroke={c.surface}
                          strokeWidth={2}
                        />
                      </g>
                    ) : (
                      <g key={`f-${props.index}`} />
                    )
                  }
                  connectNulls
                  isAnimationActive={false}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 ps-16 text-xs text-muted">{t('stockDetail.volumeTitle')}</p>
        <div className="h-[96px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={rows}
              syncId={SYNC_ID}
              margin={{ top: 4, right: 8, left: 8, bottom: 0 }}
            >
              <XAxis dataKey="date" hide padding={{ right: 24 }} />
              <YAxis tickFormatter={(v: number) => formatCompact(v)} width={72} {...style.axis} />
              <Tooltip
                {...style.tooltip}
                cursor={{ fill: c.surfaceSunken }}
                labelFormatter={(v) => date(String(v))}
                formatter={(value) => [formatCompact(Number(value)), t('stockDetail.stats.volume')]}
              />
              <Bar
                dataKey="volume"
                fill={c.borderStrong}
                fillOpacity={0.6}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
