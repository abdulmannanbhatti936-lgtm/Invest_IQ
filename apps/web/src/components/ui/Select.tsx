import { forwardRef, useId, type ReactNode, type SelectHTMLAttributes } from 'react';
import { fieldClasses } from './Input';

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  error?: string;
  /** Keeps the label for screen readers only, e.g. inside a table row with its own heading */
  hideLabel?: boolean;
  children: ReactNode;
}

// Same rules as Input: label above, inline error linked for screen readers (Design.md §13).
export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, hideLabel = false, className = '', id, children, ...props }, ref) => {
    const generatedId = useId();
    const selectId = id || generatedId;
    const errorId = `${selectId}-error`;

    return (
      <div className="flex w-full flex-col gap-2">
        <label
          htmlFor={selectId}
          className={hideLabel ? 'sr-only' : 'text-sm font-medium text-ink'}
        >
          {label}
        </label>
        <select
          id={selectId}
          ref={ref}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          className={`h-10 ${fieldClasses(Boolean(error))} ${className}`}
          {...props}
        >
          {children}
        </select>
        {error && (
          <span id={errorId} className="text-xs text-danger">
            {error}
          </span>
        )}
      </div>
    );
  },
);

Select.displayName = 'Select';
