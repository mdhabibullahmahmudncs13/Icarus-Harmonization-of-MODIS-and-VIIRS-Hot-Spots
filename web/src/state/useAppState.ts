/**
 * React binding for the URL-synced app state.
 * The URL is the source of truth: back/forward buttons stay consistent.
 */
import { useCallback, useEffect, useState } from "react";
import { parseAppState, writeStateToUrl, type AppState } from "./urlState";

export function useAppState(): [AppState, (next: AppState) => void] {
  const [state, setState] = useState<AppState>(() => parseAppState(window.location.search));

  useEffect(() => {
    const onPop = (): void => setState(parseAppState(window.location.search));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const update = useCallback((next: AppState) => {
    setState(next);
    writeStateToUrl(next);
  }, []);

  return [state, update];
}
