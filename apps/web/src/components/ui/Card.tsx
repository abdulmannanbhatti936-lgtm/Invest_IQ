import type { HTMLAttributes, KeyboardEvent, ReactNode } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  /** `warning`: the tinted treatment for low-confidence AI output (Design.md §6.4) */
  tone?: 'default' | 'warning';
  /** Inner padding; `none` for cards whose rows run edge to edge */
  padding?: 'none' | 'md';
}

const TONES = {
  default: 'border border-line bg-surface',
  warning: 'border-2 border-warning bg-warning-tint',
};

/** The one card used everywhere (Design.md §6.2). Clickable cards lift slightly on hover. */
export const Card = ({
  children,
  className = '',
  tone = 'default',
  padding = 'md',
  onClick,
  ...props
}: CardProps) => {
  // Clickable cards behave like buttons for keyboard and screen-reader users
  const interactive = onClick
    ? {
        role: 'button',
        tabIndex: 0,
        onKeyDown: (e: KeyboardEvent<HTMLDivElement>) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            e.currentTarget.click();
          }
        },
      }
    : {};
  return (
    <div
      className={`${TONES[tone]} rounded-card shadow-e1 ${padding === 'md' ? 'p-4 sm:p-6' : ''} ${
        onClick
          ? 'cursor-pointer transition-[transform,box-shadow] duration-150 ease-enter hover:-translate-y-0.5 hover:shadow-e2'
          : ''
      } ${className}`}
      onClick={onClick}
      {...interactive}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader = ({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) => <div className={`mb-4 ${className}`}>{children}</div>;

export const CardTitle = ({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) => <h2 className={`text-lg font-semibold text-ink ${className}`}>{children}</h2>;

export const CardContent = ({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) => <div className={className}>{children}</div>;
