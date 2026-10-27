import { useId } from 'react';

/**
 * An on/off setting: the label and a one-line explanation beside a switch (role="switch", so
 * screen readers say "on" or "off"). The knob moves to the end side, so it follows RTL.
 */
export const Switch = ({
  label,
  help,
  checked,
  onChange,
  disabled = false,
}: {
  label: string;
  help?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) => {
  const id = useId();
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <div className="min-w-0 space-y-2">
        <label htmlFor={id} className="text-sm font-medium text-ink">
          {label}
        </label>
        {help && (
          <p id={`${id}-help`} className="text-sm text-muted">
            {help}
          </p>
        )}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={help ? `${id}-help` : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-10 shrink-0 items-center rounded-full border transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${
          checked ? 'border-primary bg-primary' : 'border-line-strong bg-sunken'
        }`}
      >
        <span
          aria-hidden="true"
          className={`inline-block h-4 w-4 rounded-full shadow-e1 transition-transform duration-150 ${
            checked
              ? 'translate-x-5 bg-inverse rtl:-translate-x-5'
              : 'translate-x-1 bg-muted rtl:-translate-x-1'
          }`}
        />
      </button>
    </div>
  );
};
