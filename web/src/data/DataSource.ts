import type { Dataset, SourceKind } from '../contract/types';

export interface DataSource {
  readonly kind: SourceKind;
  load(query?: LoadQuery): Promise<Dataset>;
}

/** What a load is about: the area, and the day to judge. */
export interface LoadQuery {
  /** Preset id of the area the payloads describe. */
  aoi?: string;
  /** The day the anomalies payload ranks against its season. */
  date?: string | null;
}

/** The query string for a request, or `''` when there is nothing to say. */
function query(params: Record<string, string | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value);
  }
  const text = search.toString();
  return text ? `?${text}` : '';
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

/**
 * The key each payload has to carry, by payload.
 *
 * The cast to the contract type is unchecked, so a payload that is truncated,
 * stale or served by a proxy that answers with an error page reaches the app
 * as `undefined` and blows up inside a `useMemo` — outside the error handling
 * that would report it, so the app blanks out with no message. One key per
 * payload is enough to catch that: the key the app reads the payload through.
 */
const REQUIRED_KEY: Record<string, string> = {
  meta: 'sensors',
  series: 'series',
  cells: 'cells',
  baseline: 'baseline',
  anomaly: 'flag',
  criticalPeriod: 'insufficient_activity',
  validation: 'cell_sweep',
  methods: 'collapse_rule',
  aoi: 'presets',
};

async function getJSON<T>(url: string, payload: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} -> ${res.status}`);
  const body: unknown = await res.json();
  const key = REQUIRED_KEY[payload];
  if (key !== undefined) {
    if (body === null || typeof body !== 'object') {
      throw new Error(`${url} did not return a payload object`);
    }
    if (!(key in body)) {
      throw new Error(`${url} is missing "${key}"; it is not a ${payload} payload`);
    }
  }
  return body as T;
}

/** Reads the generated Phase 0 payloads from web/public/mock/. */
export class MockDataSource implements DataSource {
  readonly kind: SourceKind = 'mock';
  constructor(private readonly base = '/mock') {}

  /**
   * The mock is nine fixed payloads for one extent (docs/IMPLEMENTATION_PLAN.md
   * §F3), so it has nothing to scope by area or day: the query is ignored and
   * the same nine files come back.
   */
  async load(_query?: LoadQuery): Promise<Dataset> {
    const keys = Object.keys(FILES) as (keyof typeof FILES)[];
    const payloads = await Promise.all(
      keys.map((k) => getJSON<unknown>(`${this.base}/${FILES[k]}`, k)),
    );
    const out = {} as Record<string, unknown>;
    keys.forEach((k, i) => (out[k] = payloads[i]));
    return out as unknown as Dataset;
  }
}

/** Reads the live API once it exists. Not reachable during Phase 1. */
export class ApiDataSource implements DataSource {
  readonly kind: SourceKind = 'live';
  constructor(private readonly base = '/api/v1') {}

  /**
   * The API scopes every payload by the area, and the anomalies payload also
   * by the day (docs/ARCHITECTURE.md §6), so the query goes out on every
   * request that accepts it.
   */
  async load(q: LoadQuery = {}): Promise<Dataset> {
    const area = query({ aoi: q.aoi });
    const meta = await getJSON<Dataset['meta']>(
      `${this.base.replace('/v1', '')}/meta${area}`,
      'meta',
    );
    const [series, cells, baseline, anomaly, criticalPeriod, validation, methods, aoi] =
      await Promise.all([
        getJSON<Dataset['series']>(`${this.base}/series${area}`, 'series'),
        getJSON<Dataset['cells']>(`${this.base}/cells${area}`, 'cells'),
        getJSON<Dataset['baseline']>(`${this.base}/baseline${area}`, 'baseline'),
        getJSON<Dataset['anomaly']>(
          `${this.base}/anomalies${query({ aoi: q.aoi, date: q.date })}`,
          'anomaly',
        ),
        getJSON<Dataset['criticalPeriod']>(
          `${this.base}/critical-period${area}`,
          'criticalPeriod',
        ),
        getJSON<Dataset['validation']>(`${this.base}/validation${area}`, 'validation'),
        getJSON<Dataset['methods']>(`${this.base}/methods${area}`, 'methods'),
        getJSON<Dataset['aoi']>(`${this.base}/aoi`, 'aoi'),
      ]);
    return { meta, series, cells, baseline, anomaly, criticalPeriod, validation, methods, aoi };
  }
}

export function getDataSource(): DataSource {
  const mode = import.meta.env.VITE_DATA ?? 'mock';
  if (mode === 'api') return new ApiDataSource(import.meta.env.VITE_API_BASE ?? '/api/v1');
  return new MockDataSource();
}
