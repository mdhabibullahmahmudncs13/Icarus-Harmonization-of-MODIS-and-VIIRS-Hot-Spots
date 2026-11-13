// Pure functions for the burning-activity calendar and series.
// No I/O, no framework — unit-tested in tests/.

import type { BinSource, Mode, SeriesPoint } from '../contract/types';

export interface Bin {
  year: number;
  bin: number; // 1..46
  start: string; // ISO date
  end: string; // ISO date (inclusive)
  raw: number;
  harmonized: number;
  coverage: number; // S7, 0..1; below 0.75 hatches
  source: BinSource;
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

/**
 * Last day of a bin, as an ISO date.
 *
 * The 46th bin starts on day 361, so it runs past the end of the year in a
 * 365-day one. The end is clamped to 31 December, otherwise the bin claims
 * days that belong to the next year and a January date looks like it falls
 * in the previous year's last bin.
 */
export function binEndISO(year: number, bin: number, binDays = 8): string {
  const offset = bin * binDays - 1;
  const d = new Date(Date.UTC(year, 0, 1 + offset));
  const lastDay = Date.UTC(year, 11, 31);
  const clamped = Math.min(d.getTime(), lastDay);
  return new Date(clamped).toISOString().slice(0, 10);
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
        // S7 coverage and source are properties of the bin, so every day in a
        // bin carries the same pair; take it from the first row.
        coverage: row.coverage,
        source: row.source,
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

/**
 * The largest value in a list, never below a floor.
 *
 * A loop rather than `Math.max(...values)`: a spread passes every element as
 * an argument, and the engine's argument limit is lower than the number of
 * cells a large region can produce.
 */
export function maxValue(values: number[], floor = 1): number {
  let max = floor;
  for (const v of values) {
    if (v > max) max = v;
  }
  return max;
}

/**
 * The bounding box of a set of grid cells, and their largest value.
 *
 * One pass for all five numbers, for the same reason as :func:`maxValue`:
 * the pilot extent is ~380,000 cells, well past what a spread can carry.
 */
export function cellExtent(
  cells: { bounds: [number, number, number, number]; raw: number; harmonized: number }[],
  mode: Mode,
): { bounds: [number, number, number, number]; max: number; active: number } {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  let max = 1;
  let active = 0;
  for (const c of cells) {
    west = Math.min(west, c.bounds[0]);
    south = Math.min(south, c.bounds[1]);
    east = Math.max(east, c.bounds[2]);
    north = Math.max(north, c.bounds[3]);
    const value = mode === 'raw' ? c.raw : c.harmonized;
    if (value > max) max = value;
    if (value > 0) active += 1;
  }
  return { bounds: [west, south, east, north], max, active };
}

/**
 * The bin a date falls in, or undefined if it falls in none.
 *
 * A bin owns every date from its start to its end, so the date that starts a
 * bin and the date in the middle of it select the same bin. When two bins
 * could match, the later one wins: a bin that starts on the date belongs to
 * that bin, not to the previous year's tail.
 */
export function findBin(bins: Bin[], date: string): Bin | undefined {
  let found: Bin | undefined;
  for (const b of bins) {
    if (b.start <= date && date <= b.end) {
      if (!found || b.start >= found.start) found = b;
    }
  }
  return found;
}

const RAMP_DARK: [number, number, number][] = [
  [32, 33, 38],
  [122, 90, 43],
  [224, 104, 75],
  [255, 177, 153],
  [244, 244, 246],
];

const RAMP_LIGHT: [number, number, number][] = [
  [223, 227, 238],
  [240, 195, 107],
  [224, 104, 75],
  [179, 69, 47],
  [17, 17, 20],
];

/** Interpolate a 5-stop ramp into a CSS colour, t in [0,1]. */
export function rampColor(t: number, theme: 'dark' | 'light' = 'dark'): string {
  const stops = theme === 'light' ? RAMP_LIGHT : RAMP_DARK;
  const clamped = Math.max(0, Math.min(1, t));
  const pos = clamped * (stops.length - 1);
  const lo = Math.floor(pos);
  const hi = Math.min(lo + 1, stops.length - 1);
  const f = pos - lo;
  const c = stops[lo].map((v, i) => Math.round(v + (stops[hi][i] - v) * f));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}
