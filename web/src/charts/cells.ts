/**
 * Cell-map model (Implementation plan F4).
 *
 * Pure functions only. They turn the already-fetched CellsResponse into
 * screen rectangles so the map can render without a second fetch and without
 * any statistics: every value is the payload's own, and the colour bucket is
 * presentation.
 *
 * No basemap and no tiles. A tile source would be a third-party request,
 * which the project forbids, so the map draws the region's own cell polygons
 * on a plain ground. `docs/frontend.md` specifies MapLibre plus a basemap;
 * that is a Phase 6 job once the basemap is packaged as self-hosted PMTiles.
 */
import type { CellsResponse } from "../contract";
import type { Mode } from "../state/urlState";
import { rampLevel } from "./calendar";

/** Kilometres per degree of latitude, the same constant the backend grids on. */
export const KM_PER_DEGREE_LAT = 111;

/** Units shown for each mode, matching the chart and the calendar. */
export const CELL_UNIT: Record<Mode, string> = {
  raw: "detections",
  harmonized: "cell-days",
};

export interface CellRect {
  cell_id: string;
  /** Screen geometry in the model's own units, y growing downward. */
  x: number;
  y: number;
  width: number;
  height: number;
  /** The value for the active mode. */
  value: number;
  /** Ramp step 0..6, decided from this mode's own maximum. */
  level: 0 | 1 | 2 | 3 | 4 | 5 | 6;
  raw: number;
  harmonized: number;
  peak_frp: number;
  /** [west, south, east, north] in degrees, as the payload states it. */
  bounds: [number, number, number, number];
  /** Centre of the cell, for handing a selection to the globe. */
  lat: number;
  lon: number;
}

export interface CellMapModel {
  width: number;
  height: number;
  rects: CellRect[];
  /** Largest value in the active mode, used for the ramp and the legend. */
  max: number;
}

/**
 * Project the cells onto a region box that preserves physical shape.
 *
 * Longitude degrees are shorter than latitude degrees away from the equator,
 * so the x span is scaled by cos(mid latitude) before the aspect ratio is
 * fixed. Without that the map would stretch the region east to west.
 */
export function buildCellMap(cells: CellsResponse, mode: Mode, width = 620): CellMapModel {
  const [west, south, east, north] = cells.meta.region.bbox;
  const spanLon = Math.max(east - west, 1e-6);
  const spanLat = Math.max(north - south, 1e-6);
  const midLat = (south + north) / 2;
  const widthKm = spanLon * KM_PER_DEGREE_LAT * Math.cos((midLat * Math.PI) / 180);
  const heightKm = spanLat * KM_PER_DEGREE_LAT;
  const height = Math.max(1, Math.round((width * heightKm) / Math.max(widthKm, 1e-6)));

  const px = (lon: number): number => ((lon - west) / spanLon) * width;
  const py = (lat: number): number => ((north - lat) / spanLat) * height;

  // Keep a one-pixel floor so a cell can never vanish entirely at this scale.
  const MIN = 0.75;

  let max = 0;
  const rects: CellRect[] = [];
  for (const row of cells.rows) {
    const [cellWest, cellSouth, cellEast, cellNorth] = row.bounds;
    const value = mode === "raw" ? row.raw : row.harmonized;
    if (value > max) max = value;

    // Clamp into the box so the minimum size can never push a cell out of it.
    const cellWidth = Math.max(px(cellEast) - px(cellWest), MIN);
    const cellHeight = Math.max(py(cellSouth) - py(cellNorth), MIN);
    const x = Math.min(Math.max(px(cellWest), 0), width - cellWidth);
    const y = Math.min(Math.max(py(cellNorth), 0), height - cellHeight);
    rects.push({
      cell_id: row.cell_id,
      x,
      y,
      width: cellWidth,
      height: cellHeight,
      value,
      level: 0,
      raw: row.raw,
      harmonized: row.harmonized,
      peak_frp: row.peak_frp,
      bounds: [cellWest, cellSouth, cellEast, cellNorth],
      lat: (cellSouth + cellNorth) / 2,
      lon: (cellWest + cellEast) / 2,
    });
  }

  for (const rect of rects) rect.level = rampLevel(rect.value, max);

  return { width, height, rects, max };
}
