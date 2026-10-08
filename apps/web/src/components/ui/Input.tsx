import { forwardRef, useId, type InputHTMLAttributes } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

// Label above the input (never placeholder-as-label), required fields marked with an
// asterisk, and the inline error linked to the input for screen readers (Design.md §13).
export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = '', id, required, ...props }, ref) => {
    const generatedId = useId();
    const inputId = id || generatedId;
    const errorId = `${inputId}-error`;

    return (
      <div className="flex w-full flex-col space-y-1.5">
        <label htmlFor={inputId} className="text-sm font-medium text-gray-700">
          {label}
          {required && (
            <span className="ms-0.5 text-red-600" aria-hidden="true">
              *
            </span>
          )}
        </label>
        <input
          id={inputId}
          ref={ref}
          aria-required={required || undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          className={`flex h-10 w-full rounded-md border bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 ${
            error ? 'border-red-500 focus:ring-red-500' : 'border-gray-300'
          } ${className}`}
          {...props}
        />
        {error && (
          <span id={errorId} className="mt-1 text-xs text-red-600">
            {error}
          </span>
        )}
      </div>
    );
  },
);

Input.displayName = 'Input';
