/**
 * A drawn area of interest (FR-16).
 *
 * The shape is a ring of `[longitude, latitude]` pairs — the GeoJSON order,
 * so the same array can be sent to the API as it is stored in the hash.
 * The API does the real filtering; these helpers only carry the shape around
 * and decide what the user may draw.
 */

/** A ring of `[longitude, latitude]` pairs. */
export type Ring = [number, number][];

export const CUSTOM_AOI = 'custom';

/** The ring is closed by repeating the first point; a drawn one need not be. */
export function closeRing(ring: Ring): Ring {
  if (ring.length === 0) return ring;
  const [first, last] = [ring[0], ring[ring.length - 1]];
  if (first[0] === last[0] && first[1] === last[1]) return ring;
  return [...ring, first];
}

/** Is the point inside the ring? Ray casting, on the horizontal axis. */
export function pointInRing(lon: number, lat: number, ring: Ring): boolean {
  if (ring.length < 4) return false;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > lat !== yj > lat) {
      const xCross = ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
      if (lon <= xCross) inside = !inside;
    }
  }
  return inside;
}

/** Do two edges of the ring cross? A self-crossing ring is not an area. */
export function selfIntersects(ring: Ring): boolean {
  const closed = closeRing(ring);
  const n = closed.length - 1;
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (j === i + 1 || i === j + 1 || (i === 0 && j === n - 1) || (j === 0 && i === n - 1)) {
        continue;
      }
      if (segmentsCross(closed[i], closed[i + 1], closed[j], closed[j + 1])) return true;
    }
  }
  return false;
}

function cross(o: [number, number], a: [number, number], b: [number, number]): number {
  return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
}

function onSegment(
  a: [number, number],
  b: [number, number],
  p: [number, number],
): boolean {
  return (
    Math.min(a[0], b[0]) - 1e-12 <= p[0] &&
    p[0] <= Math.max(a[0], b[0]) + 1e-12 &&
    Math.min(a[1], b[1]) - 1e-12 <= p[1] &&
    p[1] <= Math.max(a[1], b[1]) + 1e-12
  );
}

function segmentsCross(
  a: [number, number],
  b: [number, number],
  c: [number, number],
  d: [number, number],
): boolean {
  const d1 = cross(a, b, c);
  const d2 = cross(a, b, d);
  const d3 = cross(c, d, a);
  const d4 = cross(c, d, b);
  if (d1 > 0 !== d2 > 0 && d3 > 0 !== d4 > 0) return true;
  return (
    (d1 === 0 && onSegment(a, b, c)) ||
    (d2 === 0 && onSegment(a, b, d)) ||
    (d3 === 0 && onSegment(c, d, a)) ||
    (d4 === 0 && onSegment(c, d, b))
  );
}

/**
 * Can the ring be drawn?
 *
 * The same rules the API applies, so a shape the UI accepts is a shape the
 * API honours: three points at least, not crossing itself, and not flat.
 */
export function isUsableRing(ring: Ring): boolean {
  if (ring.length < 3) return false;
  if (selfIntersects(ring)) return false;
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  const west = Math.min(...lons);
  const east = Math.max(...lons);
  const south = Math.min(...lats);
  const north = Math.max(...lats);
  return west < east && south < north;
}

/** The bounding box of the ring, as `[west, south, east, north]`. */
export function ringBbox(ring: Ring): [number, number, number, number] {
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
}

/** The ring as the API wants it: a JSON list of `[lon, lat]` pairs. */
export function polygonParam(ring: Ring | null): string | null {
  if (!ring || ring.length === 0) return null;
  return JSON.stringify(ring);
}

/** The ring, read back out of a hash value. `null` when it is not one. */
export function parseRing(raw: string | null): Ring | null {
  if (!raw) return null;
  try {
    const decoded: unknown = JSON.parse(raw);
    if (!Array.isArray(decoded)) return null;
    const ring: Ring = [];
    for (const position of decoded) {
      if (!Array.isArray(position) || position.length !== 2) return null;
      const [lon, lat] = position;
      if (typeof lon !== 'number' || typeof lat !== 'number') return null;
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
      ring.push([lon, lat]);
    }
    return ring.length >= 3 ? ring : null;
  } catch {
    return null;
  }
}

/** A short label for the drawn shape, for the region chip. */
export function describeRing(ring: Ring | null): string {
  if (!ring || ring.length === 0) return '';
  const [west, south, east, north] = ringBbox(ring);
  const digits = (value: number) => value.toFixed(2);
  return `${digits(west)}°–${digits(east)}°E · ${digits(south)}°–${digits(north)}°N`;
}
