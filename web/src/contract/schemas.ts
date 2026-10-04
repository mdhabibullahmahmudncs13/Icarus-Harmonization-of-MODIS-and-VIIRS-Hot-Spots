/**
 * Icarus API contract — zod schemas and TypeScript types.
 *
 * One source of truth for the frontend (runtime validation), the mock
 * generator (generation-time validation) and the Python backend (via the
 * JSON Schema exported to docs/contract.schema.json by `npm run
 * contract:export`).
 *
 * Every response carries the same `meta` block (Implementation plan,
 * section 4.1). The frontend displays numbers from these shapes; it never
 * computes statistics from them.
 */
import { z } from "zod";

/* ------------------------------------------------------------------ */
/* Primitive, shared pieces                                            */
/* ------------------------------------------------------------------ */

/** Where a response's data came from. Reported truthfully on every response. */
export const sourceSchema = z.enum(["mock", "live", "cache", "fixture"]);
export type Source = z.infer<typeof sourceSchema>;

/** Geographic bounding box, degrees: [west, south, east, north]. */
export const bboxSchema = z.tuple([z.number(), z.number(), z.number(), z.number()]);
export type Bbox = z.infer<typeof bboxSchema>;

/** Calendar date, ISO 8601 (YYYY-MM-DD). */
export const isoDateSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "expected an ISO date (YYYY-MM-DD)");
export type IsoDate = z.infer<typeof isoDateSchema>;

/** ISO 8601 timestamp with time component. */
export const isoTimestampSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}T/, "expected an ISO timestamp (YYYY-MM-DDThh:mm...)");

/** The `meta` block present on every response. */
export const metaSchema = z.object({
  source: sourceSchema,
  generated_at: isoTimestampSchema,
  region: z.object({ bbox: bboxSchema }),
  /** Grid cell size in kilometres. */
  cell_km: z.number().positive(),
  /** Confidence filter applied to detections (numeric, after VIIRS l/n/h mapping). */
  min_confidence: z.number(),
  /** Inclusive [start, end] dates covered by this dataset. */
  date_range: z.tuple([isoDateSchema, isoDateSchema]),
});
export type Meta = z.infer<typeof metaSchema>;

/* ------------------------------------------------------------------ */
/* Sensor epochs (GET /api/meta)                                       */
/* ------------------------------------------------------------------ */

/**
 * One sensor epoch. `product` is a FIRMS sensor product name.
 * Dates may be mock placeholders until verified against FIRMS docs;
 * the UI must not present placeholder dates as facts.
 */
export const sensorSchema = z.object({
  product: z.string().min(1),
  family: z.enum(["MODIS", "VIIRS"]),
  start: isoDateSchema,
  end: isoDateSchema.nullable(),
});
export type Sensor = z.infer<typeof sensorSchema>;

export const metaResponseSchema = z.object({
  meta: metaSchema,
  sensors: z.array(sensorSchema),
});
export type MetaResponse = z.infer<typeof metaResponseSchema>;

/* ------------------------------------------------------------------ */
/* Daily counts (GET /api/series)                                      */
/* ------------------------------------------------------------------ */

/**
 * One day of counts.
 * Raw = count of detections per day; harmonized = distinct cell-days per day.
 */
export const seriesRowSchema = z.object({
  date: isoDateSchema,
  raw_modis: z.number().int().nonnegative(),
  raw_viirs: z.number().int().nonnegative(),
  raw_total: z.number().int().nonnegative(),
  harm_modis: z.number().int().nonnegative(),
  harm_viirs: z.number().int().nonnegative(),
  harm_total: z.number().int().nonnegative(),
});
export type SeriesRow = z.infer<typeof seriesRowSchema>;

export const seriesResponseSchema = z.object({
  meta: metaSchema,
  rows: z.array(seriesRowSchema),
});
export type SeriesResponse = z.infer<typeof seriesResponseSchema>;

/* ------------------------------------------------------------------ */
/* Grid cells (GET /api/cells?start&end)                               */
/* ------------------------------------------------------------------ */

export const cellRowSchema = z.object({
  cell_id: z.string().min(1),
  /** [west, south, east, north] in degrees. */
  bounds: bboxSchema,
  /** Raw detections inside the cell over the window. */
  raw: z.number().int().nonnegative(),
  /** Distinct cell-days inside the cell over the window (here: 1 cell-day max per day). */
  harmonized: z.number().int().nonnegative(),
  /** Peak fire radiative power among detections in the cell, MW. */
  peak_frp: z.number().nonnegative(),
});
export type CellRow = z.infer<typeof cellRowSchema>;

export const cellsResponseSchema = z.object({
  meta: metaSchema,
  rows: z.array(cellRowSchema),
});
export type CellsResponse = z.infer<typeof cellsResponseSchema>;

