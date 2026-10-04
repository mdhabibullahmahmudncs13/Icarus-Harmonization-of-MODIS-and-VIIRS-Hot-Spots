/**
 * The globe's numbers, tested without a GPU.
 *
 * These are the checks that catch the failure that would actually ship: a
 * land mask that decodes to the wrong hemisphere, a rotation that points the
 * camera at the wrong side of the planet, or a cell centroid computed from
 * the wrong corner of its bounding box.
 */
import { describe, expect, it } from "vitest";
import { LAND_MASK_BITS_BASE64, LAND_MASK_HEIGHT, LAND_MASK_WIDTH } from "../../src/landmask";
import {
  base64ToBytes,
  bboxCentre,
  bboxOutline,
  cellCentre,
  decodeLandMask,
  graticuleSegments,
  isLand,
  latLonToVec3,
  lerpAngle,
  rotationToFace,
  seededRandom,
} from "../../src/globe/geo";
import { spotsFromCells, topSpots, totalFor } from "../../src/globe/hotspots";
import type { CellsResponse } from "../../src/contract";

const mask = decodeLandMask(LAND_MASK_BITS_BASE64, LAND_MASK_WIDTH, LAND_MASK_HEIGHT);

/** Mask cell containing a coordinate, matching the generator's convention. */
function at(lat: number, lon: number): boolean {
  const row = Math.min(
    LAND_MASK_HEIGHT - 1,
    Math.max(0, Math.floor(((90 - lat) * LAND_MASK_HEIGHT) / 180)),
  );
  const col = Math.min(
    LAND_MASK_WIDTH - 1,
    Math.max(0, Math.floor(((lon + 180) * LAND_MASK_WIDTH) / 360)),
  );
  return isLand(mask, row, col);
}

/** Apply three.js's XYZ Euler order to a vector: Rx then Ry. */
function rotate(v: [number, number, number], rotation: { x: number; y: number }): number[] {
  const [x, y, z] = v;
  const cy = Math.cos(rotation.y);
  const sy = Math.sin(rotation.y);
  const x1 = x * cy + z * sy;
  const z1 = -x * sy + z * cy;
  const cx = Math.cos(rotation.x);
  const sx = Math.sin(rotation.x);
  return [x1, y * cx - z1 * sx, y * sx + z1 * cx];
}

describe("land mask", () => {
  it("decodes to the declared grid", () => {
    expect(mask.width).toBe(360);
    expect(mask.height).toBe(180);
    expect(base64ToBytes(LAND_MASK_BITS_BASE64).length).toBe(Math.ceil((360 * 180) / 8));
  });

  it("holds a plausible amount of land", () => {
    let land = 0;
    for (let row = 0; row < mask.height; row++) {
      for (let col = 0; col < mask.width; col++) if (isLand(mask, row, col)) land++;
    }
    const fraction = land / (mask.width * mask.height);
    // Earth is about 29% land at 1° resolution; a hemisphere-flip or a
    // transposed mask would land far outside this band.
    expect(fraction).toBeGreaterThan(0.24);
    expect(fraction).toBeLessThan(0.36);
  });

  it("puts the continents where they are", () => {
    // On land.
    expect(at(23, 10)).toBe(true); // Sahara
    expect(at(-5, -60)).toBe(true); // Amazon basin
    expect(at(50, 90)).toBe(true); // Central Asia
    expect(at(23.5, 90.5)).toBe(true); // the study region is land, not ocean
    // Not on land.
    expect(at(0, -140)).toBe(false); // mid Pacific
    expect(at(30, -40)).toBe(false); // mid Atlantic
    expect(at(-60, -20)).toBe(false); // Southern Ocean
  });

  it("rejects a truncated mask instead of rendering a partial world", () => {
    expect(() => decodeLandMask(LAND_MASK_BITS_BASE64.slice(0, 40), 360, 180)).toThrow();
  });
});

