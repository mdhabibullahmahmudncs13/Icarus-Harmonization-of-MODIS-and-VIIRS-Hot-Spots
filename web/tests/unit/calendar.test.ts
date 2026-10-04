/**
 * Tests for the calendar model (src/charts/calendar.ts).
 *
 * The calendar is derived, not fetched, so its indexing is the only thing
 * that can go wrong: a wrong day-of-year puts a fire on the wrong date.
 */
import { describe, expect, it } from "vitest";
import {
  baselineRowFor,
  buildCalendar,
  dayOfYear,
  daysInYear,
  MONTH_STARTS,
  rampLevel,
} from "../../src/charts/calendar";
import type { BaselineResponse, SeriesResponse } from "../../src/contract";

const META = {
  source: "mock" as const,
  generated_at: "2026-10-04T00:00:00Z",
  region: { bbox: [88, 20, 93, 27] as [number, number, number, number] },
  cell_km: 5.5,
  min_confidence: 50,
  date_range: ["2003-01-01", "2026-09-30"] as [string, string],
};

function seriesOf(rows: SeriesResponse["rows"]): SeriesResponse {
  return { meta: META, rows };
}

function row(date: string, raw: number, harm: number): SeriesResponse["rows"][number] {
  return {
    date,
    raw_modis: raw,
    raw_viirs: 0,
    raw_total: raw,
    harm_modis: harm,
    harm_viirs: 0,
    harm_total: harm,
  };
}

describe("day and year arithmetic", () => {
  it("counts leap years the way the calendar needs", () => {
    expect(daysInYear(2023)).toBe(365);
    expect(daysInYear(2024)).toBe(366);
    expect(daysInYear(1900)).toBe(365);
    expect(daysInYear(2000)).toBe(366);
  });

  it("numbers days of year from 1", () => {
    expect(dayOfYear("2024-01-01")).toBe(1);
    expect(dayOfYear("2024-03-01")).toBe(61); // 2024 is a leap year
    expect(dayOfYear("2023-03-01")).toBe(60);
    expect(dayOfYear("2024-12-31")).toBe(366);
    expect(dayOfYear("2023-12-31")).toBe(365);
  });

  it("places month starts monotonically and inside the year", () => {
    const starts = MONTH_STARTS.map((m) => m.doy);
    expect(starts[0]).toBe(1);
    expect([...starts].sort((a, b) => a - b)).toEqual(starts);
    expect(Math.max(...starts)).toBeLessThan(366);
  });
});

describe("buildCalendar", () => {
  const series = seriesOf([
    row("2024-01-01", 10, 4),
    row("2024-01-02", 30, 12),
    row("2023-06-15", 20, 8),
  ]);

  it("indexes rows by year and day of year", () => {
    const model = buildCalendar(series, "raw");
    expect(model.years).toEqual([2023, 2024]);
    expect(model.valueAt(2024, 1)).toBe(10);
    expect(model.valueAt(2024, 2)).toBe(30);
    expect(model.dateAt(2024, 2)).toBe("2024-01-02");
  });

  it("returns null for days the record does not cover", () => {
    const model = buildCalendar(series, "raw");
    expect(model.valueAt(2024, 300)).toBeNull();
    expect(model.dateAt(2024, 300)).toBeNull();
  });

  it("reads the mode it is asked for", () => {
    expect(buildCalendar(series, "raw").max).toBe(30);
    expect(buildCalendar(series, "harmonized").max).toBe(12);
    expect(buildCalendar(series, "harmonized").valueAt(2024, 1)).toBe(4);
  });

  it("is deterministic", () => {
    expect(buildCalendar(series, "raw").max).toBe(buildCalendar(series, "raw").max);
    expect(buildCalendar(series, "raw").years).toEqual([2023, 2024]);
  });
});

describe("rampLevel", () => {
  it("reserves 0 for no data", () => {
    expect(rampLevel(0, 100)).toBe(0);
    expect(rampLevel(5, 0)).toBe(0);
  });

  it("never decreases as the value grows", () => {
    const levels = [1, 5, 12, 25, 50, 80, 100].map((v) => rampLevel(v, 100));
    expect(levels).toEqual([...levels].sort((a, b) => a - b));
  });

  it("tops out at the maximum", () => {
    expect(rampLevel(100, 100)).toBe(6);
    expect(rampLevel(1, 100)).toBe(1);
  });
});

describe("baselineRowFor", () => {
  const baseline: BaselineResponse = {
    meta: META,
    window_days: 7,
    years_used: 24,
    rows: [
      { doy: 75, p05: 1, p25: 3, p50: 4, p75: 5, p95: 7 },
      { doy: 100, p05: 2, p25: 4, p50: 6, p75: 8, p95: 9 },
    ],
  };

  it("finds the row for the date's day of year", () => {
    expect(baselineRowFor(baseline, "2024-03-15")?.doy).toBe(75);
    expect(baselineRowFor(baseline, "2024-04-09")?.p50).toBe(6);
  });

  it("returns null when the window has no row", () => {
    expect(baselineRowFor(baseline, "2024-01-01")).toBeNull();
  });
});
