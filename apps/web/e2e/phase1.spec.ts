// Phase 1 smoke tests (Phases.md exit criteria): auth, onboarding with resume, persistence, Urdu.
import { expect, test } from '@playwright/test';
import { choices, login, newEmail, progress, register, t } from './helpers.ts';

test('register → answer part → reload resumes → finish → dashboard → logout → login', async ({
  page,
}) => {
  const email = newEmail();
  await register(page, 'en', email);
  await expect(page.getByText(t('en', 'disclaimer'))).toBeVisible(); // PRD §8.5 at onboarding

  // Answer 3 of the questions (first option = highest risk capacity)
  await expect(progress(page)).toHaveAttribute('aria-valuenow', '1');
  for (const next of ['2', '3', '4']) {
    await choices(page).first().click();
    await expect(progress(page)).toHaveAttribute('aria-valuenow', next);
  }

  // Closing the page mid-way and coming back resumes at the same question (FR6)
  await page.reload();
  await expect(progress(page)).toHaveAttribute('aria-valuenow', '4');
  await expect(page.getByText(t('en', 'onboarding.resumed'))).toBeVisible();

  // Finish: all-first answers score 21 with no safety caps → Aggressive
  const total = Number(await progress(page).getAttribute('aria-valuemax'));
  for (let step = 4; step <= total; step += 1) {
    await choices(page).first().click();
  }
  const aggressive = t('en', 'risk.aggressive');
  await expect(page.getByRole('heading', { name: new RegExp(aggressive) })).toBeVisible();
  await page.getByRole('button', { name: t('en', 'onboarding.result.cta') }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText(aggressive, { exact: true })).toBeVisible();
  await expect(page.getByText(t('en', 'disclaimer'))).toBeVisible();

  // Logout, then the profile is still there after logging back in
  await page.getByRole('button', { name: t('en', 'common.logout') }).click();
  await expect(page).toHaveURL(/\/login$/);
  await login(page, email);
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText(aggressive, { exact: true })).toBeVisible();
});

test('Urdu: right-to-left layout, Urdu text, and logout from onboarding', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: t('en', 'common.switchLanguageLabel') }).click();

  const html = page.locator('html');
  await expect(html).toHaveAttribute('dir', 'rtl');
  await expect(html).toHaveAttribute('lang', 'ur');
  await expect(page.getByRole('button', { name: t('ur', 'auth.login.submit') })).toBeVisible();

  // The choice persists through registration into onboarding, still right-to-left
  await page.getByRole('link', { name: t('ur', 'auth.login.signUp') }).click();
  await register(page, 'ur', newEmail());
  await expect(html).toHaveAttribute('dir', 'rtl');
  await expect(
    page.getByRole('heading', { name: t('ur', 'onboarding.questions.age_band.title') }),
  ).toBeVisible();
  await expect(page.getByText(t('ur', 'disclaimer'))).toBeVisible();

  await page.getByRole('button', { name: t('ur', 'common.logout') }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(html).toHaveAttribute('dir', 'rtl');
  await expect(page.getByRole('button', { name: t('ur', 'auth.login.submit') })).toBeVisible();
});
