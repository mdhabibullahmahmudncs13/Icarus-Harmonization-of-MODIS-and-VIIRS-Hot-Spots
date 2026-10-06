import { defineConfig } from '@playwright/test';

/**
 * The offline contract check (`docs/TESTING.md` §8, `docs/IMPLEMENTATION_PLAN.md`
 * §3.3): the app must load and work while every external host is blocked.
 *
 * The spec serves a built preview, so build first:
 *
 *   ./node_modules/.bin/vite build && ./node_modules/.bin/playwright test
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  use: {
    baseURL: 'http://localhost:4173',
  },
  webServer: {
    command: './node_modules/.bin/vite preview --port 4173 --strictPort',
    url: 'http://localhost:4173',
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
