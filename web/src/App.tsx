/**
 * App shell.
 *
 * Section 1 is the hero: the procedural Earth (see `globe/createEarthGlobe`)
 * with the study region's own grid cells glowing on it, and the same cells
 * listed as numbers beside it. Section 2 is the timeline — the record the
 * globe is a picture of. The Raw | Harmonized toggle in the top bar drives
 * both, and every figure opens its source JSON.
 *
 * State (mode + selected date) lives in the URL. Data is fetched once per
 * source; toggling mode never refetches.
 */
import { useCallback, useEffect, useMemo, useState, type ReactElement } from "react";
import { createDataSource } from "./data";
import { useAppState } from "./state/useAppState";
import { MockBanner } from "./components/MockBanner";
import { SourceBadge } from "./components/SourceBadge";
import { SegmentedToggle } from "./components/SegmentedToggle";
import { SeriesChart } from "./components/SeriesChart";
import { GlobeHero, type GlobeView } from "./components/GlobeHero";
import { HottestCells } from "./components/HottestCells";
import { CalendarHeatmap } from "./components/CalendarHeatmap";
import { RegionMap } from "./components/RegionMap";
import { ValidationCard } from "./components/ValidationCard";
import { AnomalyBox } from "./components/AnomalyBox";
import { MethodsPanel } from "./components/MethodsPanel";
import { ProvenanceDrawer } from "./components/ProvenanceDrawer";
import { spotsFromCells } from "./globe/hotspots";
import { GLOBE_SPEC } from "./globe/globeSpec";
import type { GlobeSpot } from "./globe/globeSpec";
import type {
  AnomalyResponse,
  BaselineResponse,
  CellsResponse,
  MetaResponse,
  MethodsResponse,
  SeriesResponse,
  ValidationResponse,
} from "./contract";

interface DrawerState {
  title: string;
  payload: unknown;
}

/** Sun-with-a-step mark (DESIGN.md §4.7), drawn locally, no icon CDN. */
function Mark(): ReactElement {
  return (
    <svg className="mark" width="30" height="28" viewBox="0 0 30 28" aria-hidden="true">
      <circle cx="22" cy="8" r="5.5" fill="none" stroke="var(--text-1)" strokeWidth="1.75" />
      <path
        d="M2 22 H12 V14 C16 14 18.5 10.5 27 7.5"
        fill="none"
        stroke="var(--text-1)"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="14" r="2.4" fill="var(--harmonized)" />
    </svg>
  );
}

