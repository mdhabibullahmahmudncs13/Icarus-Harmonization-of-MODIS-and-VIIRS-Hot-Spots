import { expect, test } from "@playwright/test";

test("app loads on mock data with banner, badge and chart", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("mock-banner")).toBeVisible();
  await expect(page.getByTestId("source-badge")).toHaveAttribute("data-source", "mock");
  await expect(page.getByTestId("series-line")).toBeVisible();
  await expect(page.getByTestId("epoch-marker")).toBeVisible();
  // Heading derived from the payload, in sentence case.
  await expect(page.getByRole("heading", { name: /Daily counts, 2003 to 2026/ })).toBeVisible();
});

test("toggle changes the rendered series and syncs the URL", async ({ page }) => {
  await page.goto("/");
  const line = page.getByTestId("series-line");
  await expect(line).toHaveAttribute("data-mode", "raw");
  const rawPath = await line.getAttribute("d");
  expect(rawPath).toBeTruthy();

  await page.getByRole("radio", { name: "Harmonized" }).click();
  await expect(line).toHaveAttribute("data-mode", "harmonized");
  // Wait out the ~600 ms transition, then compare the settled path.
  await page.waitForTimeout(750);
  const harmPath = await line.getAttribute("d");
  expect(harmPath).toBeTruthy();
  expect(harmPath).not.toBe(rawPath);

  // Mode is synced to the URL.
  expect(page.url()).toContain("mode=harmonized");

  // Toggling back restores the raw path.
  await page.getByRole("radio", { name: "Raw", exact: true }).click();
  await page.waitForTimeout(750);
  expect(await line.getAttribute("d")).toBe(rawPath);
});

test("toggling mode fires no network requests", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (req) => {
    if (req.url().startsWith("http")) requests.push(req.url());
  });

  await page.goto("/");
  await expect(page.getByTestId("series-line")).toBeVisible();
  // Let initial loads (mock JSON, fonts, HMR) settle.
  await page.waitForTimeout(600);
  requests.length = 0;

  await page.getByRole("radio", { name: "Harmonized" }).click();
  await page.waitForTimeout(400);
  await page.getByRole("radio", { name: "Raw", exact: true }).click();
  await page.waitForTimeout(400);

  expect(requests).toEqual([]);
});

test("provenance drawer opens with the payload behind the figure", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("series-line")).toBeVisible();
  await page.getByRole("button", { name: "View source JSON" }).click();
  const drawer = page.getByTestId("provenance-drawer");
  await expect(drawer).toBeVisible();
  await expect(drawer.locator("code")).toContainText('"rows"');
  await page.keyboard.press("Escape");
  await expect(drawer).not.toBeVisible();
});

test("app loads with every external host blocked", async ({ browser }) => {
  const context = await browser.newContext();
  const blocked: string[] = [];
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (url.hostname === "127.0.0.1" || url.hostname === "localhost") {
      return route.continue();
    }
    blocked.push(url.href);
    return route.abort();
  });
  const page = await context.newPage();
  await page.goto("http://127.0.0.1:5173/");
  await expect(page.getByTestId("series-line")).toBeVisible();
  await expect(page.getByTestId("mock-banner")).toBeVisible();
  await page.getByRole("radio", { name: "Harmonized" }).click();
  await expect(page.getByTestId("series-line")).toHaveAttribute("data-mode", "harmonized");
  // The app itself must never even attempt a request to a non-local host.
  expect(blocked).toEqual([]);
  await context.close();
});
