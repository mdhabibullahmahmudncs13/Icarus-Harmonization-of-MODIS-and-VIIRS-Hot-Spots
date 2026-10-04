/**
 * Cells → globe spots.
 *
 * The contract's `CellsResponse` carries a bounding box per cell; the globe
 * needs a point. This is the only conversion, and it is a centre of the box,
 * not a modelled position — the honest reading of the payload.
 */
import type { CellsResponse } from "../contract";
import { bboxCentre } from "./geo";
import type { GlobeSpot } from "./globeSpec";
import type { Mode } from "../state/urlState";

export function spotsFromCells(cells: CellsResponse): GlobeSpot[] {
  return cells.rows.map((row) => {
    const { lat, lon } = bboxCentre(row.bounds);
    return { id: row.cell_id, lat, lon, raw: row.raw, harmonized: row.harmonized };
  });
}

/** The busiest cells in the active mode, for the side panel. */
export function topSpots(spots: GlobeSpot[], n: number, mode: Mode): GlobeSpot[] {
  const value = (spot: GlobeSpot): number => (mode === "raw" ? spot.raw : spot.harmonized);
  return [...spots].sort((a, b) => value(b) - value(a)).slice(0, n);
}

export function totalFor(spots: GlobeSpot[], mode: Mode): number {
  return spots.reduce((sum, spot) => sum + (mode === "raw" ? spot.raw : spot.harmonized), 0);
}

/** Sum of one 5.5 km cell's detections, in the format the panel shows. */
export function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

/** Fixed 3-decimal coordinates: the cell grid is approximate, so no false precision. */
export function formatCoord(lat: number, lon: number): string {
  const ns = `${Math.abs(lat).toFixed(3)}°${lat >= 0 ? "N" : "S"}`;
  const ew = `${Math.abs(lon).toFixed(3)}°${lon >= 0 ? "E" : "W"}`;
  return `${ns} ${ew}`;
}
