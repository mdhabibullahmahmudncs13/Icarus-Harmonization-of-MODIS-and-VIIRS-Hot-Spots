/**
 * Icarus mock data generator — `npm run mock:gen`.
 *
 * MOCK DATA IS NEVER EVIDENCE (Implementation plan, principle 3). This is
 * the one place in the frontend workspace allowed to generate numbers, and
 * everything it writes is labelled `meta.source: "mock"` so the UI can show
 * the persistent "Mock data" banner.
 *
 * Deterministic: seeded mulberry32 PRNG, fixed generated_at timestamp.
 * Running it twice produces byte-identical files.
 *
 * Method (Implementation plan, section 4.2):
 *   1. Generate cell-day records FIRST on a grid over the region box.
 *   2. Sensors "detect" those latent cell-days.
 *   3. Aggregate the detection records into series, cells, baseline,
 *      anomaly, validation and methods, so every file agrees with every
 *      other file.
 *   4. Validate every payload against the zod contract (fail loudly).
 *
 * Everything numeric here is synthetic. The spatial blobs, seasonal curve
 * and epoch dates are assumptions for mock purposes only — no real
 * geography, no real climatology, no verified facts.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { endpoints, type EndpointPayloads } from "../src/contract/schemas";

/* ------------------------------------------------------------------ */
/* Constants                                                           */
/* ------------------------------------------------------------------ */

const SEED = 20261004;

/** Bangladesh box [west, south, east, north] — plan section 2. */
const BBOX: [number, number, number, number] = [88, 20, 93, 27];
const CELL_KM = 5.5;
const MIN_CONFIDENCE = 50;
/** Default grid cell 5.5 km; this mock keeps it configurable via constants. */
const CENTER_LAT = (BBOX[1] + BBOX[3]) / 2; // 23.5°N — used for the grid steps

const START = "2003-01-01";
const END = "2026-09-30";
const VIIRS_START = "2012-01-01"; // TODO verify against FIRMS docs

/** Fixed so regeneration is byte-identical. Bump manually when regenerating. */
const MOCK_GENERATED_AT = "2026-10-04T00:00:00Z";

/** Latent cell-days per day at peak season, before year variation. */
const BASE_RATE = 160;
/** Post-confidence-filter probability a latent cell-day is seen by MODIS-like sensor. */
const F_MODIS = 0.35;
/** Post-confidence-filter probability for the VIIRS-like sensor (higher fraction, finer sensor). */
const F_VIIRS = 0.4; // only from 2012 onward
/** VIIRS detections per detected cell-day: 1 + Bernoulli probs -> mean 1.85, range 1..4. */
const K_PROBS = [0.5, 0.25, 0.1];
const BASELINE_WINDOW_DAYS = 7;

/**
 * Sensor epochs. PLACEHOLDER DATES — every line below is a
 * TODO verify against FIRMS docs. Do not present these as facts in the UI.
 */
const SENSORS = [
  { product: "MODIS C6.1 hotspots", family: "MODIS", start: "2003-01-01", end: "2026-09-30" }, // TODO verify against FIRMS docs
  { product: "VIIRS 375 m Suomi-NPP", family: "VIIRS", start: "2012-01-01", end: "2026-11-01" }, // TODO verify against FIRMS docs
  { product: "VIIRS 375 m NOAA-20", family: "VIIRS", start: "2017-01-01", end: null }, // TODO verify against FIRMS docs
  { product: "VIIRS 375 m NOAA-21", family: "VIIRS", start: "2024-01-01", end: null }, // TODO verify against FIRMS docs
] as const;

/* ------------------------------------------------------------------ */
/* Deterministic PRNG and date helpers                                 */
/* ------------------------------------------------------------------ */

