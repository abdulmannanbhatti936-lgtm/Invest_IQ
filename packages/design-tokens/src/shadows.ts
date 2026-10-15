// Design.md §21. Dark mode uses lower-opacity shadows plus a lighter hairline, because shadows
// alone read poorly on dark backgrounds.
export const elevation = {
  light: {
    0: 'none',
    1: '0 1px 2px rgba(0,0,0,0.06)',
    2: '0 4px 8px rgba(0,0,0,0.08)',
    3: '0 8px 16px rgba(0,0,0,0.12)',
  },
  dark: {
    0: 'none',
    1: '0 1px 2px rgba(0,0,0,0.30), 0 0 0 1px rgba(255,255,255,0.03)',
    2: '0 4px 8px rgba(0,0,0,0.35), 0 0 0 1px rgba(255,255,255,0.05)',
    3: '0 8px 16px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.07)',
  },
};
