/**
 * App shell — docs/DESIGN.md v2: frosted glass over a pale mint mesh
 * ground, floating top bar with the global RAW | HARMONIZED toggle, one
 * hero tile whose thesis is the headline over the timeline (build order
 * step 1-2: shell + timeline first; globe and calendar arrive in F3+).
 *
 * State (mode + selected date) lives in the URL. Data is fetched once per
 * source; toggling mode never refetches.
 */
import { useEffect, useMemo, useState, type ReactElement } from "react";
import { createDataSource } from "./data";
import { useAppState } from "./state/useAppState";
import { MockBanner } from "./components/MockBanner";
import { SourceBadge } from "./components/SourceBadge";
import { SegmentedToggle } from "./components/SegmentedToggle";
import { SeriesChart } from "./components/SeriesChart";
import { ProvenanceDrawer } from "./components/ProvenanceDrawer";
import type { MetaResponse, SeriesResponse } from "./contract";

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
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<DrawerState | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([dataSource.getMeta(), dataSource.getSeries()])
      .then(([m, s]) => {
        if (!cancelled) {
          setMeta(m);
          setSeries(s);
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
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state, setState]);

  const source = meta?.meta.source ?? null;
  const loading = error === null && (meta === null || series === null);
  const which = import.meta.env.VITE_DATA ?? "mock";
  const rangeLabel =
    series !== null
      ? `${series.rows[0].date.slice(0, 4)} to ${series.rows[series.rows.length - 1].date.slice(0, 4)}`
      : "";

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
            <div className="bento">
              <section className="glass-tile hero-tile" id="timeline" aria-labelledby="hero-title">
                <h1 className="display" id="hero-title">
                  Same fires. One honest record.
                </h1>
                <p className="lede">
                  Reconciling 1 km MODIS and 375 m VIIRS detections so sensor changes do not look
                  like fire trends.
                </p>

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
                    {` ${meta.meta.cell_km} km`} grid. Era bands and sensor epoch markers are
                    derived from sensor windows whose dates are mock placeholders pending
                    verification against the FIRMS docs.
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
            </div>

            <footer className="app-footer">
              <p>
                Data: NASA FIRMS — MODIS C6.1 hotspots, VIIRS 375 m NOAA-20, VIIRS 375 m NOAA-21,
                VIIRS 375 m Suomi-NPP (Suomi-NPP data ends 1 Nov 2026; MODIS is being retired).
                Product details at{" "}
                <a href="https://firms.modaps.eosdis.nasa.gov/" rel="noreferrer noopener">
                  firms.modaps.eosdis.nasa.gov
                </a>
                . Icarus is Apache-2.0. Mock data is never evidence.
              </p>
            </footer>
          </>
        )}
      </main>

      <ProvenanceDrawer
        open={drawer !== null}
        title={drawer?.title ?? ""}
        payload={drawer?.payload}
        onClose={() => setDrawer(null)}
      />
    </div>
  );
}
