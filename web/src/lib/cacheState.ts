/**
 * What the service worker has actually cached — the real answer to "can I work
 * offline right now?".
 *
 * The service worker keeps two versioned caches (`icarus-shell-<version>` and
 * `icarus-data-<version>`, `web/public/sw.js`), and the page learns about
 * them through the Cache API. This module reads that state and reports it.
 *
 * `readCacheState` is split from the formatting so the numbers can be tested
 * without a browser: `summarizeCaches` is pure.
 */

/** One cache the worker owns, as reported to the user. */
export interface CacheSummary {
  /** The cache name, e.g. `icarus-shell-v1`. */
  name: string;
  /** How many entries it holds. */
  entries: number;
  /** Total size of its entries, in bytes. */
  bytes: number;
}

/** The whole offline picture. */
export interface CacheState {
  /** Every icarus cache found, sorted by name. */
  caches: CacheSummary[];
  /** Sum of all entries and bytes. */
  totalEntries: number;
  totalBytes: number;
  /** True when the page is controlled by a service worker. */
  controlled: boolean;
}

export const EMPTY_CACHE_STATE: CacheState = {
  caches: [],
  totalEntries: 0,
  totalBytes: 0,
  controlled: false,
};

/**
 * Sum a set of caches into the state the panel shows.
 *
 * Pure: the caller passes the per-cache summaries, so the arithmetic is testable
 * without a Cache API.
 */
export function summarizeCaches(
  caches: CacheSummary[],
  controlled = false,
): CacheState {
  const sorted = [...caches].sort((a, b) => a.name.localeCompare(b.name));
  return {
    caches: sorted,
    totalEntries: sorted.reduce((sum, c) => sum + c.entries, 0),
    totalBytes: sorted.reduce((sum, c) => sum + c.bytes, 0),
    controlled,
  };
}

/**
 * Read the current cache state from the browser.
 *
 * Returns `null` when the Cache API is unavailable (no `caches`, or a browser
 * without service workers) so the panel can say "unknown" instead of
 * pretending the cache is empty.
 */
export async function readCacheState(): Promise<CacheState | null> {
  if (typeof caches === 'undefined') return null;
  const names = (await caches.keys()).filter((name) => name.startsWith('icarus-'));
  const summaries: CacheSummary[] = [];
  for (const name of names) {
    const cache = await caches.open(name);
    const requests = await cache.keys();
    let bytes = 0;
    for (const request of requests) {
      const response = await cache.match(request);
      if (!response) continue;
      const length = response.headers.get('content-length');
      if (length) {
        bytes += Number(length);
        continue;
      }
      // No content-length on a stored response: fall back to the body size.
      const blob = await response.clone().blob();
      bytes += blob.size;
    }
    summaries.push({ name, entries: requests.length, bytes });
  }
  const controlled =
    typeof navigator !== 'undefined' &&
    'serviceWorker' in navigator &&
    Boolean(navigator.serviceWorker.controller);
  return summarizeCaches(summaries, controlled);
}

/** Bytes as a short human string, e.g. `1.2 MB`. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB'];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}
