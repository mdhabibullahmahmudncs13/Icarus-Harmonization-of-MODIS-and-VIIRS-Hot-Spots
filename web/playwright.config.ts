import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests.
 *
 * Two projects, one per data source:
 *
 * - `chromium` — the default suite, on the dev server with mock files. It
 *   includes a third-party-host block test: the app must load with every
 *   non-localhost request aborted (plan, section 5.4).
 * - `api-mode` — the same app with `VITE_DATA=api` on port 5174, proxying
 *   `/api` to the FastAPI service from `make demo` on port 8000. This is the
 *   Phase 5 proof that the mock-to-real swap actually works.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: "npm run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run dev:api",
      url: "http://127.0.0.1:5174",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      // `make demo` sets OFFLINE=1, so the API serves the committed fixture.
      command: "make demo",
      cwd: "..",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      testIgnore: /api-mode\.spec\.ts/,
    },
    {
      name: "api-mode",
      use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:5174" },
      testMatch: /api-mode\.spec\.ts/,
    },
  ],
});
