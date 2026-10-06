import type { Dataset, SourceKind } from '../contract/types';

export interface DataSource {
  readonly kind: SourceKind;
  load(): Promise<Dataset>;
}

const FILES = {
  meta: 'meta.json',
  series: 'series.json',
  cells: 'cells.json',
  baseline: 'baseline.json',
  anomaly: 'anomaly.json',
  criticalPeriod: 'critical-period.json',
  validation: 'validation.json',
  methods: 'methods.json',
  aoi: 'aoi.json',
} as const;

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} -> ${res.status}`);
  return (await res.json()) as T;
}

/** Reads the generated Phase 0 payloads from web/public/mock/. */
export class MockDataSource implements DataSource {
  readonly kind: SourceKind = 'mock';
  constructor(private readonly base = '/mock') {}

  async load(): Promise<Dataset> {
    const keys = Object.keys(FILES) as (keyof typeof FILES)[];
    const payloads = await Promise.all(keys.map((k) => getJSON<unknown>(`${this.base}/${FILES[k]}`)));
    const out = {} as Record<string, unknown>;
    keys.forEach((k, i) => (out[k] = payloads[i]));
    return out as unknown as Dataset;
  }
}

/** Reads the live API once it exists. Not reachable during Phase 1. */
export class ApiDataSource implements DataSource {
  readonly kind: SourceKind = 'live';
  constructor(private readonly base = '/api/v1') {}

  async load(): Promise<Dataset> {
    const meta = await getJSON<Dataset['meta']>(`${this.base.replace('/v1', '')}/meta`);
    const [series, cells, baseline, anomaly, criticalPeriod, validation, methods, aoi] =
      await Promise.all([
        getJSON<Dataset['series']>(`${this.base}/series`),
        getJSON<Dataset['cells']>(`${this.base}/cells`),
        getJSON<Dataset['baseline']>(`${this.base}/baseline`),
        getJSON<Dataset['anomaly']>(`${this.base}/anomalies`),
        getJSON<Dataset['criticalPeriod']>(`${this.base}/critical-period`),
        getJSON<Dataset['validation']>(`${this.base}/validation`),
        getJSON<Dataset['methods']>(`${this.base}/methods`),
        getJSON<Dataset['aoi']>(`${this.base}/aoi`),
      ]);
    return { meta, series, cells, baseline, anomaly, criticalPeriod, validation, methods, aoi };
  }
}

export function getDataSource(): DataSource {
  const mode = import.meta.env.VITE_DATA ?? 'mock';
  if (mode === 'api') return new ApiDataSource(import.meta.env.VITE_API_BASE ?? '/api/v1');
  return new MockDataSource();
}
