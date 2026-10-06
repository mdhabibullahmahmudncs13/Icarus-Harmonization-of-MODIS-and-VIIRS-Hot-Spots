import { useCallback, useEffect, useState } from 'react';
import { buildHash, parseHash, type AppState, type View } from './urlState';
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

  useEffect(() => {
    const onHash = () => setState(parseHash(window.location.hash));
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const commit = useCallback((next: AppState) => {
    setState(next);
    const hash = buildHash(next);
    if (typeof window !== 'undefined' && window.location.hash !== hash) {
      window.history.replaceState(null, '', hash);
    }
  }, []);

  return {
    state,
    setView: (view: View) => commit({ ...state, view }),
    setMode: (mode: Mode) => commit({ ...state, mode }),
    setAoi: (aoi: string) => commit({ ...state, aoi }),
    setDate: (date: string | null) => commit({ ...state, date }),
  };
}
