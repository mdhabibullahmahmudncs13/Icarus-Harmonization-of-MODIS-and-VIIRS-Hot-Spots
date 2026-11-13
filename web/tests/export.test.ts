import { describe, expect, it } from 'vitest';

import { exportUrl, formatCount, recordCount } from '../src/lib/export';

describe('exportUrl', () => {
  it('asks the export route for the area and the window', () => {
    expect(exportUrl('/api/v1', { aoi: 'BGD', start: '2019-01-01', end: '2019-12-31' })).toBe(
      '/api/export?aoi=BGD&start=2019-01-01&end=2019-12-31',
    );
  });

  it('leaves out a bound that is not set, so the API reads it as open', () => {
    expect(exportUrl('/api/v1', { aoi: 'BGD', start: '2019-01-01', end: null })).toBe(
      '/api/export?aoi=BGD&start=2019-01-01',
    );
  });

  it('exports everything in the area when there is no window', () => {
    expect(exportUrl('/api/v1', { aoi: 'BGD' })).toBe('/api/export?aoi=BGD');
  });

  it('keeps a base that has no version segment', () => {
    expect(exportUrl('/api', { aoi: 'BGD' })).toBe('/api/export?aoi=BGD');
  });

  it('works against a base on another host', () => {
    expect(exportUrl('http://127.0.0.1:8000/api/v1', { aoi: 'IND-C' })).toBe(
      'http://127.0.0.1:8000/api/export?aoi=IND-C',
    );
  });
});

describe('recordCount', () => {
  it('adds up the daily detections', () => {
    expect(
      recordCount([
        { raw_total: 10 },
        { raw_total: 0 },
        { raw_total: 5 },
      ]),
    ).toBe(15);
  });

  it('counts nothing for an empty series', () => {
    expect(recordCount([])).toBe(0);
  });
});

describe('formatCount', () => {
  it('counts small numbers exactly', () => {
    expect(formatCount(0)).toBe('0 records');
    expect(formatCount(999)).toBe('999 records');
  });

  it('shortens thousands and millions', () => {
    expect(formatCount(1500)).toBe('2k records');
    expect(formatCount(1_330_000)).toBe('1.3M records');
  });
});
