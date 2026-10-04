/**
 * gen-landmask.ts — one-time generator for the globe's land mask.
 *
 * Reads the Natural Earth 1:110m land polygons (public domain) from
 * `scripts/data/land-110m.json` (world-atlas TopoJSON) and rasterises them
 * onto a regular equirectangular grid: one bit per cell, raw row 0 = 90°N,
 * column 0 = 180°W. The result is written to `src/landmask.ts` so the globe
 * ships the mask it draws and never touches the network at runtime.
 *
 * Run: npm run land:gen   (offline — the input file is committed)
 *
 * Source: Natural Earth, https://www.naturalearthdata.com/ (public domain),
 * packaged as TopoJSON by world-atlas (ISC).
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { geoContains } from "d3-geo";
import { feature } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import type { Feature, FeatureCollection, Geometry } from "geojson";

const HERE = dirname(fileURLToPath(import.meta.url));
const INPUT = join(HERE, "data", "land-110m.json");
const OUTPUT = join(HERE, "..", "src", "landmask.ts");

/** Grid resolution in degrees per cell (1° = 360 × 180 = 64 800 cells). */
const DEG = 1;
const WIDTH = Math.round(360 / DEG);
const HEIGHT = Math.round(180 / DEG);

/** Sample the cell centre: lon = -180 + (col + 0.5) * DEG, lat = 90 - (row + 0.5) * DEG. */
function cellCentre(row: number, col: number): [number, number] {
  const lon = -180 + (col + 0.5) * DEG;
  const lat = 90 - (row + 0.5) * DEG;
  return [lon, lat];
}

function main(): void {
  const raw = JSON.parse(readFileSync(INPUT, "utf8")) as Topology;
  const land = feature(raw, raw.objects.land as GeometryCollection) as
    FeatureCollection<Geometry> | Feature<Geometry>;
  const features: Feature<Geometry>[] = "features" in land ? land.features : [land];

  const bits = new Uint8Array(Math.ceil((WIDTH * HEIGHT) / 8));
  let landCells = 0;
  for (let row = 0; row < HEIGHT; row++) {
    for (let col = 0; col < WIDTH; col++) {
      const [lon, lat] = cellCentre(row, col);
      if (!features.some((f) => geoContains(f, [lon, lat]))) continue;
      const i = row * WIDTH + col;
      bits[i >> 3] |= 1 << (7 - (i & 7));
      landCells++;
    }
  }

  const base64 = Buffer.from(bits).toString("base64");
  const source = `/**
 * GENERATED — do not edit by hand.
 *
 * Land mask for the globe, ${DEG}° cells on an equirectangular grid
 * (${WIDTH} × ${HEIGHT} = ${WIDTH * HEIGHT} cells, ${landCells} land).
 *
 * Reproduce with \`npm run land:gen\` from \`scripts/gen-landmask.ts\`.
 * Source data: Natural Earth 1:110m land (public domain,
 * https://www.naturalearthdata.com/), packaged as TopoJSON by world-atlas
 * (ISC); the input is committed at \`scripts/data/land-110m.json\`.
 *
 * Bit order: index = row * LAND_MASK_WIDTH + col, row 0 = 90°N,
 * col 0 = 180°W, most-significant bit first within each byte.
 */
export const LAND_MASK_WIDTH = ${WIDTH};
export const LAND_MASK_HEIGHT = ${HEIGHT};
export const LAND_MASK_BITS_BASE64 =
  "${base64}";
`;
  writeFileSync(OUTPUT, source, "utf8");
  process.stdout.write(
    `wrote ${OUTPUT}: ${WIDTH}x${HEIGHT}, ${landCells} land cells, ${base64.length} base64 chars\n`,
  );
}

main();
