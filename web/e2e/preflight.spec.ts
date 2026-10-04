import { expect, test } from "@playwright/test";

/**
 * Design pre-flight: the rules that can only be checked against the rendered
 * page. These are measurable claims, not opinions about taste.
 */

test("the page carries no em or en dashes in visible copy", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("series-line")).toBeVisible();
  await expect(page.getByTestId("calendar")).toBeVisible();
  const text = await page.locator("body").innerText();
  expect(text).not.toContain("—");
  expect(text).not.toContain("–");
});

test("nothing overflows horizontally at desktop or phone width", async ({ page }) => {
  for (const size of [
    { width: 1280, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(size);
    await page.goto("/");
    await expect(page.getByTestId("series-line")).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, `horizontal overflow at ${size.width}px`).toBeLessThanOrEqual(1);
  }
});

test("the top navigation stays on one line and every link resolves", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  await expect(page.getByTestId("series-line")).toBeVisible();

  const links = page.getByRole("navigation", { name: "Sections" }).getByRole("link");
  const count = await links.count();
  expect(count).toBeGreaterThanOrEqual(6);

  const tops: number[] = [];
  const hrefs: string[] = [];
  for (let i = 0; i < count; i++) {
    const link = links.nth(i);
    const box = await link.boundingBox();
    expect(box).not.toBeNull();
    if (box) tops.push(Math.round(box.y));
    const href = await link.getAttribute("href");
    expect(href).toBeTruthy();
    if (href) hrefs.push(href);
  }
  // One line: no two items differ by more than a pixel of vertical offset.
  expect(Math.max(...tops) - Math.min(...tops)).toBeLessThanOrEqual(2);

  for (const href of hrefs) {
    await expect(page.locator(href)).toHaveCount(1);
  }
});

test("the new sections are reachable and the mode toggle takes focus", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("calendar")).toBeVisible();
  await expect(page.locator("#evidence")).toBeVisible();
  await expect(page.locator("#methods")).toBeVisible();
  await expect(page.locator("#anomaly")).toBeVisible();

  const toggle = page.getByTestId("mode-toggle").getByRole("radio", { name: "Raw" });
  await toggle.focus();
  await expect(toggle).toBeFocused();
  const outlineWidth = await toggle.evaluate((el) => getComputedStyle(el).outlineWidth);
  expect(outlineWidth).not.toBe("0px");
});
