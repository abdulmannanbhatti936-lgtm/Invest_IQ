import type { ReactNode } from 'react';

type BadgeVariant = 'success' | 'danger' | 'warning' | 'neutral' | 'primary';

const VARIANTS: Record<BadgeVariant, string> = {
  success: 'bg-success-tint text-success',
  danger: 'bg-danger-tint text-danger',
  warning: 'bg-warning-tint text-warning',
  neutral: 'bg-sunken text-ink border border-line',
  primary: 'bg-primary-tint text-primary',
};

/** Pill badge (Design.md §17); the icon, when there is one, carries the meaning with the text. */
export const Badge = ({
  children,
  variant = 'neutral',
  className = '',
}: {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}) => (
  <span
    className={`inline-flex min-h-6 items-center gap-2 rounded-full px-2 text-xs font-semibold whitespace-nowrap ${VARIANTS[variant]} ${className}`}
  >
    {children}
  </span>
);
