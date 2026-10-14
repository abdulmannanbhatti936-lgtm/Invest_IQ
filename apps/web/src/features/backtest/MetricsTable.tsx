import type { ReactNode } from 'react';
import { useTranslation } from '@investiq/i18n';
import type { BacktestMetrics, BacktestResult } from '@investiq/shared-types';
import { Figure } from '../../components/ui/Feedback';
import { formatDate, formatPctString } from '../../lib/format';
import { isLoss, ratioToPct, roundDecimal } from './backtestView';

interface Column {
  key: string;
  label: string;
  metrics: BacktestMetrics;
}

const pct = (ratio: string | null, signed = true) =>
  ratio == null ? '—' : formatPctString(ratioToPct(ratio), signed);

/**
 * FR31 for every line on the chart: total return first, then the secondary measures, each
 * with one plain-language line (Design.md §7.4).
 */
export const MetricsTable = ({ result }: { result: BacktestResult }) => {
  const { t, i18n } = useTranslation();
  const date = (iso: string | null) => (iso ? formatDate(iso, i18n.language) : '—');

  const columns: Column[] = [
    {
      key: 'portfolio',
      label: t(result.kind === 'custom' ? 'backtest.columns.custom' : 'backtest.columns.portfolio'),
      metrics: result.portfolio.metrics,
    },
  ];
  if (result.start_date_rules.metrics) {
    columns.push({
      key: 'rules',
      label: t('backtest.columns.startDateRules'),
      metrics: result.start_date_rules.metrics,
    });
  }
  columns.push({
    key: 'benchmark',
    label: t('backtest.columns.benchmark'),
    metrics: result.benchmark.metrics,
  });
  if (result.kse100.metrics) {
    columns.push({
      key: 'kse100',
      label: t('backtest.columns.kse100'),
      metrics: result.kse100.metrics,
    });
  }

  const rows: { label: string; help: string; cell: (m: BacktestMetrics) => ReactNode }[] = [
    {
      label: t('backtest.metrics.totalReturn'),
      help: t('backtest.metrics.totalReturnHelp'),
      cell: (m) => (
        <Figure className={`font-semibold ${isLoss(m.total_return) ? 'text-danger' : ''}`}>
          {pct(m.total_return)}
        </Figure>
      ),
    },
    {
      label: t('backtest.metrics.annualised'),
      help: t('backtest.metrics.annualisedHelp'),
      cell: (m) => <Figure>{pct(m.annualised_return)}</Figure>,
    },
    {
      label: t('backtest.metrics.sharpe'),
      help: t('backtest.metrics.sharpeHelp'),
      cell: (m) => <Figure>{m.sharpe_ratio == null ? '—' : roundDecimal(m.sharpe_ratio)}</Figure>,
    },
    {
      label: t('backtest.metrics.drawdown'),
      help: t('backtest.metrics.drawdownHelp'),
      cell: (m) => (
        <>
          <Figure className="block">{pct(m.max_drawdown, false)}</Figure>
          {m.drawdown_peak_date && (
            <span className="block text-xs text-muted">
              {t('backtest.metrics.drawdownDates', {
                from: date(m.drawdown_peak_date),
                to: date(m.drawdown_trough_date),
              })}
            </span>
          )}
        </>
      ),
    },
    {
      label: t('backtest.metrics.winRate'),
      help: t('backtest.metrics.winRateHelp'),
      cell: (m) => (
        <>
          <Figure className="block">{pct(m.win_rate, false)}</Figure>
          <span className="block text-xs text-muted">
            {t('backtest.metrics.winRateValue', { won: m.months_won, total: m.months_total })}
          </span>
        </>
      ),
    },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-sm">
        <caption className="sr-only">{t('backtest.metrics.caption')}</caption>
        <thead>
          <tr className="border-b border-line text-start text-xs text-muted">
            <th scope="col" className="py-2 pe-4 text-start font-medium">
              {t('backtest.metrics.measure')}
            </th>
            {columns.map((c) => (
              <th key={c.key} scope="col" className="px-4 py-2 text-end font-medium">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-line align-top last:border-0">
              <th scope="row" className="py-4 pe-4 text-start font-normal">
                <span className="block font-medium text-ink">{row.label}</span>
                <span className="block text-xs text-muted">{row.help}</span>
              </th>
              {columns.map((c) => (
                <td key={c.key} className="px-4 py-4 text-end text-ink">
                  {row.cell(c.metrics)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
