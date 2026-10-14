import {
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Frown,
  Meh,
  Smile,
} from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import type { SentimentLabel, Signal } from '@investiq/shared-types';
import { Badge } from '../../components/ui/Badge';
import { Figure } from '../../components/ui/Feedback';
import { formatPct } from '../../lib/format';
import { confidenceLevel } from './predictionView';

// Signals use arrow icons, sentiment uses mood icons, so the two are never confused (Design §17)
const SIGNAL_BADGE: Record<
  Signal,
  { variant: 'success' | 'danger' | 'neutral'; icon: typeof ArrowUpRight }
> = {
  BUY: { variant: 'success', icon: ArrowUpRight },
  SELL: { variant: 'danger', icon: ArrowDownRight },
  HOLD: { variant: 'neutral', icon: ArrowRight },
};

const SENTIMENT_BADGE: Record<
  SentimentLabel,
  { variant: 'success' | 'danger' | 'neutral'; icon: typeof Smile }
> = {
  positive: { variant: 'success', icon: Smile },
  negative: { variant: 'danger', icon: Frown },
  neutral: { variant: 'neutral', icon: Meh },
};

export const SignalBadge = ({ signal, large = false }: { signal: Signal; large?: boolean }) => {
  const { t } = useTranslation();
  const { variant, icon: Icon } = SIGNAL_BADGE[signal];
  return (
    <Badge variant={variant} className={large ? 'text-sm' : ''}>
      <Icon className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
      {t(`prediction.signal.${signal}`)}
    </Badge>
  );
};

export const SentimentBadge = ({
  label,
  probability = null,
  large = false,
}: {
  label: SentimentLabel;
  /** FinBERT's probability for this label, shown next to it when FinBERT scored it */
  probability?: number | null;
  large?: boolean;
}) => {
  const { t } = useTranslation();
  const { variant, icon: Icon } = SENTIMENT_BADGE[label];
  const name = t(`sentiment.label.${label}`);
  return (
    <Badge variant={variant} className={large ? 'text-sm' : ''}>
      <Icon className="h-4 w-4" aria-hidden="true" />
      {probability == null ? (
        name
      ) : (
        <span className="tabular-nums">
          {t('sentiment.labelWithProbability', { label: name, pct: formatPct(probability) })}
        </span>
      )}
    </Badge>
  );
};

/**
 * Confidence next to every forecast (Design.md §6.4, §17): level and percentage, in the
 * warning treatment with an icon when the forecast is low-confidence.
 */
export const ConfidencePill = ({
  value,
  threshold,
  low,
}: {
  value: number;
  threshold: number;
  low: boolean;
}) => {
  const { t } = useTranslation();
  const level = confidenceLevel(value, threshold);
  return (
    <Badge variant={low ? 'warning' : 'neutral'}>
      {low && <AlertTriangle className="h-4 w-4" aria-hidden="true" />}
      <span>
        {t(low ? 'prediction.lowConfidenceShort' : `prediction.level.${level}`)} ·{' '}
        <Figure>{formatPct(value)}</Figure>
      </span>
    </Badge>
  );
};
