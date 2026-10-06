import { expect, test } from '@playwright/test';

/**
 * `docs/IMPLEMENTATION_PLAN.md` §7 gate: "a cold start with the network off
 * succeeds". The test loads the app once so the service worker installs and
 * caches the shell, the hashed assets and the data payloads, then flips the
 * browser offline and reloads — everything must come from the caches, and
 * the Raw | Harmonized toggle must still work without a refetch.
 */
test('cold start with the network off is served by the service worker', async ({
  context,
  page,
}) => {
  await page.goto('/');
  await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible();

  // The worker takes control and its caches fill up with the shell, assets
  // and data the page just used.
  const cachedEntries = await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
    if (!navigator.serviceWorker.controller) {
      await new Promise<void>((resolve) => {
        navigator.serviceWorker.addEventListener('controllerchange', () => resolve(), {
          once: true,
        });
      });
    }
    for (let attempt = 0; attempt < 100; attempt += 1) {
      const names = await caches.keys();
      const entries = (
        await Promise.all(names.map((name) => caches.open(name).then((cache) => cache.keys())))
      ).flat();
      if (entries.length > 3) return entries.length;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    return -1;
  });
  expect(cachedEntries, 'the service worker must have cached the app').toBeGreaterThan(3);

  // The browser has no route to the preview server at all.
  await context.setOffline(true);
  await page.reload();

  const mode = page.getByRole('group', { name: 'Series mode' });
  await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible();
  await expect(mode).toBeVisible();
  await expect(page.locator('.mock-banner')).toBeVisible();

  // The mode control still flips — from cached data, with no request.
  const raw = mode.getByRole('button', { name: 'Raw' });
  const harmonized = mode.getByRole('button', { name: 'Harmonized' });
  await raw.click();
  await expect(raw).toHaveAttribute('aria-pressed', 'true');
  await expect(harmonized).toHaveAttribute('aria-pressed', 'false');
});
