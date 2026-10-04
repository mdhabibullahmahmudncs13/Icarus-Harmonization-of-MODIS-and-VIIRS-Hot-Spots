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

test("the calendar reads the same payload and follows the toggle", async ({ page }) => {
  const payload = (await (await page.request.get("/mock/series.json")).json()) as {
    rows: { date: string; raw_total: number; harm_total: number }[];
  };
  // A day where the two modes genuinely differ, so the assertion can bite.
  const target = payload.rows.find((r) => r.raw_total !== r.harm_total);
  expect(target).toBeTruthy();
  if (!target) return;

  await page.goto("/");
  await expect(page.getByTestId("calendar")).toBeVisible();
  await expect(page.getByTestId("calendar-readout")).toBeVisible();
  await expect(page.getByRole("heading", { name: /Burning calendar, 2003 to 2026/ })).toBeVisible();

  const cell = page.locator(`[data-testid="cal-cell"][data-date="${target.date}"]`);
  await expect(cell).toHaveCount(1);
  await cell.click();

  // Selection reaches the URL, and the readout quotes the raw value.
  expect(page.url()).toContain(`date=${target.date}`);
  await expect(page.getByTestId("calendar-readout")).toContainText(
    `${target.date}: ${target.raw_total} detections`,
  );

  await page.getByRole("radio", { name: "Harmonized" }).click();
  // Same cell, same payload, new mode: no refetch, just a different reading.
  await expect(page.getByTestId("calendar-readout")).toContainText(
    `${target.date}: ${target.harm_total} cell-days`,
  );
});

test("the validation card and methods panel show the payload and its citations", async ({
  page,
}) => {
  const validation = (await (await page.request.get("/mock/validation.json")).json()) as {
    raw: { pearson: number };
    harmonized: { pearson: number };
    overlap: { start: string; end: string };
  };
  const methods = (await (await page.request.get("/mock/methods.json")).json()) as {
    confidence_mapping: { l: number; n: number; h: number };
    datasets: { id: string; url: string }[];
    notices: string[];
  };
  const citedUrl = methods.datasets[0].url;
  const map = methods.confidence_mapping;

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Validation on the overlap" })).toBeVisible();

  // Scoped to the card and the table: the dates live inside a sentence and
  // the harmonized correlation is repeated once per sweep cell.
  const card = page.locator("#evidence");
  await expect(card.getByText(validation.overlap.start)).toBeVisible();
  await expect(card.getByText(validation.overlap.end)).toBeVisible();
  const table = card.locator(".stat-table");
  await expect(table.getByText(validation.raw.pearson.toFixed(3))).toBeVisible();
  await expect(table.getByText(validation.harmonized.pearson.toFixed(3))).toBeVisible();
  await expect(table.getByText("Raw detections")).toBeVisible();
  await expect(table.getByText("Harmonized cell-days")).toBeVisible();

  // Methods is a disclosure: it starts closed, then opens on click.
  const summary = page.getByText("Methods and datasets");
  await expect(summary).toBeVisible();
  await summary.click();
  await expect(page.getByText(`low ${map.l}, nominal ${map.n}, high ${map.h}`)).toBeVisible();
  // The citations are the payload's own URLs, not a hard-coded one: every
  // dataset must render as a link.
  const cited = page.getByRole("link", { name: citedUrl });
  await expect(cited).toHaveCount(methods.datasets.length);
  await expect(cited.first()).toBeVisible();
  await expect(page.getByText(methods.datasets[0].id)).toBeVisible();
  await expect(page.getByText(methods.notices[0])).toBeVisible();
});

test("the anomaly box answers for the selected day against the baseline", async ({ page }) => {
  const baseline = (await (await page.request.get("/mock/baseline.json")).json()) as {
    rows: { doy: number; p50: number; p95: number }[];
  };
  const first = baseline.rows[0];
  expect(first).toBeTruthy();
  if (!first) return;

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Is this unusual?" })).toBeVisible();
  // No date selected yet, so the box tells you to pick one.
  await expect(page.getByText(/Select a day on the timeline or the calendar/)).toBeVisible();

  // Clicking a day makes the box look up that day-of-year in the baseline.
  await page.getByTestId("cal-cell").first().click();
  await expect(page.locator(".baseline-band")).toBeVisible();
  await expect(
    page.locator(".baseline-band").getByText(String(first.p50), { exact: true }),
  ).toBeVisible();
});

test("the region map draws the payload's cells and follows the toggle", async ({ page }) => {
  const cells = (await (await page.request.get("/mock/cells.json")).json()) as {
    meta: { cell_km: number };
    rows: { cell_id: string; raw: number; harmonized: number }[];
  };
  const rawMax = Math.max(...cells.rows.map((row) => row.raw));
  const harmonizedMax = Math.max(...cells.rows.map((row) => row.harmonized));
  expect(rawMax).not.toBe(harmonizedMax);

  await page.goto("/");
  await expect(page.getByTestId("region-map")).toBeVisible();
  // One square per payload cell, not a sampled subset.
  await expect(page.getByTestId("map-cell")).toHaveCount(cells.rows.length);

  // The legend names the raw unit and the raw maximum.
  await expect(page.locator("#map .cal-key")).toContainText(`${rawMax} detections`);

  // Clicking a square makes the same selection the table makes: in raw mode
  // the busiest cell is the table's first row.
  const busiest = cells.rows.reduce((a, b) => (b.raw > a.raw ? b : a));
  await page.locator(`[data-testid="map-cell"][data-cell-id="${busiest.cell_id}"]`).click();
  await expect(page.getByTestId("hot-row").first()).toHaveAttribute("aria-pressed", "true");

  // The same cells, read as cell-days, without a refetch.
  await page.getByRole("radio", { name: "Harmonized" }).click();
  await expect(page.locator("#map .cal-key")).toContainText(`${harmonizedMax} cell-days`);
});
