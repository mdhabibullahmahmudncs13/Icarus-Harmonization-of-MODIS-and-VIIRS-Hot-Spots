import type { SourceKind } from '../contract/types';

/**
 * What a source is, in words, and whether it may be called evidence.
 *
 * Only `cache` and `live` are observations of the world. `mock` is generated
 * for the interface and `fixture` is the committed offline demo detection set;
 * both are synthetic and must say so.
 */
export interface SourceNotice {
  /** Short lead-in, e.g. "Mock data." */
  title: string;
  /** One sentence on what the numbers are and are not. */
  body: string;
  /** True only for sources that are real observations. */
  isEvidence: boolean;
}

const NOTICES: Record<SourceKind, SourceNotice> = {
  mock: {
    title: 'Mock data.',
    body: 'Generated for the interface only. Not an observation and never used as evidence.',
    isEvidence: false,
  },
  fixture: {
    title: 'Fixture data.',
    body:
      'The committed offline demo detections, served without a network. Synthetic, ' +
      'not an observation and never used as evidence.',
    isEvidence: false,
  },
  cache: {
    title: 'Cached observations.',
    body: 'Downloaded NASA FIRMS detections read from the local cache.',
    isEvidence: true,
  },
  live: {
    title: 'Live observations.',
    body: 'Downloaded NASA FIRMS detections, fetched from the live API.',
    isEvidence: true,
  },
};

/**
 * The notice a source must show. Every source has one, so a synthetic tier can
 * never be labelled with another tier's name — the single hard-coded
 * "Mock data" banner used to stand over the fixture.
 */
export function sourceNotice(source: SourceKind): SourceNotice {
  return NOTICES[source];
}

/** The banner a source needs, or `null` when the data is evidence and needs none. */
export function bannerFor(source: SourceKind): SourceNotice | null {
  const notice = sourceNotice(source);
  return notice.isEvidence ? null : notice;
}

/**
 * Release guard (`docs/IMPLEMENTATION_PLAN.md` §3.3): a release build must not
 * ship on data that is not evidence.
 *
 * Scoped to builds that opt in with `--mode release`, so an ordinary
 * `npm run build` can still produce a mock preview for interface work.
 */
export function assertReleaseDataSource(mode: string, release: boolean): void {
  if (!release) return;
  if (mode === 'api') return;
  throw new Error(
    `release build refuses to ship on "${mode}" data: ` +
      'set VITE_DATA=api, or build without --mode release',
  );
}
