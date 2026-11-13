import { describe, expect, it } from 'vitest';
import {
  aggregateToBins,
  binEndISO,
  binOfDoy,
  binStartISO,
  cellExtent,
  doyFromISO,
  extent,
  findBin,
  maxValue,
  modeValue,
  rampColor,
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

  it('clamps the last bin to the end of the year', () => {
    // Bin 46 starts on day 361, so it runs past the end of the year.
    expect(binStartISO(2019, 46)).toBe('2019-12-27');
    expect(binEndISO(2019, 46)).toBe('2019-12-31');
    expect(binStartISO(2020, 46)).toBe('2020-12-26');
    expect(binEndISO(2020, 46)).toBe('2020-12-31');
  });

  it('never ends a bin in the following year', () => {
    for (let year = 2018; year <= 2022; year += 1) {
      for (let bin = 1; bin <= 46; bin += 1) {
        expect(binEndISO(year, bin).slice(0, 4)).toBe(String(year));
      }
    }
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

describe('findBin', () => {
  const bins = aggregateToBins(
    [
      row('2019-12-27', 1, 1), // bin 46 of 2019
      row('2020-01-01', 1, 1), // bin 1 of 2020
      row('2020-12-26', 1, 1), // bin 46 of 2020
    ],
    8,
  );

  it('finds the bin a date falls in', () => {
    expect(findBin(bins, '2019-12-27')).toMatchObject({ year: 2019, bin: 46 });
    expect(findBin(bins, '2019-12-31')).toMatchObject({ year: 2019, bin: 46 });
    expect(findBin(bins, '2020-01-01')).toMatchObject({ year: 2020, bin: 1 });
  });

  it('gives a January date to the new year, not the previous tail', () => {
    // The previous year's last bin used to run into January, so 1 January
    // matched bin 46 of 2019 as well as bin 1 of 2020.
    expect(findBin(bins, '2020-01-01')?.year).toBe(2020);
  });

  it('returns undefined for a date in no bin', () => {
    expect(findBin(bins, '2018-06-01')).toBeUndefined();
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

describe('maxValue', () => {
  it('returns the largest value', () => {
    expect(maxValue([3, 9, 4])).toBe(9);
  });

  it('never falls below the floor', () => {
    expect(maxValue([])).toBe(1);
    expect(maxValue([0, 0])).toBe(1);
    expect(maxValue([0, 0], 5)).toBe(5);
  });

  it('copes with more values than a spread can carry', () => {
    // The pilot extent is ~380,000 cells, well past the engine's argument
    // limit: `Math.max(...values)` throws there. The loop must not.
    const values = new Array(400_000).fill(2);
    values[399_999] = 12;
    expect(maxValue(values)).toBe(12);
  });
});

describe('cellExtent', () => {
  const cell = (w: number, s: number, e: number, n: number, raw: number, harm: number) => ({
    bounds: [w, s, e, n] as [number, number, number, number],
    raw,
    harmonized: harm,
  });

  it('bounds the cells and counts the active ones', () => {
    const { bounds, max, active } = cellExtent(
      [cell(10, 20, 11, 21, 5, 2), cell(8, 18, 9, 19, 0, 0)],
      'raw',
    );
    expect(bounds).toEqual([8, 18, 11, 21]);
    expect(max).toBe(5);
    expect(active).toBe(1);
  });

  it('reads the value of the active mode', () => {
    const cells = [cell(0, 0, 1, 1, 5, 2)];
    expect(cellExtent(cells, 'raw').max).toBe(5);
    expect(cellExtent(cells, 'harmonized').max).toBe(2);
  });

  it('copes with more cells than a spread can carry', () => {
    const cells = new Array(400_000).fill(null).map(() => cell(0, 0, 1, 1, 3, 1));
    const { bounds, max, active } = cellExtent(cells, 'raw');
    expect(bounds).toEqual([0, 0, 1, 1]);
    expect(max).toBe(3);
    expect(active).toBe(400_000);
  });
});
