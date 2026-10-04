/**
 * App state: mode (raw | harmonized) and selected date, synced to the URL
 * query string (F1 acceptance). Parsing and serializing are pure so they
 * can be unit-tested without a browser.
 */

export type Mode = "raw" | "harmonized";

export interface AppState {
  mode: Mode;
  /** Selected date, ISO (YYYY-MM-DD), or null when nothing is selected. */
  date: string | null;
}

export const DEFAULT_STATE: AppState = { mode: "raw", date: null };

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function parseMode(value: string | null | undefined): Mode {
  return value === "harmonized" ? "harmonized" : "raw";
}

/** Parse `?mode=...&date=...` into app state. Unknown values fall back to defaults. */
export function parseAppState(search: string): AppState {
  const params = new URLSearchParams(search);
  const date = params.get("date");
  return {
    mode: parseMode(params.get("mode")),
    date: date !== null && ISO_DATE.test(date) ? date : null,
  };
}

/** Serialize app state into a query string, always including mode. */
export function serializeAppState(state: AppState): string {
  const params = new URLSearchParams();
  params.set("mode", state.mode);
  if (state.date !== null) params.set("date", state.date);
  return `?${params.toString()}`;
}

/** Push state to the browser history so the URL always matches the app. */
export function writeStateToUrl(
  state: AppState,
  loc: Location = window.location,
  history: History = window.history,
): void {
  const query = serializeAppState(state);
  history.pushState(null, "", `${loc.pathname}${query}${loc.hash}`);
}
