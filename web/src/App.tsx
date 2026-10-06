import { useCallback, useEffect, useMemo, useState } from 'react';
import type { Dataset } from './contract/types';
import { getDataSource } from './data/DataSource';
import { aggregateToBins } from './lib/series';
import { useAppState } from './state/useAppState';
import { VIEWS, type View } from './state/urlState';
import { Rail } from './components/Rail';
import { SeriesChart } from './components/SeriesChart';
import { CalendarHeatmap } from './components/CalendarHeatmap';
import { RegionMap } from './components/RegionMap';
import {
  AnomalyBox,
  CriticalPeriodPanel,
  MethodsPanel,
  OfflinePanel,
  ValidationCard,
} from './components/panels';
import { ProvenanceDrawer } from './components/ProvenanceDrawer';
import { HelpDialog, KeyboardHint, LoadingSkeleton, MockBanner } from './components/shared';
import { Icon } from './components/Icon';

const TITLES: Record<View, { title: string; sub: string }> = {
  overview: { title: 'Overview', sub: 'Same fires, one honest record.' },
  calendar: { title: 'Calendar', sub: 'Years × 46 eight-day bins.' },
  map: { title: 'Map', sub: 'Grid cells by activity.' },
  anomalies: { title: 'Anomalies', sub: 'Is this period unusual for the season?' },
  critical: { title: 'Critical fire period', sub: 'Onset, peak, end, window mass.' },
  validation: { title: 'Validation', sub: 'Raw vs harmonized agreement over the overlap.' },
  methods: { title: 'Methods', sub: 'What was computed, and on which datasets.' },
  offline: { title: 'Offline', sub: 'Works without the network.' },
};

const THEME_KEY = 'icarus:theme';
type Theme = 'dark' | 'light';
type Overlay = { kind: 'provenance' } | { kind: 'help' } | null;

