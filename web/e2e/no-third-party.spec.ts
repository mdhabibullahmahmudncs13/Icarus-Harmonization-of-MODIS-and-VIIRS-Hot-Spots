import { expect, test, type BrowserContext } from '@playwright/test';

/**
 * `docs/IMPLEMENTATION_PLAN.md` §3.3: "No third-party requests. A Playwright
 * test blocks all external hosts; the app still loads and works."
 *
 * This replaces the manual read of the browser's network log. Every request
 * that is not addressed to the preview server itself is aborted *and*
 * recorded; the test then exercises the page and fails if a single external
 * request was attempted.
 *
 * Service workers are blocked here on purpose: a worker answers fetches
 * itself, and Playwright's route layer cannot see requests that originate
 * inside one, so an active worker could hide a request from this check.
 */
test.use({ serviceWorkers: 'block' });

/** Abort every external host and return the URLs that were attempted. */
async function blockExternal(context: BrowserContext): Promise<string[]> {
  const external: string[] = [];
  await context.route('**/*', (route) => {
    const { hostname } = new URL(route.request().url());
    if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1') {
      return route.continue();
    }
    external.push(route.request().url());
    return route.abort();
  });
  return external;
}

test('the app loads and works while every external host is blocked', async ({
  context,
  page,
}) => {
  const external = await blockExternal(context);

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

test('the landing page renders with every external host blocked', async ({
  context,
  page,
}) => {
  const external = await blockExternal(context);

  await page.goto('/landing.html');

  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  // Its only call to action is the app, served from the same origin.
  const cta = page.locator('[data-app-link]').first();
  await expect(cta).toHaveAttribute('href', '/');

  // The hero script loaded and built the route rail from the seven beats.
  await expect(page.getByRole('navigation', { name: 'Journey' })).toBeVisible();
  await expect(page.locator('#rail-list li')).toHaveCount(7);

  // The Earth textures are served locally, not from a CDN.
  const texture = await page.request.get('/earth/earth-blue-marble.jpg');
  expect(texture.status()).toBe(200);

  expect(external, 'the landing page must not contact any third-party host').toEqual([]);
});
