import { describe, expect, it } from 'vitest';
import { applyChange, buildHash, DEFAULT_STATE, parseHash } from '../src/state/urlState';

describe('parseHash', () => {
  it('returns defaults for an empty hash', () => {
    expect(parseHash('')).toEqual(DEFAULT_STATE);
  });

  it('parses view and query', () => {
    expect(parseHash('#calendar?mode=raw&aoi=IND-C&date=2019-03-01')).toEqual({
      view: 'calendar',
      mode: 'raw',
      aoi: 'IND-C',
      date: '2019-03-01',
    });
  });

  it('falls back for an unknown view', () => {
    expect(parseHash('#nope').view).toBe('overview');
  });

  it('rejects a malformed date and mode', () => {
    const s = parseHash('#map?date=0519&mode=sideways');
    expect(s.date).toBeNull();
    expect(s.mode).toBe('harmonized');
  });
});

describe('buildHash', () => {
  it('omits a null date', () => {
    expect(buildHash({ view: 'map', mode: 'raw', aoi: 'BGD', date: null })).toBe(
      '#map?mode=raw&aoi=BGD',
    );
  });

  it('round-trips through parseHash', () => {
    const state = { view: 'anomalies', mode: 'raw', aoi: 'NPL', date: '2020-02-02' } as const;
    expect(parseHash(buildHash(state))).toEqual(state);
  });
});

describe('applyChange', () => {
  it('changes one field and keeps the rest', () => {
    const next = applyChange(DEFAULT_STATE, { view: 'map' });
    expect(next).toEqual({ ...DEFAULT_STATE, view: 'map' });
  });

  it('lets two changes in a row both land', () => {
    // The regression this guards: a setter that copied the state at the time
    // it was built dropped the earlier of two changes in the same tick.
    const first = applyChange(DEFAULT_STATE, { view: 'map' });
    const second = applyChange(first, { aoi: 'IND-C' });
    expect(second).toMatchObject({ view: 'map', aoi: 'IND-C' });
  });

  it('does not mutate the state it was given', () => {
    const before = { ...DEFAULT_STATE };
    applyChange(before, { mode: 'raw' });
    expect(before).toEqual(DEFAULT_STATE);
  });
});
