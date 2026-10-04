/**
 * Calendar model for the burning-activity calendar.
 *
 * Pure functions only: they turn the already-fetched SeriesResponse into a
 * year x day-of-year lookup so the calendar can render without a second
 * fetch and without any statistics. Bucketing is presentation, not science.
 */
import type { BaselineResponse, SeriesResponse } from "../contract";
import type { Mode } from "../state/urlState";

export const DAY_MS = 86400000;

/** Days in a year, so the leap-year column is handled honestly. */
export function daysInYear(year: number): number {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0 ? 366 : 365;
}

/** 1-based day of year for an ISO date (or Date). */
export function dayOfYear(value: string | Date): number {
  const d = typeof value === "string" ? new Date(`${value}T00:00:00Z`) : value;
  const year = d.getUTCFullYear();
  return Math.round((d.getTime() - Date.UTC(year, 0, 1)) / DAY_MS) + 1;
}

export interface CalendarModel {
  /** Years present in the record, ascending. */
  years: number[];
  /** Largest value for the active mode, used to set the ramp. */
  max: number;
  /** Value for a year and day of year, or null when the day has no row. */
  valueAt: (year: number, doy: number) => number | null;
  /** ISO date for a year and day of year, or null. */
  dateAt: (year: number, doy: number) => string | null;
}

/** Index the series by year and day of year for one mode. */
export function buildCalendar(series: SeriesResponse, mode: Mode): CalendarModel {
  const values = new Map<string, number>();
  const dates = new Map<string, string>();
  let max = 0;

  for (const row of series.rows) {
    const year = Number(row.date.slice(0, 4));
    const doy = dayOfYear(row.date);
    const key = `${year}:${doy}`;
    const value = mode === "raw" ? row.raw_total : row.harm_total;
    values.set(key, value);
    dates.set(key, row.date);
    if (value > max) max = value;
  }

  const years = [...new Set(series.rows.map((r) => Number(r.date.slice(0, 4))))].sort(
    (a, b) => a - b,
  );

  return {
    years,
    max,
    valueAt: (year, doy) => values.get(`${year}:${doy}`) ?? null,
    dateAt: (year, doy) => dates.get(`${year}:${doy}`) ?? null,
  };
}

/**
 * Ramp step 1..6 for a value, or 0 for no data. Uses fixed fractions of the
 * mode maximum so the two modes are read on their own scales, and the ramp
 * stays legible at the calendar's cell size.
 */
export function rampLevel(value: number, max: number): 0 | 1 | 2 | 3 | 4 | 5 | 6 {
  if (value <= 0 || max <= 0) return 0;
  const fraction = value / max;
  if (fraction <= 0.04) return 1;
  if (fraction <= 0.1) return 2;
  if (fraction <= 0.2) return 3;
  if (fraction <= 0.4) return 4;
  if (fraction <= 0.7) return 5;
  return 6;
}

/** The baseline row whose day of year matches, or null when absent. */
export function baselineRowFor(
  baseline: BaselineResponse,
  isoDate: string,
): BaselineResponse["rows"][number] | null {
  const doy = dayOfYear(isoDate);
  return baseline.rows.find((row) => row.doy === doy) ?? null;
}

/** Month boundary days, for the calendar's month ticks. */
export const MONTH_STARTS: readonly { doy: number; label: string }[] = [
  { doy: 1, label: "Jan" },
  { doy: 32, label: "Feb" },
  { doy: 60, label: "Mar" },
  { doy: 91, label: "Apr" },
  { doy: 121, label: "May" },
  { doy: 152, label: "Jun" },
  { doy: 182, label: "Jul" },
  { doy: 213, label: "Aug" },
  { doy: 244, label: "Sep" },
  { doy: 274, label: "Oct" },
  { doy: 305, label: "Nov" },
  { doy: 335, label: "Dec" },
];
