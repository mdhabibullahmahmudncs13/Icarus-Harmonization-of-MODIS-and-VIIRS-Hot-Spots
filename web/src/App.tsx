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
import { ProvenanceDrawer } from "./components/ProvenanceDrawer";
import { spotsFromCells } from "./globe/hotspots";
import { GLOBE_SPEC } from "./globe/globeSpec";
import type { GlobeSpot } from "./globe/globeSpec";
import type { CellsResponse, MetaResponse, SeriesResponse } from "./contract";

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
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  // What the hero camera is looking at; the panel and the globe share it.
  const [view, setView] = useState<GlobeView>({ kind: "region" });

  useEffect(() => {
    let cancelled = false;
    Promise.all([dataSource.getMeta(), dataSource.getSeries(), dataSource.getCells()])
      .then(([m, s, c]) => {
        if (!cancelled) {
          setMeta(m);
          setSeries(s);
          setCells(c);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [dataSource]);

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
            <a href="#timeline">Timeline</a>
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
                Data: NASA FIRMS — MODIS C6.1 hotspots, VIIRS 375 m NOAA-20, VIIRS 375 m NOAA-21,
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
