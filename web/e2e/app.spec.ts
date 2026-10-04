import { expect, test, type Page } from "@playwright/test";

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

test("the globe hero draws the region and the panel lists real payload cells", async ({ page }) => {
  const cells = (await (await page.request.get("/mock/cells.json")).json()) as {
    rows: { cell_id: string; raw: number; harmonized: number }[];
  };

  await page.goto("/");
  await expect(page.getByTestId("globe-stage")).toBeVisible();
  await expect(page.locator("canvas")).toBeVisible();
  // WebGL started, so the hero drew rather than falling back to the note.
  await expect(page.getByTestId("globe-fallback")).toHaveCount(0);

  // The panel repeats the payload: same cell count, same busiest raw value.
  await expect(
    page.getByText(`${cells.rows.length.toLocaleString("en-US")} cells ≥ 1 detection`),
  ).toBeVisible();
  const busiest = Math.max(...cells.rows.map((row) => row.raw));
  await expect(page.getByTestId("hot-row")).toHaveCount(7);
  await expect(page.getByTestId("hot-row").first()).toContainText(`${busiest} detections`);
});

/**
 * The globe's own pixels, with the copy that sits over the canvas hidden.
 * A plain element screenshot would also capture the overlays, which change
 * with the mode and would make the diff below pass for the wrong reason.
 */
async function globeClip(
  page: Page,
): Promise<{ x: number; y: number; width: number; height: number }> {
  await page.addStyleTag({ content: ".hero-copy { visibility: hidden !important; }" });
  await page.evaluate(() => window.scrollTo(0, 0));
  const stage = await page.getByTestId("globe-stage").boundingBox();
  expect(stage).not.toBeNull();
  return {
    x: Math.round(stage!.x),
    y: Math.round(stage!.y),
    width: Math.round(stage!.width),
    height: Math.round(stage!.height),
  };
}

test("selecting a hotspot cell marks it and moves the globe", async ({ page }) => {
  // Reduced motion pins the camera, so the opening move is not still easing
  // through this test: the baseline is fixed and only the click can change it.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.getByTestId("globe-stage")).toBeVisible();
  const clip = await globeClip(page);
  await page.waitForTimeout(700);
  const before = await page.screenshot({ clip });
  expect(Buffer.compare(before, await page.screenshot({ clip }))).toBe(0);

  const firstRow = page.getByTestId("hot-row").first();
  await firstRow.click();
  await expect(firstRow).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "Whole Earth" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  await page.waitForTimeout(400);
  const after = await page.screenshot({ clip });
  expect(Buffer.compare(before, after)).not.toBe(0);

  await page.getByRole("button", { name: "Whole Earth" }).click();
  await expect(firstRow).toHaveAttribute("aria-pressed", "false");
});

test("the mode toggle reaches the globe itself, not just the legend", async ({ page }) => {
  // Reduced motion pins the camera (no auto-spin, no easing), so the render is
  // deterministic and any pixel change below can only come from the data.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.getByTestId("globe-stage")).toBeVisible();
  const clip = await globeClip(page);
  await page.waitForTimeout(700);
  const rawFrame = await page.screenshot({ clip });
  // Guard the guard: with a still camera two frames must be byte-identical, or
  // the diff below would prove nothing about the toggle.
  expect(Buffer.compare(rawFrame, await page.screenshot({ clip }))).toBe(0);

  await page.getByRole("radio", { name: "Harmonized" }).click();
  await page.waitForTimeout(400);
  const harmonizedFrame = await page.screenshot({ clip });
  expect(Buffer.compare(rawFrame, harmonizedFrame)).not.toBe(0);

  // The copy that explains the globe follows the same mode.
  await page.addStyleTag({ content: ".hero-copy { visibility: visible !important; }" });
  await expect(page.getByText(/sized by distinct cell-days/)).toBeVisible();

  await expect(page.getByText(/sized by every detection counted/)).toHaveCount(0);
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
