import { forwardRef, useId, type ReactNode, type SelectHTMLAttributes } from 'react';

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
      <div className="flex w-full flex-col space-y-1.5">
        <label
          htmlFor={selectId}
          className={hideLabel ? 'sr-only' : 'text-sm font-medium text-gray-700'}
        >
          {label}
        </label>
        <select
          id={selectId}
          ref={ref}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          className={`flex h-10 w-full rounded-md border bg-white px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 ${
            error ? 'border-red-500 focus:ring-red-500' : 'border-gray-300'
          } ${className}`}
          {...props}
        >
          {children}
        </select>
        {error && (
          <span id={errorId} className="mt-1 text-xs text-red-600">
            {error}
          </span>
        )}
      </div>
    );
  },
);

Select.displayName = 'Select';
