import { useCallback, useEffect, useRef, useState } from 'react';
import { applyChange, buildHash, parseHash, type AppState, type View } from './urlState';
import type { Mode } from '../contract/types';

export function useAppState(): {
  state: AppState;
  setView: (view: View) => void;
  setMode: (mode: Mode) => void;
  setAoi: (aoi: string) => void;
  setDate: (date: string | null) => void;
} {
  const [state, setState] = useState<AppState>(() =>
    typeof window === 'undefined' ? parseHash('') : parseHash(window.location.hash),
  );

  // The latest committed state, kept in a ref so two changes in one tick both
  // build on the first: a setter that read the rendered `state` would drop the
  // earlier change. The ref is written as soon as a change is committed, so it
  // is never behind.
  const latest = useRef(state);
  latest.current = state;

  // The hash is the record of the state, so a back or forward step is read
  // back from it rather than from a remembered copy. `popstate` covers the
  // history entries this hook pushes; `hashchange` covers a hash the user
  // edited by hand.
  useEffect(() => {
    const read = () => {
      const parsed = parseHash(window.location.hash);
      latest.current = parsed;
      setState(parsed);
    };
    window.addEventListener('popstate', read);
    window.addEventListener('hashchange', read);
    return () => {
      window.removeEventListener('popstate', read);
      window.removeEventListener('hashchange', read);
    };
  }, []);

  const commit = useCallback((change: Partial<AppState>) => {
    const updated = applyChange(latest.current, change);
    latest.current = updated;
    setState(updated);
    const hash = buildHash(updated);
    if (typeof window !== 'undefined' && window.location.hash !== hash) {
      // A history entry, so the back button undoes this change.
      window.history.pushState(null, '', hash);
    }
  }, []);

  return {
    state,
    setView: (view: View) => commit({ view }),
    setMode: (mode: Mode) => commit({ mode }),
    setAoi: (aoi: string) => commit({ aoi }),
    setDate: (date: string | null) => commit({ date }),
  };
}
