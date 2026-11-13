import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiDataSource, MockDataSource } from '../src/data/DataSource';

/** The key each payload has to carry, and a body that carries it. */
const VALID: Record<string, Record<string, unknown>> = {
  meta: { sensors: [] },
  series: { series: [] },
  cells: { cells: [] },
  baseline: { baseline: [] },
  anomaly: { flag: 'normal' },
  criticalPeriod: { insufficient_activity: false },
  validation: { cell_sweep: [] },
  methods: { collapse_rule: 'x' },
  aoi: { presets: [] },
};

/** The file each mock payload is served from, and the key it has to carry. */
const MOCK_FILES: Record<string, string> = {
  'meta.json': 'meta',
  'series.json': 'series',
  'cells.json': 'cells',
  'baseline.json': 'baseline',
  'anomaly.json': 'anomaly',
  'critical-period.json': 'criticalPeriod',
  'validation.json': 'validation',
  'methods.json': 'methods',
  'aoi.json': 'aoi',
};

/**
 * The API paths, and the payload each one answers with.
 *
 * The API serves the same nine payloads under bare names, not filenames, so
 * the lookup has to know both spellings: the mock answers `/mock/meta.json`,
 * the API answers `/api/meta` — with or without the `/v1` version prefix.
 */
const API_PATHS: Record<string, string> = {
  meta: 'meta',
  series: 'series',
  cells: 'cells',
  baseline: 'baseline',
  anomalies: 'anomaly',
  'critical-period': 'criticalPeriod',
  validation: 'validation',
  methods: 'methods',
  aoi: 'aoi',
};

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Capture every URL the source asks for, and answer each with a valid body. */
function captureFetch(): string[] {
  const urls: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      urls.push(url);
      const body = VALID[payloadFor(url)] ?? {};
      return { ok: true, json: async () => body } as unknown as Response;
    }),
  );
  return urls;
}

/** The payload a URL asks for, by whichever spelling that URL uses. */
function payloadFor(url: string): string {
  const path = url.split('?')[0];
  const file = path.slice(path.lastIndexOf('/') + 1);
  const mock = MOCK_FILES[file];
  if (mock !== undefined) return mock;
  // The API answers under bare names, with or without the `/v1` prefix.
  return API_PATHS[file] ?? '';
}

/** Answer every request with one body, whatever is asked for. */
function stubFetch(body: unknown): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: true, json: async () => body }) as unknown as Response),
  );
}

/**
 * Answer every request with a valid body, except the one named.
 *
 * The nine payloads are fetched together, so a stub that answers every URL
 * with the same body makes whichever payload is fetched first the one that
 * fails — the error then names a payload the test did not ask about.
 */
function stubFetchExcept(file: string, body: unknown): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const asked = url.slice(url.lastIndexOf('/') + 1).split('?')[0];
      return {
        ok: true,
        json: async () => (asked === file ? body : VALID[payloadFor(url)] ?? {}),
      } as unknown as Response;
    }),
  );
}

describe('ApiDataSource', () => {
  it('scopes every payload by the area', async () => {
    const urls = captureFetch();
    await new ApiDataSource('/api/v1').load({ aoi: 'IND-C' });

    // The regression this guards: the API scopes its payloads by AOI, but the
    // frontend asked without one, so every view showed the default region.
    for (const url of urls) {
      if (url.endsWith('/api/v1/aoi')) continue; // the preset list is not scoped
      expect(url).toContain('aoi=IND-C');
    }
  });

  it('asks the anomalies endpoint about the selected day', async () => {
    const urls = captureFetch();
    await new ApiDataSource('/api/v1').load({ aoi: 'BGD', date: '2019-03-01' });

    const anomaly = urls.find((u) => u.includes('/anomalies'));
    expect(anomaly).toContain('date=2019-03-01');
  });

  it('sends no day when none is selected', async () => {
    const urls = captureFetch();
    await new ApiDataSource('/api/v1').load({ aoi: 'BGD', date: null });

    const anomaly = urls.find((u) => u.includes('/anomalies'));
    expect(anomaly).not.toContain('date=');
  });

  it('asks for nothing in particular when given no query', async () => {
    const urls = captureFetch();
    await new ApiDataSource('/api/v1').load();

    for (const url of urls) {
      expect(url).not.toContain('?');
    }
  });
});

describe('MockDataSource', () => {
  it('reads the same nine files whatever the area', async () => {
    const urls = captureFetch();
    await new MockDataSource('/mock').load({ aoi: 'IND-C', date: '2019-03-01' });

    // The mock is nine fixed payloads for one extent, so the query cannot
    // change what comes back — only the API source is scopeable.
    expect(urls).toHaveLength(9);
    expect(urls.every((u) => u.startsWith('/mock/'))).toBe(true);
    expect(urls.some((u) => u.includes('?'))).toBe(false);
  });
});

describe('payload validation', () => {
  it('refuses a payload that is missing the key the app reads it through', async () => {
    // The regression this guards: the payload was cast to the contract type
    // unchecked, so a truncated file reached the app as undefined and threw
    // inside a useMemo — outside the error handling, so the app blanked out
    // with no message.
    stubFetchExcept('series.json', { source: 'mock' });
    await expect(new MockDataSource('/mock').load()).rejects.toThrow(/missing "series"/);
  });

  it('refuses a payload that is not an object', async () => {
    stubFetch(null);
    await expect(new MockDataSource('/mock').load()).rejects.toThrow(/payload object/);
  });

  it('accepts the nine payloads the mock ships', async () => {
    captureFetch();
    await expect(new MockDataSource('/mock').load()).resolves.toBeTruthy();
  });
});
