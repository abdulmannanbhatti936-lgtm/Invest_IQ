// Builds the theme stylesheet from token data passed in, so this file has no imports and
// vite.config.ts (checked as a Node ESM file) can load it directly.

const kebab = (name: string) => name.replace(/[A-Z0-9]/g, (c) => `-${c.toLowerCase()}`);

/** `--iq-<token>` custom properties: colours, then elevation levels and motion values. */
export const cssVariables = (
  colors: object,
  elevation: Record<string | number, string>,
  motion: { duration: Record<string, string>; easing: Record<string, string> },
): Record<string, string> => ({
  ...Object.fromEntries(Object.entries(colors).map(([k, v]) => [`--iq-${kebab(k)}`, v])),
  ...Object.fromEntries(Object.entries(elevation).map(([k, v]) => [`--iq-elevation-${k}`, v])),
  ...Object.fromEntries(
    Object.entries(motion.duration).map(([k, v]) => [`--iq-duration-${kebab(k)}`, v]),
  ),
  ...Object.fromEntries(
    Object.entries(motion.easing).map(([k, v]) => [`--iq-ease-${kebab(k)}`, v]),
  ),
});

/** Dark on :root (the default) and under [data-theme='dark'], light under [data-theme='light']. */
export const themeCss = (dark: Record<string, string>, light: Record<string, string>): string => {
  const block = (selector: string, scheme: string, vars: Record<string, string>) =>
    `${selector}{color-scheme:${scheme};${Object.entries(vars)
      .map(([k, v]) => `${k}:${v}`)
      .join(';')}}`;
  return [
    block(`:root,:root[data-theme='dark']`, 'dark', dark),
    block(`:root[data-theme='light']`, 'light', light),
  ].join('\n');
};
