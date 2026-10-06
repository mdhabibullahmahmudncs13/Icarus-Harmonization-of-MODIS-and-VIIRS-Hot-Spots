import { describe, expect, it } from 'vitest';
import {
  aggregateToBins,
  binEndISO,
  binOfDoy,
  binStartISO,
  doyFromISO,
  extent,
  modeValue,
  rampColor,
  stepRatios,
} from '../src/lib/series';
import type { SeriesPoint } from '../src/contract/types';

const row = (date: string, raw: number, harm: number): SeriesPoint => ({
  date,
  raw_modis: raw,
  raw_viirs: 0,
  raw_total: raw,
  harm_modis: harm,
  harm_viirs: 0,
  harm_total: harm,
  coverage: 1,
  source: 'MODIS',
});

describe('binOfDoy', () => {
  it('maps the MODIS 8-day boundaries', () => {
    expect(binOfDoy(1)).toBe(1);
    expect(binOfDoy(8)).toBe(1);
    expect(binOfDoy(9)).toBe(2);
    expect(binOfDoy(365)).toBe(46);
    expect(binOfDoy(366)).toBe(46);
  });

  it('never exceeds 46 bins', () => {
    for (let doy = 1; doy <= 366; doy++) {
      const b = binOfDoy(doy);
      expect(b).toBeGreaterThanOrEqual(1);
      expect(b).toBeLessThanOrEqual(46);
    }
  });
});

describe('dates', () => {
  it('round-trips day of year', () => {
    expect(doyFromISO('2020-01-01')).toBe(1);
    expect(doyFromISO('2020-12-31')).toBe(366); // leap year
    expect(doyFromISO('2019-12-31')).toBe(365);
  });

  it('computes bin start and end', () => {
    expect(binStartISO(2020, 1)).toBe('2020-01-01');
    expect(binEndISO(2020, 1)).toBe('2020-01-08');
    expect(binStartISO(2020, 2)).toBe('2020-01-09');
  });
});

describe('modeValue', () => {
  it('picks the active metric', () => {
    const r = row('2019-03-01', 12, 3);
    expect(modeValue(r, 'raw')).toBe(12);
    expect(modeValue(r, 'harmonized')).toBe(3);
  });
});

describe('aggregateToBins', () => {
  it('sums daily rows into one entry per year and bin', () => {
    const bins = aggregateToBins(
      [row('2019-01-01', 2, 1), row('2019-01-08', 3, 1), row('2019-01-09', 5, 2)],
      8,
    );
    expect(bins).toHaveLength(2);
    expect(bins[0]).toMatchObject({ year: 2019, bin: 1, raw: 5, harmonized: 2 });
    expect(bins[1]).toMatchObject({ year: 2019, bin: 2, raw: 5, harmonized: 2 });
  });

  it('sorts by year then bin', () => {
    const bins = aggregateToBins([row('2020-01-09', 1, 1), row('2019-01-01', 1, 1)], 8);
    expect(bins.map((b) => b.year)).toEqual([2019, 2020]);
  });

  it('carries the S7 coverage and source into the bin', () => {
    const bins = aggregateToBins([{ ...row('2019-01-02', 4, 2), coverage: 0.5, source: 'VIIRS_CAL' }], 8);
    expect(bins[0]).toMatchObject({ year: 2019, bin: 1, coverage: 0.5, source: 'VIIRS_CAL' });
  });
});

describe('stepRatios', () => {
  it('reports the raw step but a flat harmonized step', () => {
    const rows = [
      row('2011-06-01', 10, 5),
      row('2011-06-02', 10, 5),
      row('2013-06-01', 30, 5),
      row('2013-06-02', 30, 5),
    ];
    const { raw, harmonized } = stepRatios(rows, '2012-01-20');
    expect(raw).toBeCloseTo(3, 5);
    expect(harmonized).toBeCloseTo(1, 5);
  });
});

describe('extent / rampColor', () => {
  it('extent handles empty and ranges', () => {
    expect(extent([])).toEqual([0, 0]);
    expect(extent([3, -1, 7])).toEqual([-1, 7]);
  });

  it('rampColor clamps and returns rgb', () => {
    expect(rampColor(-1)).toMatch(/^rgb\(/);
    expect(rampColor(2)).toMatch(/^rgb\(/);
    expect(rampColor(0)).toBe('rgb(32, 33, 38)');
  });
});
