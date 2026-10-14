import { forwardRef, useId, type InputHTMLAttributes } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  /** Keeps the label for screen readers only, e.g. in repeated rows under a visible one */
  hideLabel?: boolean;
}

/** The look shared by text inputs, selects and the chat box. */
export const fieldClasses = (invalid: boolean) =>
  `w-full rounded-control border bg-surface px-4 text-sm text-ink placeholder:text-muted disabled:cursor-not-allowed disabled:bg-sunken disabled:text-muted ${
    invalid ? 'border-danger' : 'border-line-strong'
  }`;

// Label above the input (never placeholder-as-label), required fields marked with an
// asterisk, and the inline error linked to the input for screen readers (Design.md §13).
export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hideLabel = false, className = '', id, required, ...props }, ref) => {
    const generatedId = useId();
    const inputId = id || generatedId;
    const errorId = `${inputId}-error`;

    return (
      <div className="flex w-full flex-col gap-2">
        <label htmlFor={inputId} className={hideLabel ? 'sr-only' : 'text-sm font-medium text-ink'}>
          {label}
          {required && (
            <span className="ms-2 text-danger" aria-hidden="true">
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
          className={`h-10 ${fieldClasses(Boolean(error))} ${className}`}
          {...props}
        />
        {error && (
          <span id={errorId} className="text-xs text-danger">
            {error}
          </span>
        )}
      </div>
    );
  },
);

Input.displayName = 'Input';
