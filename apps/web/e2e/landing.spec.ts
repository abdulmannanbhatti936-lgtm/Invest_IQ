// UI round (2026-10-15): the public landing page, the route rule for "/", the reduced-motion
// fallback, and the RTL and chat-counter fixes.
import { expect, test } from '@playwright/test';
import { choices, newEmail, progress, register, t } from './helpers.ts';

const finishOnboarding = async (page: import('@playwright/test').Page) => {
  const total = Number(await progress(page).getAttribute('aria-valuemax'));
  for (let step = 1; step <= total; step += 1) {
    await choices(page).first().click();
  }
  await page.getByRole('button', { name: t('en', 'onboarding.result.cta') }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
};

test('logged out, "/" is the landing page and its calls to action open sign-up and log-in', async ({
  page,
}) => {
  await page.goto('/');
  await expect(
    page.getByRole('heading', { level: 1, name: t('en', 'landing.hero.title') }),
  ).toBeVisible();
  // Every section is there, with its source labels
  for (const key of [
    'landing.zoom.titleEnd',
    'landing.risk.title',
    'landing.costs.title',
    'landing.how.title',
    'landing.honesty.title',
  ]) {
    await expect(page.getByText(t('en', key), { exact: false }).first()).toBeAttached();
  }
  await expect(page.getByText(t('en', 'disclaimer')).first()).toBeAttached();

  await page
    .getByRole('link', { name: t('en', 'landing.hero.start') })
    .first()
    .click();
  await expect(page).toHaveURL(/\/register$/);

  await page.goto('/');
  await page.getByRole('link', { name: t('en', 'landing.hero.login'), exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test('the landing page switches to Urdu, right to left', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: t('en', 'common.switchLanguageLabel') }).click();
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(
    page.getByRole('heading', { level: 1, name: t('ur', 'landing.hero.title') }),
  ).toBeVisible();
  await expect(
    page.getByRole('link', { name: t('ur', 'landing.hero.start') }).first(),
  ).toBeVisible();
});

test('under reduced motion the bloom is the static image, never the 3D canvas', async ({
  browser,
}) => {
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto('/');
  await expect(page.locator('img[src*="/landing/bloom-"]')).toBeVisible();
  await expect(page.locator('canvas')).toHaveCount(0);
  await context.close();
});

test('logged in, "/" goes on to the dashboard', async ({ page }) => {
  await register(page, 'en', newEmail());
  // Profile not finished yet: onboarding first
  await page.goto('/');
  await expect(page).toHaveURL(/\/onboarding$/);
  await finishOnboarding(page);
  await page.goto('/');
  await expect(page).toHaveURL(/\/dashboard$/);
});

test('Urdu at 1024 px: English company names read left to right and are cut at their end', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 800 });
  await register(page, 'en', newEmail());
  await finishOnboarding(page);
  await page.getByRole('button', { name: t('en', 'common.switchLanguageLabel') }).click();
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await page.goto('/stocks');

  const names = page.locator('main .iq-truncate-end');
  await expect(names.first()).toBeVisible();
  const count = await names.count();
  expect(count).toBeGreaterThan(0);
  // Every tenth name, to keep the run short; they all share the one component
  for (let i = 0; i < count; i += 10) {
    const name = names.nth(i);
    // Left to right inside the Urdu page: an ellipsis can only replace the end of the name
    await expect(name).toHaveCSS('direction', 'ltr');
    await expect(name).toHaveCSS('text-overflow', 'ellipsis');
    // The full name stays available on hover or long-press
    await expect(name).toHaveAttribute('title', /\S/);
  }
});

test('Urdu chat: the character counter reads "0 / 1000", not "1000 / 0"', async ({ page }) => {
  await register(page, 'en', newEmail());
  await finishOnboarding(page);
  await page.goto('/chat');
  await page
    .getByRole('main')
    .getByRole('button', { name: t('en', 'common.switchLanguageLabel') })
    .click();
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  // The counter is wrapped in a left-to-right isolate (U+2066 ... U+2069)
  await expect(page.getByText('⁦0 / 1000⁩', { exact: true })).toBeVisible();
});
