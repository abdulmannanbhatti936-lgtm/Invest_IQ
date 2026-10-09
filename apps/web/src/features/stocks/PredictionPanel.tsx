import type { UseQueryResult } from '@tanstack/react-query';
import { AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, Info } from 'lucide-react';
import { getErrorCode, getErrorStatus } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { Prediction, Signal } from '@investiq/shared-types';
import { Card } from '../../components/ui/Card';
import { ErrorState, Figure, Notice, Skeleton } from '../../components/ui/Feedback';
import { formatDate, formatPct, formatPrice, formatSignedPct } from '../../lib/format';

const SIGNAL_STYLE: Record<Signal, { className: string; icon: typeof ArrowUpRight }> = {
  BUY: { className: 'bg-green-100 text-green-800', icon: ArrowUpRight },
  SELL: { className: 'bg-red-100 text-red-800', icon: ArrowDownRight },
  HOLD: { className: 'bg-gray-100 text-gray-800', icon: ArrowRight },
};

/** 3-segment Low/Medium/High meter (Design.md §6.4). */
const ConfidenceMeter = ({ value, threshold }: { value: number; threshold: number }) => {
  const { t } = useTranslation();
  const level = value < threshold ? 'low' : value < 0.75 ? 'medium' : 'high';
  const filled = level === 'low' ? 1 : level === 'medium' ? 2 : 3;
  const color =
    level === 'low' ? 'bg-amber-500' : level === 'medium' ? 'bg-sky-500' : 'bg-green-600';
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span
          className="flex items-center gap-1 text-gray-600"
          title={t('prediction.confidenceHelp')}
        >
          {t('prediction.confidence')}
          <Info className="h-3.5 w-3.5 text-gray-400" aria-label={t('prediction.confidenceHelp')} />
        </span>
        <span className="font-semibold">
          {t(`prediction.level.${level}`)} · <Figure>{formatPct(value)}</Figure>
        </span>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-1" aria-hidden="true">
        {[1, 2, 3].map((i) => (
          <div key={i} className={`h-2 rounded-full ${i <= filled ? color : 'bg-gray-200'}`} />
        ))}
      </div>
    </div>
  );
};

export const PredictionPanel = ({ query }: { query: UseQueryResult<Prediction> }) => {
  const { t, i18n } = useTranslation();

  const body = () => {
    if (query.isPending) {
      return (
        <div className="space-y-3">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-2 w-full" />
        </div>
      );
    }
    if (query.isError) {
      if (getErrorStatus(query.error) === 404) {
        const code = getErrorCode(query.error);
        const key =
          code === 'insufficient_data'
            ? 'prediction.insufficientData'
            : code === 'not_ready'
              ? 'prediction.notReady'
              : 'prediction.notTracked';
        return (
          <Notice tone={code === 'insufficient_data' ? 'warning' : 'neutral'}>{t(key)}</Notice>
        );
      }
      return (
        <ErrorState message={t('prediction.loadError')} onRetry={() => void query.refetch()} />
      );
    }

    const p = query.data;
    const { className, icon: SignalIcon } = SIGNAL_STYLE[p.signal];
    const ev = p.evaluation;
    return (
      <div className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs text-gray-500">{t('prediction.forecastLabel')}</p>
            <p className="text-3xl font-bold">
              <Figure>{formatPrice(p.forecast_price)}</Figure>
            </p>
            <p className="text-sm text-gray-600">
              <Figure
                className={
                  p.expected_change_pct > 0
                    ? 'text-green-700'
                    : p.expected_change_pct < 0
                      ? 'text-red-700'
                      : ''
                }
              >
                {formatSignedPct(p.expected_change_pct)}
              </Figure>{' '}
              {t('prediction.fromClose', { price: formatPrice(p.last_close) })}
            </p>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-base font-semibold ${className}`}
          >
            <SignalIcon className="h-4 w-4 rtl:-scale-x-100" />
            {t(`prediction.signal.${p.signal}`)}
          </span>
        </div>

        <ConfidenceMeter value={p.confidence_score} threshold={p.low_confidence_threshold} />

        {p.low_confidence && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
            <p className="flex items-center gap-2 font-semibold">
              <AlertTriangle className="h-4 w-4" />
              {t('prediction.lowConfidenceTitle')}
            </p>
            <p className="mt-1">
              {p.models_agree
                ? t('prediction.lowConfidenceBody', {
                    threshold: Math.round(p.low_confidence_threshold * 100),
                  })
                : t('prediction.disagree')}
            </p>
          </div>
        )}

        {ev && (
          <details className="rounded-lg bg-gray-50 p-4 text-sm text-gray-700">
            <summary className="cursor-pointer font-medium text-gray-900">
              {t('prediction.evaluationTitle')}
            </summary>
            <p className="mt-2 leading-relaxed">
              {t('prediction.evaluationBody', {
                start: formatDate(ev.test_start_date, i18n.language),
                end: formatDate(ev.test_end_date, i18n.language),
                direction: formatPct(ev.lstm_directional_accuracy),
                accuracy: formatPct(ev.classifier_accuracy),
                baseline: formatPct(ev.classifier_baseline_accuracy),
                rmse: `${ev.lstm_rmse_pct.toFixed(1)}%`,
              })}
            </p>
            <p className="mt-2 text-xs text-gray-500">{t('prediction.evaluationNote')}</p>
          </details>
        )}

        <p className="text-xs text-gray-400">
          {t('prediction.generated', {
            date: formatDate(p.generated_at, i18n.language),
            version: p.model_version,
          })}
        </p>
      </div>
    );
  };

  const flagged = query.data?.low_confidence;
  return (
    // Low-confidence predictions get a visibly different card, not just a note (Design.md §6.4)
    <Card className={flagged ? 'border-2 border-amber-300 bg-amber-50/30' : ''}>
      <h2 className="text-lg font-semibold text-gray-900">{t('prediction.title')}</h2>
      <p className="mt-1 mb-5 text-sm text-gray-500">{t('prediction.subtitle')}</p>
      {body()}
    </Card>
  );
};
