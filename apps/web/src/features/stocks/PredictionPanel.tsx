import type { UseQueryResult } from '@tanstack/react-query';
import { AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, Info } from 'lucide-react';
import { getErrorCode, getErrorStatus } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { Prediction, Signal } from '@investiq/shared-types';
import { Badge } from '../../components/ui/Badge';
import { Card } from '../../components/ui/Card';
import { ErrorState, Figure, Notice, Skeleton } from '../../components/ui/Feedback';
import { formatDate, formatPct, formatPrice, formatSignedPct } from '../../lib/format';
import {
  confidenceLevel,
  forecastDirection,
  unavailableMessageKey,
  type ConfidenceLevel,
} from './predictionView';

const SIGNAL_BADGE: Record<
  Signal,
  { variant: 'success' | 'danger' | 'neutral'; icon: typeof ArrowUpRight }
> = {
  BUY: { variant: 'success', icon: ArrowUpRight },
  SELL: { variant: 'danger', icon: ArrowDownRight },
  HOLD: { variant: 'neutral', icon: ArrowRight },
};

const LEVEL_COLOR: Record<ConfidenceLevel, string> = {
  low: 'bg-amber-500',
  medium: 'bg-sky-500',
  high: 'bg-green-600',
};

const LEVEL_SEGMENTS: Record<ConfidenceLevel, number> = { low: 1, medium: 2, high: 3 };

/** 3-segment Low/Medium/High meter (Design.md §6.4). */
const ConfidenceMeter = ({ value, threshold }: { value: number; threshold: number }) => {
  const { t } = useTranslation();
  const level = confidenceLevel(value, threshold);
  return (
    <div>
      <div className="flex items-center justify-between gap-4 text-sm">
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
          <div
            key={i}
            className={`h-2 rounded-full ${i <= LEVEL_SEGMENTS[level] ? LEVEL_COLOR[level] : 'bg-gray-200'}`}
          />
        ))}
      </div>
    </div>
  );
};

const LowConfidenceNote = ({ prediction }: { prediction: Prediction }) => {
  const { t } = useTranslation();
  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
      <p className="flex items-center gap-2 font-semibold">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        {t('prediction.lowConfidenceTitle')}
      </p>
      <p className="mt-2">{t('prediction.lowConfidenceIntro')}</p>
      <ul className="mt-1 list-disc space-y-1 ps-5">
        {prediction.low_confidence_reasons.map((reason) => (
          <li key={reason}>
            {t(`prediction.reason.${reason}`, {
              threshold: Math.round(prediction.low_confidence_threshold * 100),
              ticker: prediction.ticker,
            })}
          </li>
        ))}
      </ul>
    </div>
  );
};

const SignalRow = ({ prediction }: { prediction: Prediction }) => {
  const { t } = useTranslation();
  const { variant, icon: SignalIcon } = SIGNAL_BADGE[prediction.signal];
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 pt-4 text-sm">
      <span className="flex items-center gap-1 text-gray-600" title={t('prediction.signalHelp')}>
        {t('prediction.signalTitle')}
        <Info className="h-3.5 w-3.5 text-gray-400" aria-label={t('prediction.signalHelp')} />
      </span>
      <span className="flex items-center gap-2">
        <Badge variant={variant} className="gap-1 text-sm">
          <SignalIcon className="h-3.5 w-3.5 rtl:-scale-x-100" />
          {t(`prediction.signal.${prediction.signal}`)}
        </Badge>
        {prediction.signal_probability != null && (
          <span className="text-gray-500">
            {t('prediction.signalProbability', {
              pct: formatPct(prediction.signal_probability),
            })}
          </span>
        )}
      </span>
    </div>
  );
};

