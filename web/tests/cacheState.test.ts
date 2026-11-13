import { describe, expect, it } from 'vitest';

import { formatBytes, summarizeCaches } from '../src/lib/cacheState';

describe('summarizeCaches', () => {
  it('totals entries and bytes across the caches', () => {
    const state = summarizeCaches([
      { name: 'icarus-data-v1', entries: 9, bytes: 2048 },
      { name: 'icarus-shell-v1', entries: 12, bytes: 1024 },
    ]);
    expect(state.totalEntries).toBe(21);
    expect(state.totalBytes).toBe(3072);
  });

  it('sorts the caches by name so the panel order is stable', () => {
    const state = summarizeCaches([
      { name: 'icarus-shell-v1', entries: 1, bytes: 1 },
      { name: 'icarus-data-v1', entries: 1, bytes: 1 },
    ]);
    expect(state.caches.map((c) => c.name)).toEqual(['icarus-data-v1', 'icarus-shell-v1']);
  });

  it('reports an empty cache as empty, not as an error', () => {
    const state = summarizeCaches([]);
    expect(state.totalEntries).toBe(0);
    expect(state.totalBytes).toBe(0);
    expect(state.caches).toEqual([]);
  });

  it('records whether the page is controlled by a worker', () => {
    expect(summarizeCaches([], true).controlled).toBe(true);
    expect(summarizeCaches([], false).controlled).toBe(false);
  });
});

describe('formatBytes', () => {
  it('shows raw bytes below a kilobyte', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(512)).toBe('512 B');
  });

  it('scales to KB, MB and GB', () => {
    expect(formatBytes(1024)).toBe('1.0 KB');
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB');
    expect(formatBytes(3 * 1024 * 1024 * 1024)).toBe('3.0 GB');
  });

  it('drops the decimal once the number gets large', () => {
    expect(formatBytes(20 * 1024 * 1024)).toBe('20 MB');
  });
});