/* ------------------------------------------------------------------ */
/* Seasonal baseline (GET /api/baseline)                               */
/* ------------------------------------------------------------------ */

/** Percentiles of the daily series for one day of year. */
export const baselineRowSchema = z.object({
  doy: z.number().int().min(1).max(366),
  p05: z.number().nonnegative(),
  p25: z.number().nonnegative(),
  p50: z.number().nonnegative(),
  p75: z.number().nonnegative(),
  p95: z.number().nonnegative(),
});
export type BaselineRow = z.infer<typeof baselineRowSchema>;

export const baselineResponseSchema = z.object({
  meta: metaSchema,
  /** Half-width, in days, of the day-of-year window used for each percentile. */
  window_days: z.number().int().nonnegative(),
  /** Number of years contributing to the percentiles. */
  years_used: z.number().int().positive(),
  rows: z.array(baselineRowSchema),
});
export type BaselineResponse = z.infer<typeof baselineResponseSchema>;

/* ------------------------------------------------------------------ */
/* Anomaly (GET /api/anomaly?date&bbox)                                */
/* ------------------------------------------------------------------ */

export const anomalyResponseSchema = z.object({
  meta: metaSchema,
  date: isoDateSchema,
  /** The observed value being judged (same units as the active series). */
  value: z.number().nonnegative(),
  /** Percentile of the value against the day-of-year baseline, 0-100. */
  percentile: z.number().min(0).max(100),
  /** Half-width, in days, of the baseline window used. */
  baseline_window: z.number().int().nonnegative(),
  /** Day-of-year window used, [start, end] as 1-based days of year. */
  doy_range: z.tuple([z.number().int().min(1), z.number().int().max(366)]),
  years_used: z.number().int().positive(),
});
export type AnomalyResponse = z.infer<typeof anomalyResponseSchema>;

/* ------------------------------------------------------------------ */
/* Validation (GET /api/validation)                                    */
/* ------------------------------------------------------------------ */

/** Correlation between two sensor series on the overlap period. */
export const correlationSchema = z.object({
  pearson: z.number().min(-1).max(1),
  spearman: z.number().min(-1).max(1),
  /** Mean(second series) / mean(first series) over the overlap. */
  ratio: z.number().nonnegative(),
});
export type Correlation = z.infer<typeof correlationSchema>;

/** One point of the cell-size sweep. */
export const cellSweepRowSchema = z.object({
  cell_km: z.number().positive(),
  raw_pearson: z.number().min(-1).max(1),
  harmonized_pearson: z.number().min(-1).max(1),
});
export type CellSweepRow = z.infer<typeof cellSweepRowSchema>;

export const validationResponseSchema = z.object({
  meta: metaSchema,
  overlap: z.object({ start: isoDateSchema, end: isoDateSchema }),
  /** raw MODIS vs raw VIIRS, daily counts on the overlap. */
  raw: correlationSchema,
  /** harmonized MODIS vs harmonized VIIRS, daily counts on the overlap. */
  harmonized: correlationSchema,
  cell_sweep: z.array(cellSweepRowSchema),
});
export type ValidationResponse = z.infer<typeof validationResponseSchema>;

/* ------------------------------------------------------------------ */
/* Methods (GET /api/methods)                                          */
/* ------------------------------------------------------------------ */

/** Citation for one dataset. `product` uses FIRMS sensor product naming. */
export const datasetSchema = z.object({
  id: z.string().min(1),
  product: z.string().min(1),
  url: z.string().url(),
});
export type Dataset = z.infer<typeof datasetSchema>;

export const methodsResponseSchema = z.object({
  meta: metaSchema,
  cell_km: z.number().positive(),
  min_confidence: z.number(),
  /** VIIRS confidence letters mapped to numeric values before filtering. */
  confidence_mapping: z.object({
    l: z.number(),
    n: z.number(),
    h: z.number(),
  }),
  /** Plain-language description of the cell-day collapse rule. */
  collapse_rule: z.string().min(1),
  notices: z.array(z.string()),
  datasets: z.array(datasetSchema),
});
export type MethodsResponse = z.infer<typeof methodsResponseSchema>;

/* ------------------------------------------------------------------ */
/* Endpoint registry                                                   */
/* ------------------------------------------------------------------ */

/** One schema per endpoint, keyed by endpoint name (section 4.1 of the plan). */
export const endpoints = {
  meta: metaResponseSchema,
  series: seriesResponseSchema,
  cells: cellsResponseSchema,
  baseline: baselineResponseSchema,
  anomaly: anomalyResponseSchema,
  validation: validationResponseSchema,
  methods: methodsResponseSchema,
} as const;

export type EndpointName = keyof typeof endpoints;
export type EndpointPayloads = {
  [K in EndpointName]: z.infer<(typeof endpoints)[K]>;
};
