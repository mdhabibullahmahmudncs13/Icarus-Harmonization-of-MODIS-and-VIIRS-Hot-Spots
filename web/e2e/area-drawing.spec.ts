import { expect, test } from '@playwright/test';

/**
 * The custom-area drawing flow (FR-16, US-4).
 *
 * The unit tests cover the geometry; this covers the part a unit test cannot
 * reach — that a click on the map lands where the pointer is, that the shape
 * stays a draft until the user says so, and that the applied shape travels in
 * the URL hash.
 */
test('a drawn area is applied, kept in the hash, and cleared', async ({ page }) => {
  await page.goto('/#map');

  // The map view shows the drawing control.
  const draw = page.getByRole('button', { name: 'Draw an area' });
  await expect(draw).toBeVisible();
  await draw.click();

  const group = page.getByRole('group', { name: 'Draw an area' });
  await expect(group).toBeVisible();

  // The apply button is disabled until the shape is drawable.
  const use = group.getByRole('button', { name: 'Use this area' });
  await expect(use).toBeDisabled();

  // Three clicks on the map make a triangle. The click positions are inside
  // the SVG, so they land on the map and not on the controls beside it.
  const svg = page.locator('svg.map');
  const box = await svg.boundingBox();
  expect(box, 'the map must be drawn before it can be clicked').not.toBeNull();
  for (const [dx, dy] of [
    [0.3, 0.3],
    [0.7, 0.3],
    [0.5, 0.7],
  ]) {
    await svg.click({ position: { x: box!.width * dx, y: box!.height * dy } });
  }

  await expect(group).toContainText('3 points');
  await expect(use).toBeEnabled();

  // Applying it swaps the controls for the applied ones.
  await use.click();
  const applied = page.getByRole('group', { name: 'Custom area' });
  await expect(applied).toBeVisible();
  await expect(page.getByRole('button', { name: 'Redraw' })).toBeVisible();

  // The shape is in the hash, so the area is shareable.
  await expect(page).toHaveURL(/poly=/);

  // And it survives a reload.
  await page.reload();
  await expect(page.getByRole('group', { name: 'Custom area' })).toBeVisible();

  // Clearing it drops the shape and the hash entry with it.
  await page.getByRole('button', { name: 'Clear' }).click();
  await expect(page.getByRole('button', { name: 'Draw an area' })).toBeVisible();
  await expect(page).not.toHaveURL(/poly=/);
});
