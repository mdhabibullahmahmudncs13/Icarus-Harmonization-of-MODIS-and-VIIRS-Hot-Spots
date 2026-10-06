// Pure functions for the burning-activity calendar and series.
// No I/O, no framework — unit-tested in tests/.

import type { Mode, SeriesPoint } from '../contract/types';

export interface Bin {
  year: number;
  bin: number; // 1..46
  start: string; // ISO date
  end: string; // ISO date (inclusive)
  raw: number;
  harmonized: number;
  coverage: number; // 0..1 (mock reports 1.0 for observed bins)
}

export function doyFromISO(date: string): number {
  const [y, m, d] = date.split('-').map(Number);
  const start = Date.UTC(y, 0, 1);
  const ms = Date.UTC(y, m - 1, d) - start;
  return Math.round(ms / 86_400_000) + 1;
}

/** MODIS 8-day convention: 46 bins per year, restarting 1 January. */
export function binOfDoy(doy: number, binDays = 8): number {
  return Math.min(Math.floor((doy - 1) / binDays) + 1, 46);
}

/** First day of a bin, as an ISO date. */
export function binStartISO(year: number, bin: number, binDays = 8): string {
  const offset = (bin - 1) * binDays;
  const d = new Date(Date.UTC(year, 0, 1 + offset));
  return d.toISOString().slice(0, 10);
}

export function binEndISO(year: number, bin: number, binDays = 8): string {
  const offset = bin * binDays - 1;
  const d = new Date(Date.UTC(year, 0, 1 + offset));
  return d.toISOString().slice(0, 10);
}

/** The value a row contributes for the active mode. */
export function modeValue(row: SeriesPoint, mode: Mode): number {
  return mode === 'raw' ? row.raw_total : row.harm_total;
}

/** Aggregate a daily series into 46 eight-day bins per year. */
export function aggregateToBins(rows: SeriesPoint[], binDays = 8): Bin[] {
  const byKey = new Map<string, Bin>();
  for (const row of rows) {
    const year = Number(row.date.slice(0, 4));
    const bin = binOfDoy(doyFromISO(row.date), binDays);
    const key = `${year}-${bin}`;
    let entry = byKey.get(key);
    if (!entry) {
      entry = {
        year,
        bin,
        start: binStartISO(year, bin, binDays),
        end: binEndISO(year, bin, binDays),
        raw: 0,
        harmonized: 0,
        coverage: 1,
      };
      byKey.set(key, entry);
    }
    entry.raw += row.raw_total;
    entry.harmonized += row.harm_total;
  }
  return [...byKey.values()].sort((a, b) => a.year - b.year || a.bin - b.bin);
}

export function extent(values: number[]): [number, number] {
  if (values.length === 0) return [0, 0];
  let min = Infinity;
  let max = -Infinity;
  for (const v of values) {
    if (v < min) min = v;
    if (v > max) max = v;
  }
  return [min, max];
}

/** Mean of a series before and after a transition date. */
export function stepRatios(
  rows: SeriesPoint[],
  transition: string,
): { raw: number; harmonized: number } {
  const pre = rows.filter((r) => r.date < transition);
  const post = rows.filter((r) => r.date >= transition);
  const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);
  const eps = 1e-9;
  return {
    raw: mean(post.map((r) => r.raw_total)) / Math.max(mean(pre.map((r) => r.raw_total)), eps),
    harmonized:
      mean(post.map((r) => r.harm_total)) / Math.max(mean(pre.map((r) => r.harm_total)), eps),
  };
}

/** Interpolate a 5-stop ramp into a CSS colour, t in [0,1]. */
export function rampColor(t: number): string {
  const stops = [
    [32, 33, 38],
    [122, 90, 43],
    [224, 104, 75],
    [255, 177, 153],
    [244, 244, 246],
  ];
  const clamped = Math.max(0, Math.min(1, t));
  const pos = clamped * (stops.length - 1);
  const lo = Math.floor(pos);
  const hi = Math.min(lo + 1, stops.length - 1);
  const f = pos - lo;
  const c = stops[lo].map((v, i) => Math.round(v + (stops[hi][i] - v) * f));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}
