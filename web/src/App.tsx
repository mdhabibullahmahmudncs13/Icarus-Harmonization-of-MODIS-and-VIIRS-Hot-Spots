/**
 * App shell — wireframe from Implementation plan, section 5.1.
 *
 * Header: title, Raw | Harmonized toggle, source badge.
 * Hero: the series chart (the one memorable element).
 * Everything below the hero arrives in later milestones (F3-F5).
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

  const source = meta?.meta.source ?? null;
  const loading = error === null && (meta === null || series === null);
  const which = import.meta.env.VITE_DATA ?? "mock";
  const rangeLabel =
    series !== null
      ? `${series.rows[0].date.slice(0, 4)} to ${series.rows[series.rows.length - 1].date.slice(0, 4)}`
      : "";

  return (
    <div className="app">
      <MockBanner source={source} />

      <header className="app-header">
        <div className="header-inner">
          <div className="brand">
            <h1 className="brand-title">Icarus</h1>
            <p className="brand-sub">MODIS and VIIRS hotspot harmonization</p>
          </div>
          <SegmentedToggle mode={state.mode} onChange={(mode) => setState({ ...state, mode })} />
          <SourceBadge source={source} />
        </div>
      </header>

      <main className="app-main">
        {loading && (
          <p className="state-msg" role="status">
            {error === null
              ? `Loading the series from ${which === "api" ? "the API" : "the mock files"}…`
              : null}
          </p>
        )}

        {error !== null && (
          <p className="state-msg state-error" role="alert" data-testid="load-error">
            Could not load the data: {error}
          </p>
        )}

        {meta !== null && series !== null && (
          <section className="hero" aria-labelledby="hero-title">
            <figure className="figure">
              <div className="figure-head">
                <div>
                  <h2 id="hero-title">Daily counts, {rangeLabel}</h2>
                  <p className="figure-sub">
                    {state.mode === "raw"
                      ? "Raw mode: every detection counted. The finer VIIRS sensor inflates counts after 2012."
                      : "Harmonized mode: one count per 5.5 km cell per day, so the 2012 sensor step collapses."}
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
                {` ${meta.meta.cell_km} km`} grid. Sensor epoch markers are mock placeholders
                pending verification against the FIRMS docs.
              </figcaption>
            </figure>
          </section>
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
