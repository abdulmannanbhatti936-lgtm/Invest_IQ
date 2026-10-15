// Phase 8 smoke test: the chat flow against the MOCK LLM provider (services/api/integrations/
// llm/mock.py), which answers from the real grounding context on the MOCK market; no real model
// is ever called. The reply still goes through the real endpoint, figure check and source tags.
import { expect, test } from '@playwright/test';
import { choices, field, newEmail, progress, register, t } from './helpers.ts';

test('empty chat → starter question → grounded reply with its source → Roman Urdu → clear', async ({
  page,
}) => {
  test.setTimeout(120_000);

  await register(page, 'en', newEmail());
  const total = Number(await progress(page).getAttribute('aria-valuemax'));
  for (let step = 1; step <= total; step += 1) {
    await choices(page).first().click();
  }
  await page.getByRole('button', { name: t('en', 'onboarding.result.cta') }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // Chat is in the top navigation; with no history it shows the starter questions
  await page
    .getByRole('link', { name: t('en', 'nav.chat') })
    .first()
    .click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByText(t('en', 'chat.empty.title'))).toBeVisible();
  await expect(page.getByText(t('en', 'disclaimer'))).toBeVisible();

  // No portfolio yet: the reply says so and points to the Portfolio screen
  await page.getByRole('button', { name: t('en', 'chat.starters.portfolio') }).click();
  const log = page.getByRole('log');
  await expect(log.getByText(t('en', 'chat.starters.portfolio'))).toBeVisible();
  await expect(log.getByText(/MOCK reply: you do not have a portfolio yet/)).toBeVisible({
    timeout: 30_000,
  });

  // With a portfolio, the reply repeats its stored figures and is tagged with its source
  await page.goto('/portfolio');
  await field(page, t('en', 'portfolio.form.capital')).fill('100000');
  await page.getByRole('button', { name: t('en', 'portfolio.form.submit'), exact: true }).click();
  // The ticker appears in the allocation legend and in its holding row (UI round)
  await expect(page.getByText('MOCKE2EA', { exact: true }).first()).toBeVisible({
    timeout: 30_000,
  });
  await page.goto('/chat');
  const input = field(page, t('en', 'chat.inputLabel'));
  await input.fill('How much did my portfolio cost?');
  await input.press('Enter');
  await expect(
    log.getByText(/MOCK reply: your InvestIQ recommended portfolio would cost Rs\. [\d,]+\.\d{2}/),
  ).toBeVisible({
    timeout: 30_000,
  });
  await expect(log.getByText(/^From your portfolio generated /)).toBeVisible();

  // Roman Urdu is answered in Roman Urdu, with the Roman Urdu disclaimer under the reply
  await input.fill('mera portfolio kaisa hai?');
  await page.getByRole('button', { name: t('en', 'chat.send') }).click();
  await expect(log.getByText(t('en', 'chat.disclaimerRomanUrdu'))).toBeVisible({
    timeout: 30_000,
  });

  // A busy provider (MOCK 429, 3 s): a live countdown, the message kept in the box, then send again
  await input.fill('MOCK_BUSY');
  await input.press('Enter');
  const busy = new RegExp(
    t('en', 'chat.error.busyCountdown').replace('{{seconds}}', '\\d+').replace(/[.;]/g, '\\$&'),
  );
  await expect(page.getByText(busy).last()).toBeVisible({ timeout: 30_000 });
  await expect(input).toHaveValue('MOCK_BUSY');
  await expect(page.getByRole('button', { name: t('en', 'chat.send') })).toBeDisabled();
  await expect(page.getByText(t('en', 'chat.error.ready'))).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole('button', { name: t('en', 'chat.send') })).toBeEnabled();
  await input.fill('');

  // The history survives a reload; clearing it needs a confirmation
  await page.reload();
  await expect(log.getByText('mera portfolio kaisa hai?')).toBeVisible();
  await page.getByRole('button', { name: t('en', 'chat.clear') }).click();
  await page.getByRole('button', { name: t('en', 'chat.clearYes') }).click();
  await expect(page.getByText(t('en', 'chat.empty.title'))).toBeVisible();
  await page.reload();
  await expect(page.getByText(t('en', 'chat.empty.title'))).toBeVisible();
});

test('Urdu: the chat reads right to left and the toggle stays on the chat screen', async ({
  page,
}) => {
  await register(page, 'en', newEmail());
  const total = Number(await progress(page).getAttribute('aria-valuemax'));
  for (let step = 1; step <= total; step += 1) {
    await choices(page).first().click();
  }
  await page.getByRole('button', { name: t('en', 'onboarding.result.cta') }).click();
  await page.goto('/chat');

  await page
    .getByRole('main')
    .getByRole('button', { name: t('en', 'common.switchLanguageLabel') })
    .click();
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.getByRole('heading', { name: t('ur', 'chat.title') })).toBeVisible();
  await page.getByRole('button', { name: t('ur', 'chat.starters.portfolio') }).click();
  await expect(page.getByRole('log').getByText(/MOCK reply/)).toBeVisible({ timeout: 30_000 });
  // The Urdu message bubble itself is right to left
  await expect(page.getByRole('log').locator('[dir="rtl"]').first()).toBeVisible();
});
