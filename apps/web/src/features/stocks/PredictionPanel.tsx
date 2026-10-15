import type { UseQueryResult } from '@tanstack/react-query';
import { AlertTriangle, Info } from 'lucide-react';
import { getErrorCode, getErrorDetail, getErrorStatus } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { Prediction } from '@investiq/shared-types';
import { Card } from '../../components/ui/Card';
import { ErrorState, Figure, Notice, Skeleton } from '../../components/ui/Feedback';
import { formatDate, formatPct, formatPrice, formatSignedPct } from '../../lib/format';
import {
  confidenceLevel,
  forecastDirection,
  unavailableMessageKey,
  type ConfidenceLevel,
} from './predictionView';
import { SignalBadge } from './badges';

// The meter never uses the gain colour: confidence is not a result (Design.md §6.4)
const LEVEL_COLOR: Record<ConfidenceLevel, string> = {
  low: 'bg-warning',
  medium: 'bg-primary',
  high: 'bg-primary',
};

const LEVEL_SEGMENTS: Record<ConfidenceLevel, number> = { low: 1, medium: 2, high: 3 };

/** 3-segment Low/Medium/High meter (Design.md §6.4). */
const ConfidenceMeter = ({ value, threshold }: { value: number; threshold: number }) => {
  const { t } = useTranslation();
  const level = confidenceLevel(value, threshold);
  return (
    <div>
      <div className="flex items-center justify-between gap-4 text-sm">
        <span className="flex items-center gap-2 text-muted" title={t('prediction.confidenceHelp')}>
          {t('prediction.confidence')}
          <Info className="h-3.5 w-3.5 text-muted" aria-label={t('prediction.confidenceHelp')} />
        </span>
        <span className="font-semibold">
          {t(`prediction.level.${level}`)} · <Figure>{formatPct(value)}</Figure>
        </span>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2" aria-hidden="true">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className={`h-2 rounded-full ${i <= LEVEL_SEGMENTS[level] ? LEVEL_COLOR[level] : 'bg-line'}`}
          />
        ))}
      </div>
    </div>
  );
};

const LowConfidenceNote = ({ prediction }: { prediction: Prediction }) => {
  const { t } = useTranslation();
  return (
    <div className="rounded-control border border-warning bg-warning-tint p-4 text-sm text-warning">
      <p className="flex items-center gap-2 font-semibold">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        {t('prediction.lowConfidenceTitle')}
      </p>
      <p className="mt-2">{t('prediction.lowConfidenceIntro')}</p>
      <ul className="mt-2 list-disc space-y-2 ps-6">
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
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-4 text-sm">
      <span className="flex items-center gap-2 text-muted" title={t('prediction.signalHelp')}>
        {t('prediction.signalTitle')}
        <Info className="h-3.5 w-3.5 text-muted" aria-label={t('prediction.signalHelp')} />
      </span>
      <span className="flex items-center gap-2">
        <SignalBadge signal={prediction.signal} large />
        {prediction.signal_probability != null && (
          <span className="text-muted">
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
    <details className="rounded-control bg-sunken p-4 text-sm text-ink">
      <summary className="cursor-pointer font-medium text-ink">
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
        <p className="text-xs text-muted">{t('prediction.evaluationNote')}</p>
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
        <p className="font-medium text-ink">{t('prediction.notCoveredTitle')}</p>
        <p className="mt-2">
          {t(key, { ticker, stocks: getErrorDetail(error)?.covered_stock_count })}
        </p>
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
        <div className="space-y-4">
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
      <div className="space-y-6">
        {p.as_of_date && (
          <p className="text-xs text-muted">
            {t('prediction.asOf', {
              date: formatDate(p.as_of_date, i18n.language),
              price: formatPrice(p.last_close),
            })}
          </p>
        )}
        <div>
          <p className="text-xs text-muted">{t('prediction.forecastLabel')}</p>
          <p className="text-3xl font-bold">
            <Figure>{formatPrice(p.forecast_price)}</Figure>{' '}
            <Figure
              className={`text-base font-medium ${
                direction === 'up'
                  ? 'text-success'
                  : direction === 'down'
                    ? 'text-danger'
                    : 'text-muted'
              }`}
            >
              {formatSignedPct(p.expected_change_pct)}
            </Figure>
          </p>
          <p className="mt-2 text-sm text-muted">
            {t(`prediction.forecast.${direction}`, {
              pct: `${Math.abs(p.expected_change_pct).toFixed(2)}%`,
            })}
          </p>
        </div>

        <ConfidenceMeter value={p.confidence_score} threshold={p.low_confidence_threshold} />

        {p.low_confidence && <LowConfidenceNote prediction={p} />}

        <SignalRow prediction={p} />

        <EvaluationDetails prediction={p} />

        {/* 'unavailable' is already explained in the low-confidence note (PRD FR22) */}
        {p.sentiment_status !== 'unavailable' && (
          <p className="text-xs text-muted">
            {t(p.sentiment_status === 'used' ? 'prediction.inputs.used' : 'prediction.inputs.none')}
          </p>
        )}

        <p className="text-xs text-muted">
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
      <h2 className="text-lg font-semibold text-ink">{t('prediction.title')}</h2>
      <p className="mt-2 mb-6 text-sm text-muted">{t('prediction.subtitle')}</p>
      {body()}
    </Card>
  );
};
