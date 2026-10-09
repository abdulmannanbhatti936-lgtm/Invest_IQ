// Fails (exit 1) when en.json and ur.json drift apart: missing or extra keys, empty values,
// non-string values, or different {{placeholders}}. Run: npm run check -w @investiq/i18n
// Urdu strings identical to English are only reported as warnings (brand names like
// "InvestIQ" or a dash are legitimately the same).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const localesDir = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'locales');
const load = (lang) => JSON.parse(readFileSync(join(localesDir, `${lang}.json`), 'utf8'));

const flatten = (node, prefix = '') =>
  Object.entries(node).flatMap(([key, value]) =>
    value !== null && typeof value === 'object' && !Array.isArray(value)
      ? flatten(value, `${prefix}${key}.`)
      : [[`${prefix}${key}`, value]],
  );

const placeholders = (text) =>
  [...String(text).matchAll(/\{\{\s*([\w.]+)\s*(?:,[^}]*)?\}\}/g)].map((m) => m[1]).sort();

export const checkParity = (en, ur) => {
  const errors = [];
  const warnings = [];
  const enMap = new Map(flatten(en));
  const urMap = new Map(flatten(ur));

  for (const key of enMap.keys()) if (!urMap.has(key)) errors.push(`missing in ur.json: ${key}`);
  for (const key of urMap.keys())
    if (!enMap.has(key)) errors.push(`extra in ur.json (not in en.json): ${key}`);

  for (const [lang, map] of [
    ['en', enMap],
    ['ur', urMap],
  ]) {
    for (const [key, value] of map) {
      if (typeof value !== 'string')
        errors.push(`${lang}.json ${key}: value is ${typeof value}, expected text`);
      else if (value.trim() === '') errors.push(`${lang}.json ${key}: empty value`);
    }
  }

  for (const [key, enValue] of enMap) {
    if (!urMap.has(key) || typeof enValue !== 'string') continue;
    const urValue = urMap.get(key);
    const a = placeholders(enValue).join(',');
    const b = placeholders(urValue).join(',');
    if (a !== b) errors.push(`placeholders differ for ${key}: en {${a}} vs ur {${b}}`);
    if (enValue === urValue && /[A-Za-z]{3,}/.test(enValue))
      warnings.push(`ur.json ${key} is identical to English: "${enValue}"`);
  }
  return { errors, warnings, keyCount: enMap.size };
};

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const { errors, warnings, keyCount } = checkParity(load('en'), load('ur'));
  warnings.forEach((w) => console.warn(`warning: ${w}`));
  if (errors.length) {
    errors.forEach((e) => console.error(`error: ${e}`));
    console.error(`\ni18n parity check FAILED: ${errors.length} problem(s)`);
    process.exit(1);
  }
  console.log(
    `i18n parity check passed: ${keyCount} keys in en.json and ur.json, placeholders match`,
  );
}
