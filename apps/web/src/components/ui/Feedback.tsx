import type { ComponentType, ReactNode } from 'react';
import { AlertTriangle, Info, RefreshCw } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import { Button } from './Button';

/** Skeleton placeholder shaped like the content it stands for (Design.md §12.1). */
export const Skeleton = ({ className = '' }: { className?: string }) => (
  <div className={`iq-shimmer rounded-control bg-sunken ${className}`} aria-hidden="true" />
);

/** Inline, section-scoped error with a retry action (Design.md §12.3). */
export const ErrorState = ({ message, onRetry }: { message: string; onRetry?: () => void }) => {
  const { t } = useTranslation();
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-4 rounded-card border border-danger bg-danger-tint p-6 text-center"
    >
      <AlertTriangle className="h-6 w-6 text-danger" aria-hidden="true" />
      <p className="text-sm text-ink">{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          {t('common.retry')}
        </Button>
      )}
    </div>
  );
};

/** A designed empty state: why it is empty and what to do next (Design.md §12.2). */
export const EmptyState = ({
  icon: Icon,
  title,
  children,
  action,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) => (
  <div className="flex flex-col items-center gap-4 px-4 py-8 text-center">
    <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-tint text-primary">
      <Icon className="h-6 w-6" />
    </span>
    <div className="max-w-md space-y-2">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      {children && <div className="text-sm text-muted">{children}</div>}
    </div>
    {action}
  </div>
);

/** Neutral explanatory message, e.g. an "insufficient data" note. */
export const Notice = ({
  children,
  tone = 'neutral',
}: {
  children: ReactNode;
  tone?: 'neutral' | 'warning';
}) => (
  <div
    className={`flex items-start gap-4 rounded-control border p-4 text-sm text-ink ${
      tone === 'warning' ? 'border-warning bg-warning-tint' : 'border-line bg-sunken'
    }`}
  >
    {tone === 'warning' ? (
      <AlertTriangle className="mt-2 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
    ) : (
      <Info className="mt-2 h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
    )}
    <div className="min-w-0">{children}</div>
  </div>
);

/** Persistent advisory disclaimer (PRD.md §8.5, Design.md §6.6). */
export const DisclaimerBanner = () => {
  const { t } = useTranslation();
  return (
    <div className="rounded-control border border-line bg-sunken px-4 py-4 text-center text-sm text-muted">
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
