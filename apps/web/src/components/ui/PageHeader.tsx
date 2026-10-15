import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

/** Page title, one-line explanation and the way back (Design.md §14.3). */
export const PageHeader = ({
  title,
  subtitle,
  back,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  back?: { to: string; label: string };
  actions?: ReactNode;
}) => (
  <header className="mb-6 space-y-2">
    {back && (
      <Link
        to={back.to}
        className="inline-flex items-center gap-2 text-sm font-medium text-muted hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
        {back.label}
      </Link>
    )}
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="max-w-3xl text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  </header>
);
