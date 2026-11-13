import type { Mode } from '../contract/types';
import { CUSTOM_AOI, parseRing, type Ring } from '../lib/polygon';

export type View =
  | 'overview'
  | 'calendar'
  | 'map'
  | 'anomalies'
  | 'critical'
  | 'validation'
  | 'methods'
  | 'offline';

export const VIEWS: View[] = [
  'overview',
  'calendar',
  'map',
  'anomalies',
  'critical',
  'validation',
  'methods',
  'offline',
];

export interface AppState {
  view: View;
  mode: Mode;
  aoi: string;
  date: string | null;
  /** The drawn area, when the user has drawn one. */
  polygon: Ring | null;
}

export const DEFAULT_STATE: AppState = {
  view: 'overview',
  mode: 'harmonized',
  aoi: 'BGD',
  date: null,
  polygon: null,
};

function isView(value: string): value is View {
  return (VIEWS as string[]).includes(value);
}

/** Parse a location hash such as "#calendar?mode=raw&aoi=BGD". */
export function parseHash(hash: string): AppState {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  if (!raw) return { ...DEFAULT_STATE };
  const [path, query = ''] = raw.split('?');
  const params = new URLSearchParams(query);
  const mode = params.get('mode');
  const date = params.get('date');
  const polygon = parseRing(params.get('poly'));
  const aoi = params.get('aoi');
  return {
    view: isView(path) ? path : DEFAULT_STATE.view,
    mode: mode === 'raw' || mode === 'harmonized' ? mode : DEFAULT_STATE.mode,
    // `custom` is the label of a drawn shape, not an area the API can serve.
    // A hash that names it without a shape is stale, so it falls back to the
    // default area rather than asking the API about a region that is not one.
    aoi: !aoi || (aoi === CUSTOM_AOI && !polygon) ? DEFAULT_STATE.aoi : aoi,
    date: date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null,
    polygon,
  };
}

/** Serialise app state back to a location hash. */
export function buildHash(state: AppState): string {
  const params = new URLSearchParams();
  params.set('mode', state.mode);
  // The drawn shape is the area, and the `poly` parameter carries it, so the
  // label of a custom area has no place in the hash.
  if (state.aoi !== CUSTOM_AOI) params.set('aoi', state.aoi);
  if (state.date) params.set('date', state.date);
  if (state.polygon && state.polygon.length > 0) {
    params.set('poly', JSON.stringify(state.polygon));
  }
  return `#${state.view}?${params.toString()}`;
}

/**
 * Apply a change to the state it applies to.
 *
 * A change is a function of the state, not a copy of it made when the setter
 * was built: two changes in one tick must both land, and a copy made earlier
 * drops the first.
 */
export function applyChange(
  current: AppState,
  change: Partial<AppState>,
): AppState {
  return { ...current, ...change };
}
