import { describe, expect, it } from 'vitest';
import {
  closeRing,
  describeRing,
  isUsableRing,
  parseRing,
  pointInRing,
  polygonParam,
  ringBbox,
  selfIntersects,
  type Ring,
} from '../src/lib/polygon';

const SQUARE: Ring = [
  [88.2, 23.0],
  [88.6, 23.0],
  [88.6, 23.3],
  [88.2, 23.3],
];

describe('closeRing', () => {
  it('repeats the first point at the end', () => {
    expect(closeRing(SQUARE)).toHaveLength(5);
    expect(closeRing(SQUARE)[4]).toEqual(SQUARE[0]);
  });

  it('leaves a closed ring alone', () => {
    const closed = closeRing(SQUARE);
    expect(closeRing(closed)).toEqual(closed);
  });
});

describe('pointInRing', () => {
  it('counts a point in the middle as inside', () => {
    expect(pointInRing(88.4, 23.15, closeRing(SQUARE))).toBe(true);
  });

  it('counts a point outside as outside', () => {
    expect(pointInRing(89.0, 23.15, closeRing(SQUARE))).toBe(false);
  });
});

describe('selfIntersects', () => {
  it('accepts a plain square', () => {
    expect(selfIntersects(SQUARE)).toBe(false);
  });

  it('spots a bow tie', () => {
    expect(
      selfIntersects([
        [88.2, 23.0],
        [88.6, 23.3],
        [88.6, 23.0],
        [88.2, 23.3],
      ]),
    ).toBe(true);
  });
});

describe('isUsableRing', () => {
  it('accepts a triangle', () => {
    expect(
      isUsableRing([
        [88.2, 23.0],
        [88.6, 23.0],
        [88.6, 23.3],
      ]),
    ).toBe(true);
  });

  it('refuses fewer than three points', () => {
    expect(isUsableRing([[88.2, 23.0], [88.6, 23.0]])).toBe(false);
  });

  it('refuses a flat shape', () => {
    expect(
      isUsableRing([
        [88.2, 23.0],
        [88.4, 23.0],
        [88.6, 23.0],
      ]),
    ).toBe(false);
  });

  it('refuses a self-crossing shape', () => {
    expect(
      isUsableRing([
        [88.2, 23.0],
        [88.6, 23.3],
        [88.6, 23.0],
        [88.2, 23.3],
      ]),
    ).toBe(false);
  });
});

describe('ringBbox', () => {
  it('takes the extremes of the ring', () => {
    expect(ringBbox(SQUARE)).toEqual([88.2, 23.0, 88.6, 23.3]);
  });
});

describe('polygonParam', () => {
  it('is null for nothing', () => {
    expect(polygonParam(null)).toBeNull();
    expect(polygonParam([])).toBeNull();
  });

  it('is the JSON of the ring', () => {
    expect(polygonParam(SQUARE)).toBe(JSON.stringify(SQUARE));
  });
});

describe('parseRing', () => {
  it('reads back what polygonParam wrote', () => {
    expect(parseRing(polygonParam(SQUARE))).toEqual(SQUARE);
  });

  it('is null for rubbish', () => {
    expect(parseRing('not json')).toBeNull();
    expect(parseRing('{"type":"Point"}')).toBeNull();
    expect(parseRing('[[1,2]]')).toBeNull();
    expect(parseRing('[["a","b"]]')).toBeNull();
  });
});

describe('describeRing', () => {
  it('is empty for nothing', () => {
    expect(describeRing(null)).toBe('');
  });

  it('says the box of the shape', () => {
    expect(describeRing(SQUARE)).toBe('88.20°–88.60°E · 23.00°–23.30°N');
  });
});
