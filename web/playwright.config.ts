import { defineConfig } from '@playwright/test';

/**
 * The offline contract check (`docs/TESTING.md` §8, `docs/IMPLEMENTATION_PLAN.md`
 * §3.3): the app must load and work while every external host is blocked.
 *
 * The suite builds its own bundle, on the **mock** tier, and serves that.
 * Two reasons, both learned the hard way:
 *
 * - The tier must be explicit. `VITE_DATA` decides it, and a developer's
 *   `.env` may say `api`. The specs assert the non-evidence banner is
 *   visible, which only the mock tier renders — an api-tier build serves
 *   real observations and correctly shows no banner, so the suite would fail
 *   for a reason that has nothing to do with what it tests.
 * - The build must happen here. The suite previously reused whatever `dist/`
 *   was on disk, so it could test a bundle built days earlier against a
 *   different `.env` and pass or fail for reasons unrelated to the code.
 *
 * The mock tier is also the only one that can be tested at all: the offline
 * cold start must not depend on a live API, or the test cannot tell "served
 * from the cache" from "failed to load".
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  use: {
    baseURL: 'http://localhost:4173',
  },
  webServer: {
    command:
      'VITE_DATA=mock ./node_modules/.bin/vite build && ' +
      './node_modules/.bin/vite preview --port 4173 --strictPort',
    url: 'http://localhost:4173',
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
