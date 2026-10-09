import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, type Page } from '@playwright/test';

// Labels come from the real locale files, so the tests follow the copy instead of hard-coding it
const HERE = dirname(fileURLToPath(import.meta.url));
const LOCALES = join(HERE, '..', '..', '..', 'packages', 'i18n', 'src', 'locales');
const load = (lang: 'en' | 'ur') =>
  JSON.parse(readFileSync(join(LOCALES, `${lang}.json`), 'utf-8')) as Record<string, unknown>;
const messages = { en: load('en'), ur: load('ur') };

export const t = (lang: 'en' | 'ur', key: string): string => {
  const value = key
    .split('.')
    .reduce<unknown>((node, part) => (node as Record<string, unknown>)?.[part], messages[lang]);
  if (typeof value !== 'string') throw new Error(`Missing ${lang} label: ${key}`);
  return value;
};

export const PASSWORD = 'e2e-password-123';

const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** A form field by its exact label; required fields add an asterisk to the label text. */
export const field = (page: Page, label: string) =>
  page.getByLabel(new RegExp(`^${escapeRegExp(label)}\\s*\\*?$`));

/** Every E2E account uses this prefix; global teardown deletes them all (tests/testdb.py). */
export const newEmail = () =>
  `e2e_${Date.now()}_${Math.random().toString(36).slice(2, 8)}@example.com`;

export const register = async (page: Page, lang: 'en' | 'ur', email: string) => {
  await page.goto('/register');
  await field(page, t(lang, 'auth.fields.fullName')).fill('E2E Tester');
  await field(page, t(lang, 'auth.fields.email')).fill(email);
  await field(page, t(lang, 'auth.fields.password')).fill(PASSWORD);
  await field(page, t(lang, 'auth.fields.confirmPassword')).fill(PASSWORD);
  await page.getByRole('button', { name: t(lang, 'auth.register.submit') }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
};

export const login = async (page: Page, email: string) => {
  await page.goto('/login');
  await field(page, t('en', 'auth.fields.email')).fill(email);
  await field(page, t('en', 'auth.fields.password')).fill(PASSWORD);
  await page.getByRole('button', { name: t('en', 'auth.login.submit') }).click();
};

/** The questionnaire's answer cards (choice buttons). */
export const choices = (page: Page) => page.locator('main button[aria-pressed]');
export const progress = (page: Page) => page.getByRole('progressbar');