function initialTheme(): Theme {
  if (typeof window === 'undefined') return 'dark';
  try {
    const saved = window.localStorage.getItem(THEME_KEY);
    if (saved === 'dark' || saved === 'light') return saved;
  } catch {
    /* storage unavailable — fall through to the system preference */
  }
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function formatBbox(bbox: [number, number, number, number]): string {
  const [west, south, east, north] = bbox;
  const lon = `${west}°–${east}°E`;
  const lat = `${south}°–${north}°N`;
  return `${lon} · ${lat}`;
}

export function App() {
  const { state, setView, setMode, setDate } = useAppState();
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [collapsed, setCollapsed] = useState(false);
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [overlay, setOverlay] = useState<Overlay>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* storage unavailable — the theme still applies for this session */
    }
  }, [theme]);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    getDataSource()
      .load()
      .then((d) => !cancelled && setData(d))
      .catch((e: unknown) => !cancelled && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
  }, [reload]);

  const bins = useMemo(
    () => (data ? aggregateToBins(data.series.series, 8) : []),
    [data],
  );

  const transition = useMemo(() => {
    if (!data) return '2012-01-20';
    const starts = data.meta.sensors.filter((s) => s.family === 'VIIRS').map((s) => s.start);
    return starts.sort()[0] ?? '2012-01-20';
  }, [data]);

  const payloadForView = useCallback((): unknown => {
    if (!data) return null;
    switch (state.view) {
      case 'calendar':
        return data.series;
      case 'map':
        return data.cells;
      case 'anomalies':
        return data.anomaly;
      case 'critical':
        return data.criticalPeriod;
      case 'validation':
        return data.validation;
      case 'methods':
        return data.methods;
      case 'offline':
        return data.meta;
      default:
        return data.series;
    }
  }, [data, state.view]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
      ) {
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        setCollapsed((c) => !c);
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k >= '1' && k <= '8') {
        setView(VIEWS[Number(k) - 1]);
      } else if (k === 'r') {
        setMode('raw');
      } else if (k === 'h') {
        setMode('harmonized');
      } else if (k === 't') {
        setTheme((t) => (t === 'dark' ? 'light' : 'dark'));
      } else if (k === 'p') {
        setOverlay({ kind: 'provenance' });
      } else if (e.key === '?') {
        setOverlay({ kind: 'help' });
      } else if (e.key === 'Escape') {
        setOverlay(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setView, setMode]);

  const view: View = state.view;
  const heading = TITLES[view];
  const closeOverlay = () => setOverlay(null);

  return (
    <div className="shell">
      <Rail
        view={view}
        mode={state.mode}
        theme={theme}
        meta={data?.meta.meta ?? null}
        collapsed={collapsed}
        onView={setView}
        onMode={setMode}
        onTheme={setTheme}
        onCollapse={() => setCollapsed((c) => !c)}
      />

      <main className="main">
        {data ? <MockBanner source={data.meta.meta.source} /> : null}

        <header className="page-head">
          <div className="page-head__text">
            <h1 className="page-title">{heading.title}</h1>
            <p className="page-sub">{heading.sub}</p>
          </div>
          <div className="page-head__actions">
            {data ? (
              <span className="region-chip" title="Region bounding box of the loaded dataset">
                <Icon name="area" size={15} />
                <b>{formatBbox(data.meta.meta.region.bbox)}</b>
              </span>
            ) : null}
            <button
              type="button"
              className="btn"
              onClick={() => setOverlay({ kind: 'provenance' })}
              disabled={!data}
              title="Provenance (P)"
            >
              <Icon name="fingerprint" size={16} />
              Provenance
              <span className="btn__key">P</span>
            </button>
            <button
              type="button"
              className="btn btn--quiet"
              onClick={() => setOverlay({ kind: 'help' })}
              aria-label="Keyboard shortcuts"
              title="Keyboard shortcuts (?)"
            >
              <Icon name="help" size={16} />
            </button>
          </div>
        </header>

        {error ? (
          <div className="card">
            <div className="card__body error">
              <strong>Could not load data</strong>
              <span>
                {error}. If you opened the file directly, run <code>npm run dev</code> so the
                payloads are served over HTTP.
              </span>
              <span>
                <button type="button" className="btn btn--primary" onClick={() => setReload((r) => r + 1)}>
                  Try again
                </button>
              </span>
            </div>
          </div>
        ) : !data ? (
          <LoadingSkeleton />
        ) : (
          <>
            {view === 'overview' && (
              <>
                <div className="card">
                  <div className="card__head">
                    <span className="card__title">Daily activity</span>
                    <span className="badge badge--outline">{state.mode}</span>
                  </div>
                  <div className="card__body">
                    <SeriesChart rows={data.series.series} mode={state.mode} transition={transition} />
                    <p className="hint">
                      Flip the mode: raw detections jump when the finer sensor starts; harmonized
                      cell-days stay comparable.
                    </p>
                  </div>
                </div>
                <div className="card">
                  <div className="card__head">
                    <span className="card__title">Burning calendar</span>
                    <span className="badge badge--outline">{state.mode}</span>
                  </div>
                  <div className="card__body">
                    <CalendarHeatmap
                      bins={bins}
                      mode={state.mode}
                      selected={state.date}
                      onSelect={setDate}
                      onClear={() => setDate(null)}
                      theme={theme}
                    />
                  </div>
                </div>
              </>
            )}

            {view === 'calendar' && (
              <div className="card">
                <div className="card__head">
                  <span className="card__title">Burning calendar</span>
                  <span className="badge badge--outline">{state.mode}</span>
                </div>
                <div className="card__body">
                  <CalendarHeatmap
                    bins={bins}
                    mode={state.mode}
                    selected={state.date}
                    onSelect={setDate}
                    onClear={() => setDate(null)}
                    theme={theme}
                  />
                </div>
              </div>
            )}

            {view === 'map' && (
              <div className="card">
                <div className="card__head">
                  <span className="card__title">Region cells</span>
                  <span className="badge badge--outline">{state.mode}</span>
                </div>
                <div className="card__body">
                  <RegionMap
                    cells={data.cells.cells}
                    mode={state.mode}
                    theme={theme}
                  />
                </div>
              </div>
            )}

            {view === 'anomalies' && <AnomalyBox anomaly={data.anomaly} />}
            {view === 'critical' && <CriticalPeriodPanel critical={data.criticalPeriod} />}
            {view === 'validation' && <ValidationCard validation={data.validation} />}
            {view === 'methods' && <MethodsPanel methods={data.methods} />}
            {view === 'offline' && <OfflinePanel source={data.meta.meta.source} />}
          </>
        )}

        <KeyboardHint />
      </main>

      <ProvenanceDrawer
        open={overlay?.kind === 'provenance'}
        meta={data?.meta.meta ?? null}
        label={view}
        payload={payloadForView()}
        onClose={closeOverlay}
      />
      {overlay?.kind === 'help' ? <HelpDialog onClose={closeOverlay} /> : null}
    </div>
  );
}
