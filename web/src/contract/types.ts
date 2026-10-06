// TypeScript mirror of docs/contract.schema.json (Phase 0 frozen contract).
// Runtime validation is done by the JSON Schema (see tests/test_contract.py);
// these types are the compile-time view.

export type SourceKind = 'mock' | 'fixture' | 'cache' | 'live';
export type Mode = 'raw' | 'harmonized';

export interface MetaBlock {
  source: SourceKind;
  generated_at: string;
  region: { bbox: [number, number, number, number] };
  cell_km: number;
  min_confidence: number;
  date_range: [string, string];
  params_hash: string;
}

export interface MetaPayload {
  meta: MetaBlock;
  sensors: { product: string; family: string; start: string; end: string }[];
  years: { start: number; end: number };
  streams: string[];
}

/** The observing stream a series bin is anchored on (S7). */
export type BinSource = 'MODIS' | 'BRIDGE' | 'VIIRS_CAL' | 'NONE';

export interface SeriesPoint {
  date: string;
  raw_modis: number;
  raw_viirs: number;
  raw_total: number;
  harm_modis: number;
  harm_viirs: number;
  harm_total: number;
  /** S7 coverage of the eight-day bin this day falls in, 0..1. */
  coverage: number;
  source: BinSource;
}

export interface SeriesPayload {
  meta: MetaBlock;
  metric: 'density' | 'cell_days';
  bin_days: 1 | 8;
  series: SeriesPoint[];
}

export interface CellPoint {
  cell_id: string;
  bounds: [number, number, number, number];
  raw: number;
  harmonized: number;
  peak_frp: number | null;
}

export interface CellsPayload {
  meta: MetaBlock;
  window: { start: string; end: string };
  cells: CellPoint[];
}

export interface BaselinePoint {
  doy: number;
  p05: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

export interface BaselinePayload {
  meta: MetaBlock;
  window_days: number;
  years_used: number[];
  baseline: BaselinePoint[];
}

export type AnomalyFlag = 'normal' | 'elevated' | 'extreme' | 'not_scored';

export interface AnomalyPayload {
  meta: MetaBlock;
  query: { date: string; aoi: string };
  value: number | null;
  percentile: number | null;
  flag: AnomalyFlag;
  baseline_window: number;
  doy_range: [number, number];
  years_used: number[];
  reason: string | null;
}

export interface CriticalPeriodPayload {
  meta: MetaBlock;
  aoi: string;
  insufficient_activity: boolean;
  onset_bin: number | null;
  peak_bin: number | null;
  end_bin: number | null;
  window: { start_bin: number; end_bin: number; mass: number } | null;
  year_timing_deviation: { year: number; days: number }[];
}

export interface Correlation {
  pearson: number | null;
  spearman: number | null;
  ratio: number | null;
}

export interface ValidationPayload {
  meta: MetaBlock;
  overlap: { years: number[]; n_days: number };
  raw: Correlation;
  harmonized: Correlation;
  cell_sweep: { cell_km: number; raw_correlation: number; harmonized_correlation: number }[];
}

export interface MethodsPayload {
  meta: MetaBlock;
  cell_km: number;
  min_confidence: number;
  confidence_mapping: { low: number; nominal: number; high: number };
  collapse_rule: string;
  notices: string[];
  datasets: { id: string; product: string; sensor: string; used_for: string; url: string }[];
}

export interface AoiPayload {
  meta: MetaBlock;
  presets: { id: string; name: string; bbox: [number, number, number, number] }[];
}

/** Everything the app loads at startup. */
export interface Dataset {
  meta: MetaPayload;
  series: SeriesPayload;
  cells: CellsPayload;
  baseline: BaselinePayload;
  anomaly: AnomalyPayload;
  criticalPeriod: CriticalPeriodPayload;
  validation: ValidationPayload;
  methods: MethodsPayload;
  aoi: AoiPayload;
}
