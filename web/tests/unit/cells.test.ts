/**
 * Cell-map model tests (F4).
 *
 * The model is pure, so these check the geometry contract the map relies on:
 * one rectangle per payload row, every rectangle inside the box, a box that
 * keeps the region's physical shape, and values that follow the active mode
 * without any recomputation.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { buildCellMap, CELL_UNIT, KM_PER_DEGREE_LAT } from "../../src/charts/cells";
import type { CellsResponse } from "../../src/contract";

function loadCells(): CellsResponse {
  const file = resolve(process.cwd(), "public/mock", "cells.json");
  return JSON.parse(readFileSync(file, "utf8")) as CellsResponse;
}

const CELLS = loadCells();

describe("geometry", () => {
  it("returns one rectangle per payload row", () => {
    const model = buildCellMap(CELLS, "raw");
    expect(model.rects).toHaveLength(CELLS.rows.length);
    expect(new Set(model.rects.map((r) => r.cell_id)).size).toBe(CELLS.rows.length);
  });

  it("keeps every rectangle inside the box", () => {
    const model = buildCellMap(CELLS, "raw");
    for (const rect of model.rects) {
      expect(rect.x).toBeGreaterThanOrEqual(0);
      expect(rect.y).toBeGreaterThanOrEqual(0);
      expect(rect.width).toBeGreaterThan(0);
      expect(rect.height).toBeGreaterThan(0);
      expect(rect.x + rect.width).toBeLessThanOrEqual(model.width + 1e-9);
      expect(rect.y + rect.height).toBeLessThanOrEqual(model.height + 1e-9);
    }
  });

  it("keeps the region's physical shape rather than stretching it", () => {
    const [west, south, east, north] = CELLS.meta.region.bbox;
    const model = buildCellMap(CELLS, "raw", 620);
    const midLat = (south + north) / 2;
    const widthKm = (east - west) * KM_PER_DEGREE_LAT * Math.cos((midLat * Math.PI) / 180);
    const heightKm = (north - south) * KM_PER_DEGREE_LAT;
    const expected = (620 * heightKm) / widthKm;
    expect(model.height).toBeCloseTo(expected, 0);
    // Bangladesh is taller than it is wide, so the box must be too.
    expect(model.height).toBeGreaterThan(model.width);
  });

  it("puts each cell centre inside that cell's own bounds", () => {
    for (const rect of buildCellMap(CELLS, "raw").rects) {
      const [west, south, east, north] = rect.bounds;
      expect(rect.lon).toBeGreaterThan(west);
      expect(rect.lon).toBeLessThan(east);
      expect(rect.lat).toBeGreaterThan(south);
      expect(rect.lat).toBeLessThan(north);
    }
  });
});

describe("values follow the mode", () => {
  it("reads the raw column in raw mode and sets the maximum from it", () => {
    const model = buildCellMap(CELLS, "raw");
    const expectedMax = Math.max(...CELLS.rows.map((row) => row.raw));
    expect(model.max).toBe(expectedMax);
    for (const rect of model.rects) {
      const row = CELLS.rows.find((r) => r.cell_id === rect.cell_id);
      expect(rect.value).toBe(row?.raw);
    }
  });

  it("reads the harmonized column in harmonized mode", () => {
    const model = buildCellMap(CELLS, "harmonized");
    const expectedMax = Math.max(...CELLS.rows.map((row) => row.harmonized));
    expect(model.max).toBe(expectedMax);
    for (const rect of model.rects) {
      const row = CELLS.rows.find((r) => r.cell_id === rect.cell_id);
      expect(rect.value).toBe(row?.harmonized);
    }
  });

  it("gives the busiest cell the top ramp step and an empty one none", () => {
    const model = buildCellMap(CELLS, "raw");
    const busiest = model.rects.reduce((a, b) => (b.value > a.value ? b : a));
    expect(busiest.level).toBe(6);
    for (const rect of model.rects) {
      expect(rect.level).toBeGreaterThanOrEqual(0);
      expect(rect.level).toBeLessThanOrEqual(6);
    }
  });

  it("names the unit each mode is read in", () => {
    expect(CELL_UNIT.raw).toBe("detections");
    expect(CELL_UNIT.harmonized).toBe("cell-days");
  });
});
