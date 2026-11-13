import { describe, expect, it } from 'vitest';
import { dayOfYear } from '../src/components/BaselineChart';

describe('dayOfYear', () => {
  it('maps the first day of the year to 1', () => {
    expect(dayOfYear('2020-01-01')).toBe(1);
  });

  it('maps the last day of a common year to 365', () => {
    expect(dayOfYear('2019-12-31')).toBe(365);
  });

  it('maps the last day of a leap year to 366', () => {
    expect(dayOfYear('2020-12-31')).toBe(366);
  });

  it('counts the leap day', () => {
    expect(dayOfYear('2020-03-01')).toBe(61);
    expect(dayOfYear('2019-03-01')).toBe(60);
  });

  it('does not drift across the whole year', () => {
    for (let doy = 1; doy <= 365; doy += 1) {
      const d = new Date(Date.UTC(2021, 0, doy));
      const iso = d.toISOString().slice(0, 10);
      expect(dayOfYear(iso)).toBe(doy);
    }
  });
});
