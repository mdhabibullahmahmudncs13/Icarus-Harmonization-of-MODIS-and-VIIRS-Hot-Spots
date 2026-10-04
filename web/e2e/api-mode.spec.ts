import { expect, test } from "@playwright/test";

/**
 * The Phase 5 swap: the identical app running on `VITE_DATA=api`.
 *
 * These run in the `api-mode` project against the dev server on port 5174,
 * whose `/api` prefix is proxied to the FastAPI service started by
 * `make demo`. Every expected value is read back from the API itself, so the
 * assertions compare the rendered page with the payload, not with a
 * hard-coded number.
 */

interface SeriesPayload {
  rows: { date: string; raw_total: number; harm_total: number }[];
}

test("the app loads from the API and reports the API's own source", async ({ page }) => {
  const series = (await (await page.request.get("/api/series")).json()) as SeriesPayload;
  const firstYear = series.rows[0].date.slice(0, 4);
  const lastYear = series.rows[series.rows.length - 1].date.slice(0, 4);

  await page.goto("/");

  // The API is the source, so the badge says so and the mock banner is gone.
  await expect(page.getByTestId("source-badge")).toHaveAttribute("data-source", "fixture");
  await expect(page.getByTestId("mock-banner")).toHaveCount(0);

  await expect(page.getByTestId("series-line")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: `Daily counts, ${firstYear} to ${lastYear}` }),
  ).toBeVisible();

  // The globe was fed the API's cells, not the mock file's.
  const cells = (await (await page.request.get("/api/cells")).json()) as { rows: unknown[] };
  await expect(
    page.getByText(`${cells.rows.length.toLocaleString("en-US")} cells ≥ 1 detection`),
  ).toBeVisible();
});

test("the whole page renders with every request served by the API", async ({ page }) => {
  const apiCalls: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/")) apiCalls.push(url.pathname);
  });

  await page.goto("/");
  await expect(page.getByTestId("series-line")).toBeVisible();
  await expect(page.getByTestId("calendar")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Validation on the overlap" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Is this unusual?" })).toBeVisible();

  // Every contract endpoint the page needs was fetched over HTTP, and no
  // mock JSON file was requested.
  for (const endpoint of ["/api/meta", "/api/series", "/api/cells", "/api/validation"]) {
    expect(apiCalls).toContain(endpoint);
  }
  expect(apiCalls.some((path) => path.startsWith("/api/anomaly"))).toBe(true);
});

test("selecting a day asks the API for that day's anomaly", async ({ page }) => {
  const series = (await (await page.request.get("/api/series")).json()) as SeriesPayload;
  const target = series.rows.find((row) => row.raw_total !== row.harm_total) ?? series.rows[0];

  await page.goto("/");
  await expect(page.getByTestId("calendar")).toBeVisible();

  const cell = page.locator(`[data-testid="cal-cell"][data-date="${target.date}"]`);
  await expect(cell).toHaveCount(1);

  const request = page.waitForRequest((req) =>
    req.url().includes(`/api/anomaly?date=${target.date}`),
  );
  await cell.click();
  await request;

  const anomaly = (await (await page.request.get(`/api/anomaly?date=${target.date}`)).json()) as {
    value: number;
  };
  await expect(page.locator(".anomaly-tile")).toContainText(String(Math.round(anomaly.value)));
});

test("an uncovered day is reported in the box, not as a page error", async ({ page }) => {
  // 1999 is outside the fixture's range, so the API answers 404 for it.
  await page.goto("/?date=1999-01-01");
  await expect(page.getByTestId("series-line")).toBeVisible();

  await expect(page.getByTestId("anomaly-unavailable")).toBeVisible();
  await expect(page.getByTestId("anomaly-unavailable")).toContainText("HTTP 404");
  // The rest of the page is intact.
  await expect(page.getByTestId("load-error")).toHaveCount(0);
  await expect(page.getByTestId("calendar")).toBeVisible();
});