describe("sphere geometry", () => {
  it("maps lat/lon onto the unit sphere with the declared convention", () => {
    const origin = latLonToVec3(0, 0, 1);
    expect(origin[0]).toBeCloseTo(0, 10);
    expect(origin[1]).toBeCloseTo(0, 10);
    expect(origin[2]).toBeCloseTo(1, 10);
    const north = latLonToVec3(90, 0, 1);
    expect(north[1]).toBeCloseTo(1, 10);
    expect(Math.hypot(...latLonToVec3(-37, 144, 2.5))).toBeCloseTo(2.5, 10);
  });

  it("turns a coordinate to the front of the camera", () => {
    for (const [lat, lon] of [
      [23.5, 90.5],
      [0, 0],
      [-33.9, 151.2],
      [64.1, -21.9],
    ] as const) {
      const rotated = rotate(latLonToVec3(lat, lon, 1), rotationToFace(lat, lon));
      expect(rotated[0]).toBeCloseTo(0, 6);
      expect(rotated[1]).toBeCloseTo(0, 6);
      expect(rotated[2]).toBeCloseTo(1, 6);
    }
  });

  it("traces the region ring on the sphere surface", () => {
    const ring = bboxOutline([88, 20, 93, 27], 1.02);
    expect(ring).toHaveLength(48);
    for (const point of ring) expect(Math.hypot(...point)).toBeCloseTo(1.02, 6);
  });

  it("keeps the graticule on its shell", () => {
    const segments = graticuleSegments(1.0015);
    expect(segments.length % 6).toBe(0);
    for (let i = 0; i < segments.length; i += 3) {
      expect(Math.hypot(segments[i], segments[i + 1], segments[i + 2])).toBeCloseTo(1.0015, 5);
    }
  });

  it("is deterministic", () => {
    const a = seededRandom(7);
    const b = seededRandom(7);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });

  it("interpolates angles the short way round", () => {
    const near = Math.PI * 2 - 0.1;
    const wrapped = (angle: number): number =>
      ((angle % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
    // 6.18 rad and 0.1 rad are 0.2 rad apart the short way, not 6.08 the long way.
    expect(wrapped(lerpAngle(near, 0.1, 1))).toBeCloseTo(0.1, 9);
    expect(Math.abs(lerpAngle(near, 0.1, 1) - near)).toBeLessThan(Math.PI);
  });
});

describe("cells on the globe", () => {
  const cells = {
    rows: [
      { cell_id: "a", bounds: [88, 20, 88.05, 20.05], raw: 40, harmonized: 12, peak_frp: 100 },
      { cell_id: "b", bounds: [90, 24, 90.05, 24.05], raw: 7, harmonized: 45, peak_frp: 30 },
    ],
  } as unknown as CellsResponse;

  it("uses the centre of the cell's own bounds", () => {
    expect(bboxCentre([88, 20, 88.05, 20.05]).lat).toBeCloseTo(20.025, 9);
    expect(bboxCentre([88, 20, 88.05, 20.05]).lon).toBeCloseTo(88.025, 9);
    const spots = spotsFromCells(cells);
    expect(spots.map((s) => s.id)).toEqual(["a", "b"]);
    expect(spots[0].lat).toBeCloseTo(20.025, 9);
  });

  it("orders by the active mode, not by a fixed column", () => {
    const spots = spotsFromCells(cells);
    expect(topSpots(spots, 1, "raw")[0].id).toBe("a");
    expect(topSpots(spots, 1, "harmonized")[0].id).toBe("b");
    expect(totalFor(spots, "raw")).toBe(47);
    expect(totalFor(spots, "harmonized")).toBe(57);
  });

  it("describes its own cell grid rather than the mask", () => {
    const centre = cellCentre(mask, 0, 0);
    expect(centre.lat).toBeCloseTo(89.5, 6);
    expect(centre.lon).toBeCloseTo(-179.5, 6);
  });
});
