// Number/date formatting. Figures always use Western digits and render LTR,
// even in the Urdu (RTL) layout (Design.md §23).

const number = (digits: number) =>
  new Intl.NumberFormat('en-PK', { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const formatPrice = (value: number | null | undefined, currency = 'Rs.'): string =>
  value == null ? '—' : `${currency} ${number(2).format(value)}`;

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

export const formatDate = (iso: string, language: string): string =>
  new Date(iso).toLocaleDateString(language.startsWith('ur') ? 'ur-PK' : 'en-PK', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
