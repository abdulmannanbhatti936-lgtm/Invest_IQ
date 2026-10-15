// Phase 6 smoke test: a stored portfolio backtest and a refused custom mix, on the MOCK market
// the test API seeds (services/api/tests/e2e_market.py: invented stocks, never PSX data).
import { expect, test } from '@playwright/test';
import { choices, field, newEmail, progress, register, t } from './helpers.ts';

test('generate a portfolio → 3-year backtest report → custom mix must total 100%', async ({
  page,
}) => {
  test.setTimeout(120_000);

  // Onboarding: all-first answers → Aggressive (at least 4 holdings; the MOCK market has 6)
  await register(page, 'en', newEmail());
  const total = Number(await progress(page).getAttribute('aria-valuemax'));
  for (let step = 1; step <= total; step += 1) {
    await choices(page).first().click();
  }
  await page.getByRole('button', { name: t('en', 'onboarding.result.cta') }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // Generate a portfolio from the MOCK forecasts
  await page.goto('/portfolio');
  await field(page, t('en', 'portfolio.form.capital')).fill('100000');
  await page.getByRole('button', { name: t('en', 'portfolio.form.submit'), exact: true }).click();
  // The ticker appears in the allocation legend and in its holding row (UI round)
  await expect(page.getByText('MOCKE2EA', { exact: true }).first()).toBeVisible({
    timeout: 30_000,
  });

  // Run the stored portfolio over the default three years
  await page.getByRole('link', { name: t('en', 'portfolio.backtestLink') }).click();
  await expect(page).toHaveURL(/\/backtest$/);
  await page
    .getByRole('button', { name: t('en', 'backtest.landing.run') })
    .first()
    .click();
  await expect(page).toHaveURL(/\/backtest\/[0-9a-f-]{36}$/, { timeout: 30_000 });

  // Headline return (a signed percentage), the hindsight label and the KSE-100 status
  await expect(page.getByText(t('en', 'backtest.report.headline'))).toBeVisible();
  await expect(page.getByText(/[+-]\d+\.\d{2}%/).first()).toBeVisible();
  await expect(page.getByText(t('en', 'backtest.report.hindsightPortfolio'))).toBeVisible();
  await expect(page.getByText(t('en', 'backtest.report.kseAwaiting'))).toBeVisible();

  // Metrics table: every FR31 measure, one column per line on the chart
  const table = page.getByRole('table', { name: t('en', 'backtest.metrics.caption') });
  for (const key of ['totalReturn', 'annualised', 'sharpe', 'drawdown', 'winRate']) {
    await expect(
      table.getByRole('rowheader', { name: t('en', `backtest.metrics.${key}`) }),
    ).toBeVisible();
  }
  for (const key of ['portfolio', 'startDateRules', 'benchmark']) {
    await expect(
      table.getByRole('columnheader', { name: t('en', `backtest.columns.${key}`) }),
    ).toBeVisible();
  }

  // Chart legend is always shown, not only on hover (Design.md §18)
  const legend = page.getByRole('listitem');
  for (const key of ['portfolio', 'startDateRules', 'benchmark']) {
    await expect(legend.filter({ hasText: t('en', `backtest.columns.${key}`) })).toBeVisible();
  }

  // A custom mix whose shares do not add up to 100% is refused before anything is sent
  await page.getByRole('link', { name: t('en', 'backtest.report.newTest') }).click();
  await expect(page).toHaveURL(/\/backtest$/);
  const companies = page.getByLabel(t('en', 'backtest.mix.company'));
  const shares = page.getByLabel(t('en', 'backtest.mix.weight'));
  await companies.nth(0).selectOption('MOCKE2EA');
  await companies.nth(1).selectOption('MOCKE2EB');
  await shares.nth(0).fill('60');
  await shares.nth(1).fill('30');
  await field(page, t('en', 'portfolio.form.capital')).fill('100000');
  await page
    .getByRole('button', { name: t('en', 'backtest.landing.run') })
    .last()
    .click();
  await expect(page.getByText(t('en', 'backtest.mix.total'))).toBeVisible();
  await expect(page).toHaveURL(/\/backtest$/);
});
