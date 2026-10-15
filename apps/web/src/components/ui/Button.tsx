import type { ButtonHTMLAttributes } from 'react';
import { Loader2 } from 'lucide-react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'destructive';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: 'md' | 'lg';
  isLoading?: boolean;
}

/** Shared by <Button> and links styled as buttons, so both look identical (Design.md §6.1). */
export const buttonClasses = (variant: Variant = 'primary', size: 'md' | 'lg' = 'md') =>
  [
    'inline-flex items-center justify-center gap-2 rounded-control font-semibold whitespace-nowrap',
    'transition-[background-color,border-color,color,transform] duration-150 ease-enter',
    'disabled:cursor-not-allowed disabled:border-line disabled:bg-sunken disabled:text-muted disabled:shadow-none',
    size === 'lg' ? 'min-h-12 px-6 text-base' : 'min-h-10 px-4 text-sm',
    {
      primary: 'bg-primary text-inverse shadow-e1 hover:bg-primary-hover active:translate-y-px',
      secondary: 'border border-line-strong bg-transparent text-ink hover:bg-sunken',
      ghost: 'bg-transparent text-ink hover:bg-sunken',
      destructive: 'border border-danger bg-transparent text-danger hover:bg-danger-tint',
    }[variant],
  ].join(' ');

export const Button = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  className = '',
  disabled,
  ...props
}: ButtonProps) => (
  <button
    className={`${buttonClasses(variant, size)} ${className}`}
    disabled={isLoading || disabled}
    aria-busy={isLoading || undefined}
    {...props}
  >
    {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
    {children}
  </button>
);
