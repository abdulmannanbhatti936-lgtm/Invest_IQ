// Design.md §3. Urdu is Nastaleeq everywhere (team decision 2026-10-13); the display face is for
// the public landing page's Latin headings only (approved 2026-10-15).
export const typography = {
  fontFamily: {
    ui: "ui-sans-serif, system-ui, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    urdu: "'InvestIQ Urdu', 'Noto Naskh Arabic'",
    display: "'Bricolage Grotesque Variable'",
  },
  sizes: {
    xs: '0.75rem',
    sm: '0.875rem',
    base: '1rem',
    lg: '1.125rem',
    xl: '1.5rem',
    '2xl': '2rem',
    '3xl': '2.5rem',
  },
  /** Nastaleeq's tall letters need a 2.0 line height or dots and descenders are clipped */
  urduLineHeight: 2,
};