/** mulberry32 — seeded, reproducible, tiny. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const DAY_MS = 86400000;
const startMs = Date.parse(`${START}T00:00:00Z`);
const endMs = Date.parse(`${END}T00:00:00Z`);
const viirsStartMs = Date.parse(`${VIIRS_START}T00:00:00Z`);

function isoDate(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

function dayOfYear(ms: number): number {
  const d = new Date(ms);
  const yearStart = Date.UTC(d.getUTCFullYear(), 0, 1);
  return Math.floor((ms - yearStart) / DAY_MS) + 1;
}

/** Standard normal via Box–Muller (uses two uniforms). */
function gauss(rng: () => number): number {
  const u = Math.max(rng(), Number.EPSILON);
  const v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

/* ------------------------------------------------------------------ */
/* Grid over the region box                                            */
/* ------------------------------------------------------------------ */

// Latitude step for 5.5 km: 5.5 / 111 degrees.
const LAT_STEP = CELL_KM / 111;
// Longitude step scaled by cos(center latitude): at 23.5°N one degree of
// longitude is 111·cos(23.5°) km, so dividing the step by cos keeps cells
// close to the stated 5.5 km width (same approximation as src/compute plans;
// documented as an approximation, not a geodesic truth).
const LON_STEP = LAT_STEP / Math.cos((CENTER_LAT * Math.PI) / 180);

const N_ROWS = Math.floor((BBOX[3] - BBOX[1]) / LAT_STEP);
const N_COLS = Math.floor((BBOX[2] - BBOX[0]) / LON_STEP);
const N_CELLS = N_ROWS * N_COLS;

function cellBounds(row: number, col: number): [number, number, number, number] {
  const w = BBOX[0] + col * LON_STEP;
  const s = BBOX[1] + row * LAT_STEP;
  return [round(w, 6), round(s, 6), round(w + LON_STEP, 6), round(s + LAT_STEP, 6)];
}

function cellId(row: number, col: number): string {
  return `r${String(row).padStart(3, "0")}c${String(col).padStart(3, "0")}`;
}

function round(x: number, digits: number): number {
  const f = 10 ** digits;
  return Math.round(x * f) / f;
}

/* ------------------------------------------------------------------ */
/* Latent fire shape — ASSUMPTION FOR MOCK PURPOSES ONLY.              */
/* ------------------------------------------------------------------ */

// The seasonal curve and the spatial blobs below are arbitrary mock
// assumptions. They make no real-geography claims about Bangladesh: blob
// positions are invented purely so the map has structure.

const SEASON_PEAK_DOY = 75; // dry-season peak around mid-March
const SEASON_SIGMA = 38;
const SEASON_FLOOR = 0.06;

/** Weighted arbitrary intensity blobs, in cell coordinates. */
const BLOBS = [
  { row: 35, col: 25, sigma: 14, weight: 0.4 },
  { row: 75, col: 55, sigma: 16, weight: 0.35 },
  { row: 110, col: 70, sigma: 12, weight: 0.25 },
] as const;

function seasonalWeight(doy: number): number {
  const bump = Math.exp(-0.5 * ((doy - SEASON_PEAK_DOY) / SEASON_SIGMA) ** 2);
  return SEASON_FLOOR + (1 - SEASON_FLOOR) * bump;
}

function pickBlob(rng: () => number): (typeof BLOBS)[number] {
  let u = rng();
  for (const blob of BLOBS) {
    u -= blob.weight;
    if (u <= 0) return blob;
  }
  return BLOBS[BLOBS.length - 1];
}

/* ------------------------------------------------------------------ */
/* Statistics helpers (mock-only; the real ones live in src/compute)   */
/* ------------------------------------------------------------------ */

function mean(xs: number[]): number {
  if (xs.length === 0) return 0;
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

function pearson(xs: number[], ys: number[]): number {
  const n = xs.length;
  if (n === 0) return 0;
  const mx = mean(xs);
  const my = mean(ys);
  let num = 0;
  let dx = 0;
  let dy = 0;
  for (let i = 0; i < n; i++) {
    const a = xs[i] - mx;
    const b = ys[i] - my;
    num += a * b;
    dx += a * a;
    dy += b * b;
  }
  const den = Math.sqrt(dx * dy);
  return den === 0 ? 0 : num / den;
}

/** Average ranks, 1-based, ties share the mean rank. */
function ranks(xs: number[]): number[] {
  const idx = xs.map((_, i) => i).sort((a, b) => xs[a] - xs[b]);
  const out = new Array<number>(xs.length).fill(0);
  let i = 0;
  while (i < idx.length) {
    let j = i;
    while (j + 1 < idx.length && xs[idx[j + 1]] === xs[idx[i]]) j++;
    const avg = (i + j) / 2 + 1;
    for (let k = i; k <= j; k++) out[idx[k]] = avg;
    i = j + 1;
  }
  return out;
}

function spearman(xs: number[], ys: number[]): number {
  return pearson(ranks(xs), ranks(ys));
}

/** Linear-interpolation percentile of a sorted array, p in [0, 1]. */
function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const idx = (sorted.length - 1) * p;
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

/* ------------------------------------------------------------------ */
/* Phase 1: latent cell-days, sensor detections                        */
/* ------------------------------------------------------------------ */

interface Detection {
  day: number; // index into the day list
  cell: number; // flat cell index
  modis: boolean; // MODIS-like sensor detected this cell-day (1 detection)
  viirsK: number; // VIIRS-like detections for this cell-day (0 if none)
}

function buildDays(): number[] {
  const days: number[] = [];
  for (let t = startMs; t <= endMs; t += DAY_MS) days.push(t);
  return days;
}

function generateDetections(days: number[]): Detection[] {
  const rng = mulberry32(SEED);

  // Year-to-year variation: one multiplier per year, mean ~1.
  const yearMult = new Map<number, number>();
  for (let y = new Date(startMs).getUTCFullYear(); y <= new Date(endMs).getUTCFullYear(); y++) {
    yearMult.set(y, 0.75 + rng() * 0.5);
  }

  const detections: Detection[] = [];

  for (let d = 0; d < days.length; d++) {
    const ms = days[d];
    const doy = dayOfYear(ms);
    const year = new Date(ms).getUTCFullYear();
    const latent = Math.round(BASE_RATE * seasonalWeight(doy) * (yearMult.get(year) ?? 1));
    const viirsOn = ms >= viirsStartMs;

    const seenThisDay = new Set<number>();
    for (let i = 0; i < latent; i++) {
      // Spatial: pick a blob, jitter in cell units, clamp to the grid.
      const blob = pickBlob(rng);
      const row = Math.min(N_ROWS - 1, Math.max(0, Math.round(blob.row + gauss(rng) * blob.sigma)));
      const col = Math.min(N_COLS - 1, Math.max(0, Math.round(blob.col + gauss(rng) * blob.sigma)));
      const cell = row * N_COLS + col;
      // One cell-day per cell per day: repeated hits collapse to the same
      // latent cell-day (this is exactly the harmonization rule, applied
      // during generation so series/cells/calendar always agree).
      if (seenThisDay.has(cell)) continue;
      seenThisDay.add(cell);

      // Shared uniform nests the sensors: the finer VIIRS-like sensor sees
      // a superset of the MODIS-like cell-days, which is what keeps
      // harmonized counts comparable across the transition.
      const v = rng();
      const modis = v < F_MODIS;
      const viirs = viirsOn && v < F_VIIRS;
      if (!modis && !viirs) continue;

      let k = 0;
      if (viirs) {
        k = 1;
        for (const p of K_PROBS) if (rng() < p) k += 1;
      }
      detections.push({ day: d, cell, modis, viirsK: k });
    }
  }
  return detections;
}

/* ------------------------------------------------------------------ */
/* Phase 2: aggregate into endpoint payloads                           */
/* ------------------------------------------------------------------ */

function baseMeta() {
  return {
    source: "mock" as const,
    generated_at: MOCK_GENERATED_AT,
    region: { bbox: BBOX },
    cell_km: CELL_KM,
    min_confidence: MIN_CONFIDENCE,
    date_range: [START, END] as [string, string],
  };
}

function buildSeries(days: number[], detections: Detection[]): EndpointPayloads["series"] {
  const n = days.length;
  const rawM = new Array<number>(n).fill(0);
  const rawV = new Array<number>(n).fill(0);
  const harmM = new Array<number>(n).fill(0);
  const harmV = new Array<number>(n).fill(0);
  const harmTot = new Array<number>(n).fill(0);

  for (const det of detections) {
    if (det.modis) {
      rawM[det.day] += 1;
      harmM[det.day] += 1; // MODIS-like sensor: one detection per cell-day
    }
    if (det.viirsK > 0) {
      rawV[det.day] += det.viirsK;
      harmV[det.day] += 1;
    }
    if (det.modis || det.viirsK > 0) harmTot[det.day] += 1; // union, not sum
  }

  const rows = days.map((ms, d) => ({
    date: isoDate(ms),
    raw_modis: rawM[d],
    raw_viirs: rawV[d],
    raw_total: rawM[d] + rawV[d],
    harm_modis: harmM[d],
    harm_viirs: harmV[d],
    // harm_total = distinct cell-days detected by ANY sensor that day
    // (union), so parts do not necessarily sum to the total.
    harm_total: harmTot[d],
  }));

  return { meta: baseMeta(), rows };
}

function buildCells(detections: Detection[]): EndpointPayloads["cells"] {
  const raw = new Array<number>(N_CELLS).fill(0);
  const harm = new Array<number>(N_CELLS).fill(0);
  const peak = new Array<number>(N_CELLS).fill(0);
  const rng = mulberry32(SEED + 1);

  for (const det of detections) {
    const nDet = (det.modis ? 1 : 0) + det.viirsK;
    if (nDet > 0) raw[det.cell] += nDet;
    if (det.modis || det.viirsK > 0) harm[det.cell] += 1;
    for (let i = 0; i < nDet; i++) {
      // Mock FRP: skewed positive values in MW. Arbitrary, mock only.
      const frp = round(2 + rng() ** 3 * 180, 1);
      if (frp > peak[det.cell]) peak[det.cell] = frp;
    }
  }

  const rows = [];
  for (let cell = 0; cell < N_CELLS; cell++) {
    if (raw[cell] === 0) continue;
    rows.push({
      cell_id: cellId(Math.floor(cell / N_COLS), cell % N_COLS),
      bounds: cellBounds(Math.floor(cell / N_COLS), cell % N_COLS),
      raw: raw[cell],
      harmonized: harm[cell],
      peak_frp: peak[cell],
    });
  }
  return { meta: baseMeta(), rows };
}

/** Circular day-of-year distance over a 366-day year. */
function doyDistance(a: number, b: number): number {
  const d = Math.abs(a - b);
  return Math.min(d, 366 - d);
}

function baselineSamplesFor(doy: number, days: number[], harmTot: number[]): number[] {
  const samples: number[] = [];
  for (let i = 0; i < days.length; i++) {
    if (doyDistance(dayOfYear(days[i]), doy) <= BASELINE_WINDOW_DAYS) samples.push(harmTot[i]);
  }
  return samples;
}

function buildBaseline(days: number[], harmTot: number[]): EndpointPayloads["baseline"] {
  const rows = [];
  for (let doy = 1; doy <= 366; doy++) {
    const sorted = baselineSamplesFor(doy, days, harmTot).sort((a, b) => a - b);
    rows.push({
      doy,
      p05: round(percentile(sorted, 0.05), 1),
      p25: round(percentile(sorted, 0.25), 1),
      p50: round(percentile(sorted, 0.5), 1),
      p75: round(percentile(sorted, 0.75), 1),
      p95: round(percentile(sorted, 0.95), 1),
    });
  }
  const yearsUsed = new Set(days.map((ms) => new Date(ms).getUTCFullYear())).size;
  return { meta: baseMeta(), window_days: BASELINE_WINDOW_DAYS, years_used: yearsUsed, rows };
}

function buildAnomaly(days: number[], harmTot: number[]): EndpointPayloads["anomaly"] {
  // One fixed sample date so the mock payload is deterministic.
  const date = "2024-03-15";
  const idx = days.findIndex((ms) => isoDate(ms) === date);
  if (idx < 0) throw new Error(`mock: sample date ${date} outside range`);
  const doy = dayOfYear(days[idx]);
  const samples = baselineSamplesFor(doy, days, harmTot).sort((a, b) => a - b);
  const value = harmTot[idx];
  const belowOrEqual = samples.filter((x) => x <= value).length;
  const yearsUsed = new Set(days.map((ms) => new Date(ms).getUTCFullYear())).size;

  return {
    meta: baseMeta(),
    date,
    value,
    percentile: round((100 * belowOrEqual) / samples.length, 1),
    baseline_window: BASELINE_WINDOW_DAYS,
    doy_range: [Math.max(1, doy - BASELINE_WINDOW_DAYS), Math.min(366, doy + BASELINE_WINDOW_DAYS)],
    years_used: yearsUsed,
  };
}

function buildValidation(
  days: number[],
  detections: Detection[],
  series: EndpointPayloads["series"],
): EndpointPayloads["validation"] {
  const overlapStartMs = Math.max(startMs, viirsStartMs);
  const overlapIdx = days.map((ms, i) => ({ ms, i })).filter((x) => x.ms >= overlapStartMs);
  const idxs = overlapIdx.map((x) => x.i);

  const rawM = idxs.map((i) => series.rows[i].raw_modis);
  const rawV = idxs.map((i) => series.rows[i].raw_viirs);
  const harmM = idxs.map((i) => series.rows[i].harm_modis);
  const harmV = idxs.map((i) => series.rows[i].harm_viirs);
  const rawPearson = pearson(rawM, rawV);
  const harmPearson = pearson(harmM, harmV);

  const ratio = (a: number[], b: number[]): number => {
    const ma = mean(a);
    return ma === 0 ? 0 : mean(b) / ma;
  };

  // Cell-size sweep: coarsen the 5.5 km base grid by an integer factor and
  // recompute the harmonized correlation at each size. Raw counts do not
  // depend on the grid, so raw_pearson is identical across the sweep.
  const cell_sweep = [5.5, 11, 16.5, 22].map((cellKm) => {
    const factor = Math.max(1, Math.round(cellKm / CELL_KM));
    if (factor === 1) {
      return {
        cell_km: cellKm,
        raw_pearson: round(rawPearson, 4),
        harmonized_pearson: round(harmPearson, 4),
      };
    }
    const nCCols = Math.ceil(N_COLS / factor);
    const key = (day: number, coarse: number): number => day * 100000 + coarse;
    const modisSet = new Set<number>();
    const viirsSet = new Set<number>();
    const daySeenM = new Map<number, number>();
    const daySeenV = new Map<number, number>();
    for (const det of detections) {
      if (det.day < overlapIdx[0].i) continue;
      const coarse =
        Math.floor(Math.floor(det.cell / N_COLS) / factor) * nCCols +
        Math.floor((det.cell % N_COLS) / factor);
      if (det.modis) modisSet.add(key(det.day, coarse));
      if (det.viirsK > 0) viirsSet.add(key(det.day, coarse));
    }
    for (const k of modisSet)
      daySeenM.set(Math.floor(k / 100000), (daySeenM.get(Math.floor(k / 100000)) ?? 0) + 1);
    for (const k of viirsSet)
      daySeenV.set(Math.floor(k / 100000), (daySeenV.get(Math.floor(k / 100000)) ?? 0) + 1);
    const cm: number[] = [];
    const cv: number[] = [];
    for (const i of idxs) {
      cm.push(daySeenM.get(i) ?? 0);
      cv.push(daySeenV.get(i) ?? 0);
    }
    return {
      cell_km: cellKm,
      raw_pearson: round(rawPearson, 4),
      harmonized_pearson: round(pearson(cm, cv), 4),
    };
  });

  return {
    meta: baseMeta(),
    overlap: { start: isoDate(overlapStartMs), end: END },
    raw: {
      pearson: round(rawPearson, 4),
      spearman: round(spearman(rawM, rawV), 4),
      ratio: round(ratio(rawM, rawV), 4),
    },
    harmonized: {
      pearson: round(harmPearson, 4),
      spearman: round(spearman(harmM, harmV), 4),
      ratio: round(ratio(harmM, harmV), 4),
    },
    cell_sweep,
  };
}

function buildMethods(): EndpointPayloads["methods"] {
  return {
    meta: baseMeta(),
    cell_km: CELL_KM,
    min_confidence: MIN_CONFIDENCE,
    // FIRMS_VIIRS_NOAA20 confidence mapping: low/nominal/high -> 25/60/90.
    confidence_mapping: { l: 25, n: 60, h: 90 },
    collapse_rule:
      `Detections are assigned to ${CELL_KM} km grid cells by their coordinates, ` +
      `with longitude steps scaled by cos(latitude) so cells stay close to the ` +
      `stated size (an approximation, not a geodesic). Within each cell and ` +
      `calendar day all detections collapse to one cell-day. The harmonized ` +
      `daily count is the number of distinct cell-days detected by any sensor ` +
      `that day; the raw daily count is the number of detections.`,
    notices: [
      "Suomi-NPP VIIRS data ends 1 Nov 2026; NASA stops serving it after that date.",
      "MODIS is being retired; prefer VIIRS on NOAA-20 and NOAA-21 for continuity.",
      "Sensor epoch dates are placeholders pending verification against FIRMS docs.",
    ],
    datasets: [
      {
        id: "FIRMS_MODIS",
        product: "MODIS C6.1 hotspots",
        url: "https://firms.modaps.eosdis.nasa.gov/",
      },
      {
        id: "FIRMS_VIIRS_NOAA20",
        product: "VIIRS 375 m NOAA-20",
        url: "https://firms.modaps.eosdis.nasa.gov/",
      },
      {
        id: "FIRMS_VIIRS_NOAA21",
        product: "VIIRS 375 m NOAA-21",
        url: "https://firms.modaps.eosdis.nasa.gov/",
      },
      {
        id: "FIRMS_VIIRS_SNPP",
        product: "VIIRS 375 m Suomi-NPP",
        url: "https://firms.modaps.eosdis.nasa.gov/",
      },
    ],
  };
}

/* ------------------------------------------------------------------ */
/* Phase 3: validate + write                                           */
/* ------------------------------------------------------------------ */

function validate(name: keyof typeof endpoints, payload: unknown): void {
  const result = endpoints[name].safeParse(payload);
  if (!result.success) {
    console.error(`\nmock:gen FAILED contract validation for "${name}":`);
    for (const issue of result.error.issues) {
      console.error(`  ${issue.path.join(".")}: ${issue.message}`);
    }
    process.exit(1);
  }
}

function main(): void {
  const days = buildDays();
  const detections = generateDetections(days);

  const series = buildSeries(days, detections);
  const cells = buildCells(detections);
  const baseline = buildBaseline(
    days,
    series.rows.map((r) => r.harm_total),
  );
  const anomaly = buildAnomaly(
    days,
    series.rows.map((r) => r.harm_total),
  );
  const validation = buildValidation(days, detections, series);
  const meta: EndpointPayloads["meta"] = { meta: baseMeta(), sensors: [...SENSORS] };
  const methods = buildMethods();

  const files: Record<string, unknown> = {
    meta,
    series,
    cells,
    baseline,
    anomaly,
    validation,
    methods,
  };

  for (const [name, payload] of Object.entries(files)) {
    validate(name as keyof typeof endpoints, payload);
  }

  const outDir = resolve(dirname(fileURLToPath(import.meta.url)), "../public/mock");
  mkdirSync(outDir, { recursive: true });
  for (const [name, payload] of Object.entries(files)) {
    writeFileSync(resolve(outDir, `${name}.json`), JSON.stringify(payload, null, 2) + "\n", "utf8");
  }

  // One-line summary: raw vs harmonized VIIRS-to-MODIS ratio after 2012,
  // plus the total step at the transition — the demo effect at a glance.
  const post = series.rows.filter((r) => r.date >= VIIRS_START);
  const pre = series.rows.filter((r) => r.date < VIIRS_START && r.date >= "2009-01-01");
  const meanOf = (xs: number[]): number => mean(xs);
  const rawRatio = meanOf(post.map((r) => r.raw_viirs)) / meanOf(post.map((r) => r.raw_modis));
  const harmRatio = meanOf(post.map((r) => r.harm_viirs)) / meanOf(post.map((r) => r.harm_modis));
  const rawStep = meanOf(post.map((r) => r.raw_total)) / meanOf(pre.map((r) => r.raw_total));
  const harmStep = meanOf(post.map((r) => r.harm_total)) / meanOf(pre.map((r) => r.harm_total));
  console.log(
    `mock summary: after 2012 raw VIIRS/MODIS ratio = ${rawRatio.toFixed(2)}, ` +
      `harmonized ratio = ${harmRatio.toFixed(2)} ` +
      `(total step at transition: raw x${rawStep.toFixed(2)}, harmonized x${harmStep.toFixed(2)})`,
  );
  console.log(
    `mock:gen wrote ${Object.keys(files).length} files to public/mock/ ` +
      `(${series.rows.length} days, ${cells.rows.length} cells, seed ${SEED})`,
  );
}

main();
