// Number/date formatting. Figures always use Western digits and render LTR,
// even in the Urdu (RTL) layout (Design.md §23).

const number = (digits: number) =>
  new Intl.NumberFormat('en-PK', { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const formatPrice = (value: number | null | undefined, currency = 'Rs.'): string =>
  value == null ? '—' : `${currency} ${number(2).format(value)}`;

/** Money from the API arrives as a decimal string; it is only formatted, never recalculated. */
export const formatMoney = (value: string | null | undefined): string =>
  value == null ? '—' : formatPrice(Number(value));

/** A decimal string from the API with a + sign in front of a positive value. */
export const withSign = (value: string): string =>
  !value.startsWith('-') && Number(value) !== 0 ? `+${value}` : value;

/**
 * A percentage string from the API, with a + sign on request. Wrapped in a left-to-right
 * isolate so the % sign stays after the number inside Urdu (right-to-left) sentences.
 */
export const formatPctString = (value: string | null | undefined, signed = false): string =>
  value == null ? '—' : `⁦${signed ? withSign(value) : value}%⁩`;

/** Percentage points with a sign, kept left-to-right inside Urdu sentences. */
export const formatPp = (value: string): string => `⁦${withSign(value)}⁩`;

export const formatSignedPct = (value: number | null | undefined, digits = 2): string => {
  if (value == null) return '—';
  const arrow = value > 0 ? '▲' : value < 0 ? '▼' : '';
  return `${arrow}${value > 0 ? '+' : ''}${number(digits).format(value)}%`;
};

export const formatPct = (fraction: number, digits = 0): string =>
  `${number(digits).format(fraction * 100)}%`;

export const formatCompact = (value: number | null | undefined): string =>
  value == null
    ? '—'
    : new Intl.NumberFormat('en-PK', { notation: 'compact', maximumFractionDigits: 2 }).format(
        value,
      );

/** PSX time: dates always show in Pakistan time, whatever the viewer's device timezone is. */
export const DISPLAY_TIME_ZONE = 'Asia/Karachi';

export const formatDate = (iso: string, language: string): string =>
  new Date(iso).toLocaleDateString(language.startsWith('ur') ? 'ur-PK' : 'en-PK', {
    timeZone: DISPLAY_TIME_ZONE,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
