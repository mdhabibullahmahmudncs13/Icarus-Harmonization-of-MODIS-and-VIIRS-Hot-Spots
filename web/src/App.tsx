import { useEffect, useMemo, useState } from 'react';
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
import { KeyboardHint, MockBanner } from './components/shared';

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

export function App() {
  const { state, setView, setMode, setAoi, setDate } = useAppState();
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [collapsed, setCollapsed] = useState(false);
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<{ label: string; payload: unknown } | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    let cancelled = false;
    getDataSource()
      .load()
      .then((d) => !cancelled && setData(d))
      .catch((e: unknown) => !cancelled && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
  }, []);

  const bins = useMemo(
    () => (data ? aggregateToBins(data.series.series, 8) : []),
    [data],
  );

  const transition = useMemo(() => {
    if (!data) return '2012-01-20';
    const starts = data.meta.sensors.filter((s) => s.family === 'VIIRS').map((s) => s.start);
    return starts.sort()[0] ?? '2012-01-20';
  }, [data]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) return;
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
        setDrawer({ label: state.view, payload: data });
      } else if (e.key === 'Escape') {
        setDrawer(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setView, setMode, state.view, data]);

  const payloadForView = (): unknown => {
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
  };

  const view: View = state.view;
  const heading = TITLES[view];

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

        <header style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <div>
            <h1 className="page-title">{heading.title}</h1>
            <p className="page-sub">{heading.sub}</p>
          </div>
          <button
            type="button"
            className="nav-item"
            style={{ marginLeft: 'auto', width: 'auto' }}
            onClick={() => setDrawer({ label: view, payload: payloadForView() })}
            title="Provenance (P)"
          >
            Provenance (P)
          </button>
        </header>

        {error ? (
          <div className="card">
            <div className="card__body">
              <p className="error">
                Could not load data: {error}. If you opened the file directly, run{' '}
                <code>npm run dev</code> so the mock JSON is served.
              </p>
            </div>
          </div>
        ) : !data ? (
          <div className="card">
            <div className="card__body">
              <p className="empty">Loading…</p>
            </div>
          </div>
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
                  </div>
                  <div className="card__body">
                    <CalendarHeatmap bins={bins} mode={state.mode} onSelect={setDate} />
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
                  <CalendarHeatmap bins={bins} mode={state.mode} onSelect={setDate} />
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
                  <RegionMap cells={data.cells.cells} mode={state.mode} bbox={data.meta.meta.region.bbox} />
                </div>
              </div>
            )}

            {view === 'anomalies' && <AnomalyBox anomaly={data.anomaly} />}
            {view === 'critical' && <CriticalPeriodPanel critical={data.criticalPeriod} />}
            {view === 'validation' && <ValidationCard validation={data.validation} />}
            {view === 'methods' && <MethodsPanel methods={data.methods} />}
            {view === 'offline' && <OfflinePanel source={data.meta.meta.source} />}

            <section aria-label="Areas of interest" style={{ display: 'none' }}>
              {data.aoi.presets.map((p) => (
                <button key={p.id} type="button" onClick={() => setAoi(p.id)}>
                  {p.name}
                </button>
              ))}
              <span>{state.aoi}</span>
            </section>
          </>
        )}

        <KeyboardHint />
      </main>

      <ProvenanceDrawer
        open={drawer !== null}
        meta={data?.meta.meta ?? null}
        label={drawer?.label ?? ''}
        payload={drawer?.payload ?? null}
        onClose={() => setDrawer(null)}
      />
    </div>
  );
}

