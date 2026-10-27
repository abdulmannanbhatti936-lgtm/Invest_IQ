// Phase 7 smoke test: the bell, the opt-in, a real agent run on the MOCK market (invented stocks,
// never PSX data; tests/e2e_market.py), the list, mark as read, settings and the Urdu layout.
import { expect, test, type Page } from '@playwright/test';
import { choices, field, newEmail, progress, register, t } from './helpers.ts';
import { runAgentFor } from './testDb.ts';

const onboardAndGenerate = async (page: Page, email: string) => {
  await register(page, 'en', email);
  const total = Number(await progress(page).getAttribute('aria-valuemax'));
  for (let step = 1; step <= total; step += 1) {
    await choices(page).first().click();
  }
  await page.getByRole('button', { name: t('en', 'onboarding.result.cta') }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto('/portfolio');
  await field(page, t('en', 'portfolio.form.capital')).fill('100000');
  await page.getByRole('button', { name: t('en', 'portfolio.form.submit'), exact: true }).click();
  await expect(page.getByText('MOCKE2EA', { exact: true }).first()).toBeVisible({
    timeout: 30_000,
  });
};

const bell = (page: Page) =>
  page.getByRole('button', { name: new RegExp(`^${t('en', 'notifications.bell.label')}`) });

const typeSwitch = (page: Page, type: string) =>
  page.getByRole('switch', { name: t('en', `notifications.settings.types.${type}.label`) });

test('opt in from the bell → agent run → list, mark as read, settings', async ({ page }) => {
  test.setTimeout(150_000);
  const email = newEmail();
  await onboardAndGenerate(page, email);

  // Every type starts off: the bell offers one button that turns them all on
  await bell(page).click();
  const panel = page.getByRole('dialog', { name: t('en', 'notifications.title') });
  await expect(panel.getByText(t('en', 'notifications.bell.optIn.title'))).toBeVisible();
  await expect(
    panel.getByRole('link', { name: t('en', 'notifications.bell.optIn.settings') }),
  ).toBeVisible();
  await panel.getByRole('button', { name: t('en', 'notifications.bell.optIn.button') }).click();
  await expect(panel.getByText(t('en', 'notifications.bell.empty'))).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(panel).toBeHidden();

  // The real agent, twice: the second run adds nothing
  expect(runAgentFor(email)).toMatch(/^E2E agent run: completed: [1-9]\d* new/m);
  expect(runAgentFor(email)).toMatch(/^E2E agent run: completed: 0 new/m);

  // The bell shows the unread count after a refresh (it also polls every minute)
  await page.reload();
  await expect(bell(page)).toHaveAccessibleName(/unread/);
  await bell(page).click();
  await expect(panel.getByText(/Consider selling MOCKE2E/).first()).toBeVisible();
  await panel.getByRole('link', { name: t('en', 'notifications.bell.seeAll') }).click();
  await expect(page).toHaveURL(/\/notifications$/);

  // The full card: action, low-confidence label, the sale figures, advisory line and the link
  const card = page.locator('[data-notification-id]').filter({ hasText: 'Consider selling' });
  await expect(card).toHaveCount(1);
  await expect(card.getByText(t('en', 'notifications.strength.watch'))).toBeVisible();
  await expect(card.getByText(t('en', 'prediction.lowConfidenceShort'))).toBeVisible();
  await expect(card.getByText(t('en', 'portfolio.holding.sellCharges'))).toBeVisible();
  await expect(card.getByText(t('en', 'portfolio.holding.cgt'))).toBeVisible();
  await expect(card.getByText(/Rs\. [\d,]+\.\d{2}/).first()).toBeVisible();
  await expect(card.getByText(t('en', 'notifications.advisory'))).toBeVisible();
  await expect(
    card.getByRole('link', { name: t('en', 'notifications.seeReason') }),
  ).toHaveAttribute('href', /^\/stocks\/MOCKE2E[A-F]$/);

  // Grouped by type, then mark as read
  await page.getByRole('radio', { name: t('en', 'notifications.view.byType') }).click();
  await expect(
    page.getByRole('heading', { name: t('en', 'notifications.type.sell') }),
  ).toBeVisible();
  const markRead = card.getByRole('button', { name: t('en', 'notifications.markRead') });
  await markRead.click();
  await expect(markRead).toBeHidden();
  const markAll = page.getByRole('button', { name: t('en', 'notifications.markAllRead') });
  if (await markAll.isVisible()) await markAll.click();
  await expect(bell(page)).toHaveAccessibleName(t('en', 'notifications.bell.label'));

  // Settings: they persist; quiet hours need two different times; everything off
  await page.getByRole('link', { name: t('en', 'notifications.settingsLink') }).click();
  await expect(page).toHaveURL(/\/notifications\/settings$/);
  for (const type of ['roll', 'sell', 'buy']) {
    await expect(typeSwitch(page, type)).toHaveAttribute('aria-checked', 'true');
  }
  await typeSwitch(page, 'buy').click();
  await page.getByLabel(t('en', 'notifications.settings.sensitivity.strong_only')).check();
  await page.getByLabel(t('en', 'notifications.settings.capLabel')).selectOption('5');
  await page.getByRole('switch', { name: t('en', 'notifications.settings.quietToggle') }).click();
  await field(page, t('en', 'notifications.settings.quietStart')).fill('08:00');
  await field(page, t('en', 'notifications.settings.quietEnd')).fill('08:00');
  await expect(page.getByText(t('en', 'notifications.settings.quietSame'))).toBeVisible();
  const save = page.getByRole('button', { name: t('en', 'notifications.settings.save') });
  await expect(save).toBeDisabled();
  await field(page, t('en', 'notifications.settings.quietStart')).fill('22:30');
  await save.click();
  await expect(page.getByText(t('en', 'notifications.settings.saved'))).toBeVisible();

  await page.reload();
  await expect(typeSwitch(page, 'buy')).toHaveAttribute('aria-checked', 'false');
  await expect(
    page.getByLabel(t('en', 'notifications.settings.sensitivity.strong_only')),
  ).toBeChecked();
  await expect(page.getByLabel(t('en', 'notifications.settings.capLabel'))).toHaveValue('5');
  await expect(field(page, t('en', 'notifications.settings.quietStart'))).toHaveValue('22:30');
  // Without Firebase on this test server, browser notifications say so instead of failing
  await expect(page.getByText(t('en', 'notifications.settings.pushUnavailable'))).toBeVisible();

  await page.getByRole('button', { name: t('en', 'notifications.settings.offButton') }).click();
  await expect(page.getByText(t('en', 'notifications.settings.offDone'))).toBeVisible();
  for (const type of ['roll', 'sell', 'buy']) {
    await expect(typeSwitch(page, type)).toHaveAttribute('aria-checked', 'false');
  }
});

test('Urdu: the notification centre reads right to left', async ({ page }) => {
  test.setTimeout(150_000);
  const email = newEmail();
  await onboardAndGenerate(page, email);
  await page.getByRole('button', { name: t('en', 'common.switchLanguageLabel') }).click();
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');

  await page.goto('/notifications');
  await expect(page.getByRole('heading', { name: t('ur', 'notifications.title') })).toBeVisible();
  await expect(page.getByText(t('ur', 'notifications.empty.offTitle'))).toBeVisible();
  await page.getByRole('button', { name: t('ur', 'notifications.bell.optIn.button') }).click();
  await expect(page.getByText(t('ur', 'notifications.empty.title'))).toBeVisible();

  runAgentFor(email);
  await page.reload();
  const card = page.locator('[data-notification-id]').first();
  await expect(card.getByText(/MOCKE2E[A-F] کی فروخت پر غور کریں/)).toBeVisible();
  await expect(card.getByText(t('ur', 'notifications.advisory'))).toBeVisible();
  await expect(card.getByText(t('ur', 'portfolio.holding.sellCharges'))).toBeVisible();
  // Rupee figures stay left to right inside the Urdu card (Design.md §23)
  await expect(card.locator('bdi[dir="ltr"]').first()).toBeVisible();
});