const EvaluationDetails = ({ prediction }: { prediction: Prediction }) => {
  const { t, i18n } = useTranslation();
  const ev = prediction.evaluation;
  if (!ev) return null;
  const pct = (value: number | null) => (value == null ? '—' : formatPct(value));
  return (
    <details className="rounded-lg bg-gray-50 p-4 text-sm text-gray-700">
      <summary className="cursor-pointer font-medium text-gray-900">
        {t('prediction.evaluationTitle', { ticker: prediction.ticker })}
      </summary>
      <div className="mt-2 space-y-2 leading-relaxed">
        <p>
          {t('prediction.evaluationDirection', {
            start: formatDate(ev.test_start_date, i18n.language),
            end: formatDate(ev.test_end_date, i18n.language),
            direction: pct(ev.directional_accuracy),
            baselineDirection: t(`prediction.baselineDirection.${ev.baseline_direction}`),
            baseline: pct(ev.baseline_directional_accuracy),
          })}
        </p>
        <p>
          {t(
            ev.beats_naive ? 'prediction.evaluationErrorBeats' : 'prediction.evaluationErrorNoEdge',
            {
              error: `${ev.typical_error_pct.toFixed(1)}%`,
            },
          )}
        </p>
        <p>
          {t('prediction.evaluationSignal', {
            accuracy: pct(ev.classifier_accuracy),
            baseline: pct(ev.classifier_baseline_accuracy),
          })}
        </p>
        <p className="text-xs text-gray-500">{t('prediction.evaluationNote')}</p>
      </div>
    </details>
  );
};

const Unavailable = ({ error, ticker }: { error: unknown; ticker: string }) => {
  const { t } = useTranslation();
  const code = getErrorCode(error);
  const key = unavailableMessageKey(code);
  if (key === 'prediction.notCovered') {
    return (
      <Notice>
        <p className="font-medium text-gray-900">{t('prediction.notCoveredTitle')}</p>
        <p className="mt-1">{t(key, { ticker })}</p>
      </Notice>
    );
  }
  return <Notice tone={code === 'insufficient_data' ? 'warning' : 'neutral'}>{t(key)}</Notice>;
};

export const PredictionPanel = ({
  query,
  ticker,
}: {
  query: UseQueryResult<Prediction>;
  ticker: string;
}) => {
  const { t, i18n } = useTranslation();

  const body = () => {
    if (query.isPending) {
      return (
        <div className="space-y-3">
          <Skeleton className="h-4 w-56" />
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-6 w-64" />
          <Skeleton className="h-2 w-full" />
        </div>
      );
    }
    if (query.isError) {
      if (getErrorStatus(query.error) === 404) {
        return <Unavailable error={query.error} ticker={ticker.toUpperCase()} />;
      }
      return (
        <ErrorState message={t('prediction.loadError')} onRetry={() => void query.refetch()} />
      );
    }

    const p = query.data;
    const direction = forecastDirection(p.expected_change_pct);
    return (
      <div className="space-y-5">
        {p.as_of_date && (
          <p className="text-xs text-gray-500">
            {t('prediction.asOf', {
              date: formatDate(p.as_of_date, i18n.language),
              price: formatPrice(p.last_close),
            })}
          </p>
        )}
        <div>
          <p className="text-xs text-gray-500">{t('prediction.forecastLabel')}</p>
          <p className="text-3xl font-bold">
            <Figure>{formatPrice(p.forecast_price)}</Figure>{' '}
            <Figure
              className={`text-base font-medium ${
                direction === 'up'
                  ? 'text-green-700'
                  : direction === 'down'
                    ? 'text-red-700'
                    : 'text-gray-500'
              }`}
            >
              {formatSignedPct(p.expected_change_pct)}
            </Figure>
          </p>
          <p className="mt-1 text-sm text-gray-600">
            {t(`prediction.forecast.${direction}`, {
              pct: `${Math.abs(p.expected_change_pct).toFixed(2)}%`,
            })}
          </p>
        </div>

        <ConfidenceMeter value={p.confidence_score} threshold={p.low_confidence_threshold} />

        {p.low_confidence && <LowConfidenceNote prediction={p} />}

        <SignalRow prediction={p} />

        <EvaluationDetails prediction={p} />

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
    <Card tone={flagged ? 'warning' : 'default'}>
      <h2 className="text-lg font-semibold text-gray-900">{t('prediction.title')}</h2>
      <p className="mt-1 mb-5 text-sm text-gray-500">{t('prediction.subtitle')}</p>
      {body()}
    </Card>
  );
};
