import { describe, expect, it } from 'vitest';

import type { SourceKind } from '../src/contract/types';
import { assertReleaseDataSource, bannerFor, sourceNotice } from '../src/lib/source';

const ALL: SourceKind[] = ['mock', 'fixture', 'cache', 'live'];

describe('sourceNotice', () => {
  it('describes every source the contract defines', () => {
    for (const source of ALL) {
      const notice = sourceNotice(source);
      expect(notice.title.length).toBeGreaterThan(0);
      expect(notice.body.length).toBeGreaterThan(0);
    }
  });

  it('treats only cache and live as evidence', () => {
    expect(sourceNotice('mock').isEvidence).toBe(false);
    expect(sourceNotice('fixture').isEvidence).toBe(false);
    expect(sourceNotice('cache').isEvidence).toBe(true);
    expect(sourceNotice('live').isEvidence).toBe(true);
  });
});

describe('bannerFor', () => {
  it('shows no banner for observed data', () => {
    expect(bannerFor('cache')).toBeNull();
    expect(bannerFor('live')).toBeNull();
  });

  it('names the mock as mock', () => {
    expect(bannerFor('mock')?.title).toBe('Mock data.');
  });

  it('names the fixture as a fixture, never as mock', () => {
    const notice = bannerFor('fixture');
    expect(notice).not.toBeNull();
    expect(notice?.title).toBe('Fixture data.');
    // The regression this guards: one hard-coded banner stood over every
    // non-evidence source, so the fixture was labelled "Mock data".
    expect(notice?.title).not.toMatch(/mock/i);
    expect(notice?.body).not.toMatch(/mock/i);
  });

  it('says a synthetic source is not evidence', () => {
    for (const source of ['mock', 'fixture'] as SourceKind[]) {
      expect(bannerFor(source)?.body).toMatch(/never used as evidence/);
    }
  });
});

describe('assertReleaseDataSource', () => {
  it('allows a release on api data', () => {
    expect(() => assertReleaseDataSource('api', true)).not.toThrow();
  });

  it('refuses a release on mock data', () => {
    expect(() => assertReleaseDataSource('mock', true)).toThrow(/refuses to ship on "mock"/);
  });

  it('refuses a release on fixture data', () => {
    expect(() => assertReleaseDataSource('fixture', true)).toThrow(/refuses to ship on "fixture"/);
  });

  it('leaves an ordinary build alone', () => {
    expect(() => assertReleaseDataSource('mock', false)).not.toThrow();
    expect(() => assertReleaseDataSource('fixture', false)).not.toThrow();
  });
});
