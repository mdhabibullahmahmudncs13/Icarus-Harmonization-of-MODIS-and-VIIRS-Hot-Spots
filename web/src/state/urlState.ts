import type { Mode } from '../contract/types';

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
}

export const DEFAULT_STATE: AppState = {
  view: 'overview',
  mode: 'harmonized',
  aoi: 'BGD',
  date: null,
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
  return {
    view: isView(path) ? path : DEFAULT_STATE.view,
    mode: mode === 'raw' || mode === 'harmonized' ? mode : DEFAULT_STATE.mode,
    aoi: params.get('aoi') ?? DEFAULT_STATE.aoi,
    date: date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null,
  };
}

/** Serialise app state back to a location hash. */
export function buildHash(state: AppState): string {
  const params = new URLSearchParams();
  params.set('mode', state.mode);
  params.set('aoi', state.aoi);
  if (state.date) params.set('date', state.date);
  return `#${state.view}?${params.toString()}`;
}