export default function App(): ReactElement {
  const dataSource = useMemo(() => createDataSource(), []);
  const [state, setState] = useAppState();
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [series, setSeries] = useState<SeriesResponse | null>(null);
  const [cells, setCells] = useState<CellsResponse | null>(null);
  const [baseline, setBaseline] = useState<BaselineResponse | null>(null);
  const [anomaly, setAnomaly] = useState<AnomalyResponse | null>(null);
  const [anomalyError, setAnomalyError] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationResponse | null>(null);
  const [methods, setMethods] = useState<MethodsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  // What the hero camera is looking at; the panel and the globe share it.
  const [view, setView] = useState<GlobeView>({ kind: "region" });

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      dataSource.getMeta(),
      dataSource.getSeries(),
      dataSource.getCells(),
      dataSource.getBaseline(),
      dataSource.getValidation(),
      dataSource.getMethods(),
    ])
      .then(([m, s, c, b, v, meth]) => {
        if (!cancelled) {
          setMeta(m);
          setSeries(s);
          setCells(c);
          setBaseline(b);
          setValidation(v);
          setMethods(meth);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [dataSource]);

  // The anomaly answers for one day, and only one day: until the reader picks
  // one, ask about the last day in the record; when they pick a day, ask again
  // for that day. The mock source ignores the date and returns its one sample.
  const lastDate =
    series !== null && series.rows.length > 0 ? series.rows[series.rows.length - 1].date : null;
  const anomalyDate = state.date ?? lastDate;

  useEffect(() => {
    if (anomalyDate === null) return;
    let cancelled = false;
    dataSource
      .getAnomaly(anomalyDate)
      .then((a) => {
        if (!cancelled) {
          setAnomaly(a);
          setAnomalyError(null);
        }
      })
      .catch((e: unknown) => {
        // A day the record does not cover is not a page failure: say so in the
        // box instead of blanking the whole app.
        if (!cancelled) {
          setAnomaly(null);
          setAnomalyError(e instanceof Error ? e.message : String(e));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dataSource, anomalyDate]);

  // DESIGN.md §6.1: R and H set the mode from anywhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t !== null && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable))
        return;
      if (e.key === "r" || e.key === "R") setState({ ...state, mode: "raw" });
      else if (e.key === "h" || e.key === "H") setState({ ...state, mode: "harmonized" });
      // Escape belongs to the drawer while it is open.
      else if (e.key === "Escape" && drawer === null) setView({ kind: "earth" });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state, setState, drawer]);

  const source = meta?.meta.source ?? null;
  const loading = error === null && (meta === null || series === null);
  const which = import.meta.env.VITE_DATA ?? "mock";
  const rangeLabel =
    series !== null
      ? `${series.rows[0].date.slice(0, 4)} to ${series.rows[series.rows.length - 1].date.slice(0, 4)}`
      : "";
  // Stable identity: a new onClose on every render would re-register the
  // drawer's own Escape listener mid-dispatch and swallow the key.
  const closeDrawer = useCallback(() => setDrawer(null), []);
  const spots = useMemo(() => (cells === null ? [] : spotsFromCells(cells)), [cells]);
  const selectedId = view.kind === "cell" ? view.id : null;
  const drawnCells = Math.min(GLOBE_SPEC.hotspots.maxDots, spots.length);
  const selectSpot = (spot: GlobeSpot): void =>
    setView({ kind: "cell", id: spot.id, lat: spot.lat, lon: spot.lon });
  // Same selection, reached from the flat map instead of the cell table.
  const selectCell = (id: string, lat: number, lon: number): void =>
    setView({ kind: "cell", id, lat, lon });

  return (
    <div className="app">
      <a className="skip-link" href="#timeline">
        Skip to the chart
      </a>

      <div className="top-shell">
        <MockBanner source={source} />
        <header className="top-bar">
          <div className="brand">
            <Mark />
            <span className="wordmark">Icarus</span>
          </div>
          <nav className="top-nav" aria-label="Sections">
            <a href="#overview">Overview</a>
            <a href="#map">Map</a>
            <a href="#timeline">Timeline</a>
            <a href="#calendar">Calendar</a>
            <a href="#evidence">Evidence</a>
            <a href="#methods">Methods</a>
            <a href="#status">Status</a>
          </nav>
          <SegmentedToggle mode={state.mode} onChange={(mode) => setState({ ...state, mode })} />
          <SourceBadge source={source} />
        </header>
      </div>

      <main className="app-main">
        {loading && (
          <p className="state-msg" role="status">
            {`Loading the series from ${which === "api" ? "the API" : "the mock files"}…`}
          </p>
        )}

        {error !== null && (
          <p className="state-msg state-error" role="alert" data-testid="load-error">
            Could not load the data: {error}
          </p>
        )}

        {meta !== null && series !== null && (
          <>
            <section className="hero" id="overview" aria-labelledby="hero-title">
              <GlobeHero
                hotspots={spots}
                regionBounds={meta.meta.region.bbox}
                mode={state.mode}
                view={view}
                onViewChange={setView}
              >
                <div className="hero-copy">
                  <h1 className="display" id="hero-title">
                    Same fires. One honest record.
                  </h1>
                  <p className="lede">
                    Reconciling 1 km MODIS and 375 m VIIRS detections so sensor changes do not look
                    like fire trends.
                  </p>
                  <p className="hero-legend">
                    {state.mode === "raw"
                      ? "Each glowing dot is one grid cell, sized by every detection counted."
                      : "Each glowing dot is one grid cell, sized by distinct cell-days."}
                    {spots.length > 0
                      ? ` The globe draws the ${drawnCells.toLocaleString("en-US")} busiest of ${spots.length.toLocaleString("en-US")} cells on a ${meta.meta.cell_km} km grid, inside the outlined region; the panel and the cells JSON carry all of them.`
                      : ""}
                  </p>
                </div>
              </GlobeHero>

              <HottestCells
                spots={spots}
                mode={state.mode}
                selectedId={selectedId}
                onSelect={selectSpot}
                regionBounds={meta.meta.region.bbox}
                cellKm={meta.meta.cell_km}
                dateRange={meta.meta.date_range}
                onViewSource={() => setDrawer({ title: "Grid cells", payload: cells })}
              />
            </section>

            {cells !== null && (
              <section className="glass-tile map-tile" id="map" aria-labelledby="map-title">
                <div className="figure-head">
                  <div>
                    <h2 id="map-title">The region, cell by cell</h2>
                    <p className="figure-sub">
                      {state.mode === "raw"
                        ? "Raw mode: every detection counted in the cell. The finer VIIRS sensor darkens cells it sees more than once."
                        : "Harmonized mode: one shading step per cell-day, so a finer sensor cannot darken a cell on its own."}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="ghost-btn"
                    onClick={() => setDrawer({ title: "Grid cells", payload: cells })}
                  >
                    View cells JSON
                  </button>
                </div>

                <RegionMap
                  cells={cells}
                  mode={state.mode}
                  selectedId={selectedId}
                  onSelect={selectCell}
                />

                <p className="figure-note">
                  No basemap and no tiles: the map draws the payload's own cell polygons, so the
                  page still makes no third-party request. Geometry comes from the API's bounds;
                  nothing is computed here.
                </p>
              </section>
            )}

            <section className="glass-tile chart-tile" id="timeline" aria-labelledby="chart-title">
              <figure className="figure">
                <div className="figure-head">
                  <div>
                    <h2 id="chart-title">Daily counts, {rangeLabel}</h2>
                    <p className="figure-sub">
                      {state.mode === "raw"
                        ? "Raw mode: every detection counted. The finer VIIRS sensor inflates counts after 2012."
                        : "Harmonized mode: one count per cell per day, so the 2012 sensor step collapses."}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="ghost-btn"
                    onClick={() => setDrawer({ title: "Daily counts", payload: series })}
                  >
                    View source JSON
                  </button>
                </div>

                <SeriesChart
                  series={series}
                  sensors={meta.sensors}
                  mode={state.mode}
                  selectedDate={state.date}
                  onSelectDate={(date) => setState({ ...state, date })}
                />

                <figcaption className="figure-note">
                  Units: raw counts are detections; harmonized counts are distinct cell-days on a
                  {` ${meta.meta.cell_km} km`} grid. Era bands and sensor epoch markers are derived
                  from sensor windows whose dates are mock placeholders pending verification against
                  the FIRMS docs.
                </figcaption>
              </figure>
            </section>

            <section
              className="glass-tile calendar-tile"
              id="calendar"
              aria-labelledby="calendar-title"
            >
              <div className="figure-head">
                <div>
                  <h2 id="calendar-title">Burning calendar, {rangeLabel}</h2>
                  <p className="figure-sub">
                    {state.mode === "raw"
                      ? "Raw mode: every detection counted. Watch the darker band after 2012 fill in."
                      : "Harmonized mode: one count per cell-day, so a finer sensor cannot inflate a day."}
                  </p>
                </div>
              </div>

              <CalendarHeatmap
                series={series}
                mode={state.mode}
                selectedDate={state.date}
                onSelectDate={(date) => setState({ ...state, date })}
              />

              <p className="figure-note">
                Same payload as the timeline, recut by year and day, so the toggle recolors it
                without a second fetch. Select a day here or on the chart to drive the anomaly box.
              </p>
            </section>

            <div className="evidence-grid">
              {validation !== null && (
                <ValidationCard
                  validation={validation}
                  onViewSource={() => setDrawer({ title: "Validation", payload: validation })}
                />
              )}
              {anomaly !== null && baseline !== null && (
                <AnomalyBox
                  anomaly={anomaly}
                  baseline={baseline}
                  selectedDate={state.date}
                  onViewSource={() => setDrawer({ title: "Anomaly", payload: anomaly })}
                />
              )}
              {anomaly === null && baseline !== null && (
                <section
                  className="glass-tile anomaly-tile"
                  id="anomaly"
                  aria-labelledby="anomaly-title"
                  data-testid="anomaly-unavailable"
                >
                  <div className="figure-head">
                    <div>
                      <h2 id="anomaly-title">Is this unusual?</h2>
                      <p className="figure-sub">
                        {anomalyError === null
                          ? `${anomalyDate ?? "That day"} against the seasonal baseline.`
                          : "This day has no answer in the record."}
                      </p>
                    </div>
                  </div>
                  <p className="figure-note">
                    {anomalyError ?? "Reading the day's percentile against the baseline window…"}
                  </p>
                </section>
              )}
            </div>

            {methods !== null && (
              <MethodsPanel
                methods={methods}
                onViewSource={() => setDrawer({ title: "Methods", payload: methods })}
              />
            )}

            <aside className="glass-tile status-tile" id="status" aria-label="Status">
              <h2 className="tile-title">Status</h2>
              <div className="status-row">
                <span className="updated">Data last updated {meta.meta.generated_at}</span>
              </div>
              <div className="status-row">
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={() => setDrawer({ title: "Meta", payload: meta })}
                >
                  View meta JSON
                </button>
              </div>
              <p className="datasets">
                Grid {meta.meta.cell_km} km, confidence ≥ {meta.meta.min_confidence}. Window{" "}
                {meta.meta.date_range[0]} to {meta.meta.date_range[1]}.
              </p>
            </aside>

            <footer className="app-footer">
              <p>
                Data: NASA FIRMS. MODIS C6.1 hotspots, VIIRS 375 m NOAA-20, VIIRS 375 m NOAA-21,
                VIIRS 375 m Suomi-NPP (Suomi-NPP data ends 1 Nov 2026; MODIS is being retired).
                Product details at{" "}
                <a href="https://firms.modaps.eosdis.nasa.gov/" rel="noreferrer noopener">
                  firms.modaps.eosdis.nasa.gov
                </a>
                . Land mask: Natural Earth 1:110m land (public domain). Icarus is Apache-2.0. Mock
                data is never evidence.
              </p>
            </footer>
          </>
        )}
      </main>

      <ProvenanceDrawer
        open={drawer !== null}
        title={drawer?.title ?? ""}
        payload={drawer?.payload}
        onClose={closeDrawer}
      />
    </div>
  );
}
