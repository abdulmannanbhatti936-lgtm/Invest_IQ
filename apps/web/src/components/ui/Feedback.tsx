import type { ReactNode } from 'react';
import { AlertTriangle, Info, RefreshCw } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import { Button } from './Button';

/** Skeleton placeholder block (Design.md §12.1). */
export const Skeleton = ({ className = '' }: { className?: string }) => (
  <div className={`animate-pulse rounded-md bg-gray-200 ${className}`} aria-hidden="true" />
);

/** Inline, section-scoped error with a retry action (Design.md §12.3). */
export const ErrorState = ({ message, onRetry }: { message: string; onRetry?: () => void }) => {
  const { t } = useTranslation();
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 rounded-lg border border-red-100 bg-red-50 p-6 text-center"
    >
      <AlertTriangle className="h-6 w-6 text-red-500" />
      <p className="text-sm text-red-700">{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          <RefreshCw className="h-4 w-4 me-2" />
          {t('common.retry')}
        </Button>
      )}
    </div>
  );
};

/** Neutral explanatory message, e.g. an empty or "insufficient data" state. */
export const Notice = ({
  children,
  tone = 'neutral',
}: {
  children: ReactNode;
  tone?: 'neutral' | 'warning';
}) => (
  <div
    className={`flex items-start gap-3 rounded-lg border p-4 text-sm ${
      tone === 'warning'
        ? 'border-amber-200 bg-amber-50 text-amber-900'
        : 'border-gray-200 bg-gray-50 text-gray-700'
    }`}
  >
    {tone === 'warning' ? (
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
    ) : (
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-gray-500" />
    )}
    <div>{children}</div>
  </div>
);

/** Persistent advisory disclaimer (PRD.md §8.5, Design.md §6.6). */
export const DisclaimerBanner = () => {
  const { t } = useTranslation();
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-100 px-4 py-3 text-center text-sm text-gray-700">
      {t('disclaimer')}
    </div>
  );
};

/** A financial figure that stays left-to-right inside RTL text (Design.md §23). */
export const Figure = ({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) => (
  <bdi dir="ltr" className={`tabular-nums ${className}`}>
    {children}
  </bdi>
);
