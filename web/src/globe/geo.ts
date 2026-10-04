/**
 * Pure geography helpers for the hero globe.
 *
 * Everything here is deterministic and free of Three.js and of the DOM, so
 * the same numbers can be unit-tested without a GPU: the land mask decodes
 * to a bit array, lat/lon becomes a point on the sphere, and a rotation that
 * brings a coordinate to the front of the camera is arithmetic, not state.
 *
 * Sphere convention (right-handed, Y up):
 *   x = r·cos(lat)·sin(lon),  y = r·sin(lat),  z = r·cos(lat)·cos(lon)
 * so (0°, 0°) sits on +Z — the default camera direction.
 */

/** Decode standard base64 into bytes without depending on `atob`. */
export function base64ToBytes(base64: string): Uint8Array {
  const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  const lookup = new Int16Array(256).fill(-1);
  for (let i = 0; i < ALPHABET.length; i++) lookup[ALPHABET.charCodeAt(i)] = i;

  const clean = base64.replace(/[^A-Za-z0-9+/]/g, "");
  const out = new Uint8Array(Math.floor((clean.length * 6) / 8));
  let acc = 0;
  let accBits = 0;
  let outIndex = 0;
  for (let i = 0; i < clean.length; i++) {
    const value = lookup[clean.charCodeAt(i)];
    if (value < 0) continue;
    acc = (acc << 6) | value;
    accBits += 6;
    if (accBits >= 8) {
      accBits -= 8;
      out[outIndex++] = (acc >> accBits) & 0xff;
    }
  }
  return out;
}

/**
 * A land mask on an equirectangular grid: bit `index` is 1 where the cell
 * centre is land. `index = row · width + col`, most-significant bit first
 * within each byte, row 0 = 90°N, col 0 = 180°W.
 */
export interface LandMask {
  width: number;
  height: number;
  bits: Uint8Array;
}

export function decodeLandMask(base64: string, width: number, height: number): LandMask {
  const bytes = base64ToBytes(base64);
  const expected = Math.ceil((width * height) / 8);
  if (bytes.length < expected) {
    throw new Error(`Land mask is ${bytes.length} bytes, expected ${expected}`);
  }
  return { width, height, bits: bytes };
}

export function isLand(mask: LandMask, row: number, col: number): boolean {
  if (row < 0 || row >= mask.height || col < 0 || col >= mask.width) return false;
  const index = row * mask.width + col;
  return ((mask.bits[index >> 3] >> (7 - (index & 7))) & 1) === 1;
}

/** Centre of a mask cell, in degrees. */
export function cellCentre(mask: LandMask, row: number, col: number): { lat: number; lon: number } {
  return {
    lat: 90 - ((row + 0.5) * 180) / mask.height,
    lon: -180 + ((col + 0.5) * 360) / mask.width,
  };
}

export type Vec3 = [number, number, number];

export function latLonToVec3(lat: number, lon: number, radius: number): Vec3 {
  const phi = (lat * Math.PI) / 180;
  const lambda = (lon * Math.PI) / 180;
  const cosPhi = Math.cos(phi);
  return [
    radius * cosPhi * Math.sin(lambda),
    radius * Math.sin(phi),
    radius * cosPhi * Math.cos(lambda),
  ];
}

/** Centre of a `[west, south, east, north]` bounding box. */
export function bboxCentre(bounds: readonly [number, number, number, number]): {
  lat: number;
  lon: number;
} {
  const [west, south, east, north] = bounds;
  return { lat: (south + north) / 2, lon: (west + east) / 2 };
}

/**
 * Group rotation that brings a coordinate to the front of the camera, for a
 * group whose default Euler order is XYZ (three.js applies Rx·Ry·Rz).
 */
export function rotationToFace(lat: number, lon: number): { x: number; y: number } {
  return { x: (lat * Math.PI) / 180, y: (-lon * Math.PI) / 180 };
}

/** Closed ring of points tracing a bounding box along the sphere surface. */
export function bboxOutline(
  bounds: readonly [number, number, number, number],
  radius: number,
  stepsPerEdge = 12,
): Vec3[] {
  const [west, south, east, north] = bounds;
  const points: Vec3[] = [];
  const edge = (fromLat: number, fromLon: number, toLat: number, toLon: number): void => {
    for (let i = 0; i < stepsPerEdge; i++) {
      const t = i / stepsPerEdge;
      points.push(
        latLonToVec3(fromLat + (toLat - fromLat) * t, fromLon + (toLon - fromLon) * t, radius),
      );
    }
  };
  edge(south, west, south, east);
  edge(south, east, north, east);
  edge(north, east, north, west);
  edge(north, west, south, west);
  return points;
}

/** Line-segment pairs for a lat/lon graticule. */
export function graticuleSegments(
  radius: number,
  latStep = 15,
  lonStep = 15,
  segments = 72,
): Float32Array {
  const out: number[] = [];
  const push = (a: Vec3, b: Vec3): void => {
    out.push(a[0], a[1], a[2], b[0], b[1], b[2]);
  };
  for (let lat = -90 + latStep; lat < 90; lat += latStep) {
    for (let i = 0; i < segments; i++) {
      push(
        latLonToVec3(lat, (i / segments) * 360 - 180, radius),
        latLonToVec3(lat, ((i + 1) / segments) * 360 - 180, radius),
      );
    }
  }
  for (let lon = -180; lon < 180; lon += lonStep) {
    for (let i = 0; i < segments / 2; i++) {
      push(
        latLonToVec3((i / (segments / 2)) * 180 - 90, lon, radius),
        latLonToVec3(((i + 1) / (segments / 2)) * 180 - 90, lon, radius),
      );
    }
  }
  return Float32Array.from(out);
}

/** Deterministic PRNG (mulberry32) so every build renders the same scene. */
export function seededRandom(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Shortest-path interpolation between two angles, in radians. */
export function lerpAngle(from: number, to: number, t: number): number {
  let delta = (to - from) % (Math.PI * 2);
  if (delta > Math.PI) delta -= Math.PI * 2;
  if (delta < -Math.PI) delta += Math.PI * 2;
  return from + delta * t;
}
