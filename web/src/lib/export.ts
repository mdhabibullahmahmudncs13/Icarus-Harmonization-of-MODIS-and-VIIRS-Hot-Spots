/**
 * The CSV export link.
 *
 * The challenge asks for the hotspot records behind the view to be
 * downloadable, so the export is a URL the browser fetches directly. The URL
 * is built here, apart from the button, so it can be checked without a
 * browser.
 */

import { polygonParam, type Ring } from './polygon';

/** What the export is about: the area, and the window to export. */
export interface ExportQuery {
  /** Preset id of the area the records come from. */
  aoi?: string;
  /** The drawn area, when there is one. It wins over the preset. */
  polygon?: Ring | null;
  /** First day of the window, `YYYY-MM-DD`. */
  start?: string | null;
  /** Last day of the window, `YYYY-MM-DD`. */
  end?: string | null;
}

/**
 * The URL of the CSV export for a query.
 *
 * The base is the API's base (`/api/v1` by default), and the export route
 * hangs off it. A blank start or end is left out, which the API reads as "no
 * bound on that side" — so an unset date exports everything in the area.
 */
export function exportUrl(base: string, query: ExportQuery): string {
  const params = new URLSearchParams();
  const poly = polygonParam(query.polygon ?? null);
  if (poly) params.set('polygon', poly);
  else if (query.aoi) params.set('aoi', query.aoi);
  if (query.start) params.set('start', query.start);
  if (query.end) params.set('end', query.end);
  const search = params.toString();
  const root = base.replace(/\/v1\/?$/, '');
  return `${root}/export${search ? `?${search}` : ''}`;
}

/**
 * How many records the export will hold.
 *
 * The daily series already counts the detections per day, so the total is a
 * sum of what is already loaded — no extra request, and no number the app
 * has to guess at.
 */
export function recordCount(rows: { raw_total: number }[]): number {
  return rows.reduce((sum, row) => sum + row.raw_total, 0);
}

/** A count in words, so the button can say how big the download is. */
export function formatCount(count: number): string {
  if (count < 1000) return `${count} records`;
  if (count < 1_000_000) return `${Math.round(count / 1000).toLocaleString()}k records`;
  return `${(count / 1_000_000).toFixed(1)}M records`;
}
