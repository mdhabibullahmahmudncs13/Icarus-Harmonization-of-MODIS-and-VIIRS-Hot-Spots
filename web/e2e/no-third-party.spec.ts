import { expect, test } from '@playwright/test';

/**
 * `docs/IMPLEMENTATION_PLAN.md` §3.3: "No third-party requests. A Playwright
 * test blocks all external hosts; the app still loads and works."
 *
 * This replaces the manual read of the browser's network log. Every request
 * that is not addressed to the preview server itself is aborted *and*
 * recorded; the test then exercises the shell and the mode toggle and fails
 * if a single external request was attempted.
 */
test('the app loads and works while every external host is blocked', async ({
  context,
  page,
}) => {
  const external: string[] = [];
  await context.route('**/*', (route) => {
    const { hostname } = new URL(route.request().url());
    if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1') {
      return route.continue();
    }
    external.push(route.request().url());
    return route.abort();
  });

  await page.goto('/');

  // The shell renders: the rail, the Raw | Harmonized control, and the
  // non-evidence banner (this preview runs on the mock tier).
  await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible();
  const mode = page.getByRole('group', { name: 'Series mode' });
  await expect(mode).toBeVisible();
  await expect(page.locator('.mock-banner')).toBeVisible();

  // The mode control works: clicking Raw presses it and releases Harmonized.
  const raw = mode.getByRole('button', { name: 'Raw' });
  const harmonized = mode.getByRole('button', { name: 'Harmonized' });
  await raw.click();
  await expect(raw).toHaveAttribute('aria-pressed', 'true');
  await expect(harmonized).toHaveAttribute('aria-pressed', 'false');

  expect(external, 'the app must not contact any third-party host').toEqual([]);
});
