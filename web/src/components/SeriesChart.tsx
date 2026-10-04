/**
 * Hero timeline chart (DESIGN.md §7.2): daily counts 2003-2026 with era
 * bands from sensor windows, a sensor-transition marker, a ghost line for
 * the inactive mode with direct Raw/Harmonized end labels (never color
 * alone), and a mono tooltip.
 *
 * Switching mode eases every value from the raw series to the harmonized
 * one over 700 ms (DESIGN.md §10) so the false step visibly collapses;
 * with prefers-reduced-motion it swaps instantly. The chart only ever
 * reads the single fetched SeriesResponse — switching mode never touches
 * the network. Every number rendered here comes from the payload; the
 * frontend displays values and never computes statistics.
 */
import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import { scaleLinear, scaleUtc } from "d3-scale";
import { line } from "d3-shape";
import type { SeriesResponse, Sensor } from "../contract";
import type { Mode } from "../state/urlState";

const W = 1040;
const H = 420;
const M = { top: 40, right: 108, bottom: 48, left: 72 };
const INNER_W = W - M.left - M.right;
const INNER_H = H - M.top - M.bottom;
const DAY_MS = 86400000;
const TRANSITION_MS = 700; // DESIGN.md §10: mode toggle morph

const UNIT: Record<Mode, string> = {
  raw: "detections per day",
  harmonized: "cell-days per day",
};

const LABEL: Record<Mode, string> = {
  raw: "Raw",
  harmonized: "Harmonized",
};

/** Round a maximum up to a friendly axis top. */
function niceCeil(max: number): number {
  if (max <= 0) return 1;
  const mag = 10 ** Math.floor(Math.log10(max));
  const norm = max / mag;
  const steps = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];
  const nice = steps.find((s) => norm <= s + 1e-9) ?? 10;
  return nice * mag;
}

/** Cubic in-out (DESIGN.md §10). */
function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

interface EraBand {
  x0: number;
  x1: number;
  label: string;
  cls: string;
}

export interface SeriesChartProps {
  series: SeriesResponse;
  sensors: Sensor[];
  mode: Mode;
  selectedDate: string | null;
  onSelectDate: (date: string) => void;
}

export function SeriesChart({
  series,
  sensors,
  mode,
  selectedDate,
  onSelectDate,
}: SeriesChartProps): ReactElement {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  // Geometry computed once for the single fetched payload.
  const geo = useMemo(() => {
    const dates = series.rows.map((r) => new Date(`${r.date}T00:00:00Z`));
    const rawVals = Float64Array.from(series.rows.map((r) => r.raw_total));
    const harmVals = Float64Array.from(series.rows.map((r) => r.harm_total));
    const max = niceCeil(Math.max(...rawVals, ...harmVals));
    const x = scaleUtc()
      .domain([dates[0], dates[dates.length - 1]])
      .range([0, INNER_W]);
    const y = scaleLinear().domain([0, max]).range([INNER_H, 0]);
    const yTicks = [0, 1, 2, 3, 4].map((i) => (max / 4) * i);
    const startYear = dates[0].getUTCFullYear();
    const endYear = dates[dates.length - 1].getUTCFullYear();
    const yearTicks: number[] = [];
    for (let yr = startYear; yr <= endYear; yr += 3) yearTicks.push(yr);
    if (yearTicks[yearTicks.length - 1] !== endYear) yearTicks.push(endYear);

    // Era bands and the transition marker, derived from /api/meta sensor
    // windows (whose mock dates are placeholders — labelled as such below).
    const t0 = dates[0].getTime();
    const t1 = dates[dates.length - 1].getTime();
    const clampT = (t: number): number => Math.min(t1, Math.max(t0, t));
    const viirsStartStr =
      sensors
        .filter((s) => s.family === "VIIRS")
        .map((s) => s.start)
        .sort()[0] ?? null;
    const modisEndStr = sensors.find((s) => s.family === "MODIS")?.end ?? null;
    const eras: EraBand[] = [];
    let viirsX: number | null = null;
    if (viirsStartStr !== null) {
      const vs = clampT(Date.parse(`${viirsStartStr}T00:00:00Z`));
      const vsDate = new Date(vs);
      viirsX = x(vsDate);
      eras.push({ x0: 0, x1: viirsX, label: "MODIS only", cls: "era-band--modis" });
      const me = modisEndStr !== null ? clampT(Date.parse(`${modisEndStr}T00:00:00Z`)) : t1;
      eras.push({
        x0: viirsX,
        x1: x(new Date(me)),
        label: "Overlap",
        cls: "era-band--overlap",
      });
      if (me < t1) {
        eras.push({ x0: x(new Date(me)), x1: INNER_W, label: "VIIRS era", cls: "era-band--viirs" });
      }
    }

    const selectedIdx =
      selectedDate !== null ? series.rows.findIndex((r) => r.date === selectedDate) : -1;

    return { dates, rawVals, harmVals, x, y, yTicks, yearTicks, eras, viirsX, selectedIdx };
  }, [series, sensors, selectedDate]);

  const { dates, rawVals, harmVals, x, y, yTicks, yearTicks, eras, viirsX, selectedIdx } = geo;
  const unit = UNIT[mode];
  const ghostVals = mode === "raw" ? harmVals : rawVals;
  const ghostMode: Mode = mode === "raw" ? "harmonized" : "raw";

  // Shown values: animate from wherever we are to the selected mode.
  const [shown, setShown] = useState<Float64Array>(() =>
    (mode === "raw" ? rawVals : harmVals).slice(),
  );
  const shownRef = useRef(shown);
  useEffect(() => {
    shownRef.current = shown;
  }, [shown]);

  useEffect(() => {
    const from = shownRef.current;
    const to = mode === "raw" ? rawVals : harmVals;
    if (prefersReducedMotion() || from.length !== to.length) {
      shownRef.current = to;
      setShown(to);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const frame = (now: number): void => {
      const p = Math.min(1, (now - t0) / TRANSITION_MS);
      const e = easeInOutCubic(p);
      const next = new Float64Array(to.length);
      for (let i = 0; i < to.length; i++) next[i] = from[i] + (to[i] - from[i]) * e;
      shownRef.current = next;
      setShown(next);
      if (p < 1) raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [mode, rawVals, harmVals]);

  const pathD = useMemo(
    () =>
      line<number>()
        .x((_, i) => x(dates[i]))
        .y((v) => y(v))(shown) ?? "",
    [shown, x, y, dates],
  );
  const ghostD = useMemo(
    () =>
      line<number>()
        .x((_, i) => x(dates[i]))
        .y((v) => y(v))(ghostVals) ?? "",
    [ghostVals, x, y, dates],
  );

  const idxFromClientX = (clientX: number): number => {
    const svg = svgRef.current;
    if (!svg) return 0;
    const rect = svg.getBoundingClientRect();
    const px = ((clientX - rect.left) / rect.width) * W - M.left;
    const t = x.invert(Math.max(0, Math.min(INNER_W, px))).getTime();
    const idx = Math.round((t - dates[0].getTime()) / DAY_MS);
    return Math.max(0, Math.min(dates.length - 1, idx));
  };

  const hoverRow = hoverIdx !== null ? series.rows[hoverIdx] : null;
  const last = dates.length - 1;
  const activeEndY = y(shown[last]);
  let ghostEndY = y(ghostVals[last]);
  if (Math.abs(activeEndY - ghostEndY) < 14) ghostEndY = activeEndY + 14;

  const readout =
    hoverRow !== null
      ? `${hoverRow.date} — ${mode === "raw" ? hoverRow.raw_total : hoverRow.harm_total} ${unit}`
      : "Hover or focus the chart to read a day; click to select the date.";

  return (
    <div className="chart">
      <div className="chart-scroll">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="chart-svg"
          role="img"
          tabIndex={0}
          aria-label={`Daily counts chart, ${unit}. Era bands show the sensor transition. Use left and right arrow keys to inspect days, Enter to select a date.`}
          data-testid="series-chart"
          onKeyDown={(e) => {
            const len = dates.length - 1;
            if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
              e.preventDefault();
              const delta = e.key === "ArrowRight" ? 1 : -1;
              const base = hoverIdx ?? (e.key === "ArrowRight" ? -1 : len);
              setHoverIdx(Math.max(0, Math.min(len, base + delta)));
            } else if (e.key === "Home") {
              e.preventDefault();
              setHoverIdx(0);
            } else if (e.key === "End") {
              e.preventDefault();
              setHoverIdx(len);
            } else if (e.key === "Enter" && hoverIdx !== null) {
              e.preventDefault();
              onSelectDate(series.rows[hoverIdx].date);
            } else if (e.key === "Escape") {
              setHoverIdx(null);
            }
          }}
        >
          <g transform={`translate(${M.left},${M.top})`}>
            {/* Era bands from sensor windows */}
            {eras.map((era) => (
              <rect
                key={era.label}
                className={`era-band ${era.cls}`}
                x={era.x0}
                y={0}
                width={Math.max(0, era.x1 - era.x0)}
                height={INNER_H}
              />
            ))}
            {eras
              .filter((era) => era.x1 - era.x0 > 72)
              .map((era) => (
                <text
                  key={`${era.label}-label`}
                  className="era-label"
                  x={(era.x0 + era.x1) / 2}
                  y={-18}
                  textAnchor="middle"
                >
                  {era.label}
                </text>
              ))}

            {/* Horizontal gridlines */}
            {yTicks.map((t) => (
              <line key={t} x1={0} x2={INNER_W} y1={y(t)} y2={y(t)} className="gridline" />
            ))}

            {/* Sensor transition marker — mock placeholder dates, labelled as such */}
            {viirsX !== null && (
              <g className="epoch" data-testid="epoch-marker">
                <line x1={viirsX} x2={viirsX} y1={-6} y2={INNER_H} className="epoch-line" />
                <text
                  className="epoch-label"
                  x={viirsX > INNER_W - 150 ? viirsX - 8 : viirsX + 8}
                  y={INNER_H - 10}
                  textAnchor={viirsX > INNER_W - 150 ? "end" : "start"}
                >
                  Sensor transition
                </text>
              </g>
            )}

            {/* Selected date marker (from the URL) */}
            {selectedIdx >= 0 && (
              <line
                x1={x(dates[selectedIdx])}
                x2={x(dates[selectedIdx])}
                y1={0}
                y2={INNER_H}
                className="selected-line"
              />
            )}

            {/* Ghost line: the inactive mode, always visible for comparison */}
            <path d={ghostD} className="ghost-line" />

            {/* The active series line */}
            <path
              d={pathD}
              className="series-line"
              data-testid="series-line"
              data-mode={mode}
              fill="none"
            />

            {/* Direct labels at the right ends (never color alone) */}
            <text
              className={`line-label line-label--${mode}`}
              x={INNER_W + 10}
              y={activeEndY}
              dy="0.32em"
            >
              {LABEL[mode]}
            </text>
            <text
              className="line-label line-label--ghost"
              x={INNER_W + 10}
              y={ghostEndY}
              dy="0.32em"
            >
              {LABEL[ghostMode]}
            </text>

            {/* Interaction overlay */}
            <rect
              x={0}
              y={0}
              width={INNER_W}
              height={INNER_H}
              fill="transparent"
              onMouseMove={(e) => setHoverIdx(idxFromClientX(e.clientX))}
              onMouseLeave={() => setHoverIdx(null)}
              onClick={() => {
                if (hoverIdx !== null) onSelectDate(series.rows[hoverIdx].date);
              }}
            />

            {/* Hover hairline, point and mono tooltip */}
            {hoverRow !== null && hoverIdx !== null && (
              <g className="hover-group" pointerEvents="none">
                <line
                  x1={x(dates[hoverIdx])}
                  x2={x(dates[hoverIdx])}
                  y1={0}
                  y2={INNER_H}
                  className="hover-line"
                />
                <circle
                  cx={x(dates[hoverIdx])}
                  cy={y(shown[hoverIdx])}
                  r={4}
                  className="hover-dot"
                  data-mode={mode}
                />
                <g
                  transform={`translate(${
                    x(dates[hoverIdx]) > INNER_W * 0.7
                      ? x(dates[hoverIdx]) - 184
                      : x(dates[hoverIdx]) + 12
                  },${Math.max(4, y(shown[hoverIdx]) - 58)})`}
                >
                  <rect width={172} height={56} rx={8} className="tooltip-box" />
                  <text x={10} y={17} className="tooltip-date">
                    {hoverRow.date}
                  </text>
                  <text
                    x={10}
                    y={33}
                    className={`tooltip-value${mode === "raw" ? " is-active" : ""}`}
                  >
                    Raw: {hoverRow.raw_total}
                  </text>
                  <text
                    x={10}
                    y={48}
                    className={`tooltip-value${mode === "harmonized" ? " is-active" : ""}`}
                  >
                    Harmonized: {hoverRow.harm_total}
                  </text>
                </g>
              </g>
            )}

            {/* X axis */}
            <line x1={0} x2={INNER_W} y1={INNER_H} y2={INNER_H} className="axis-line" />
            {yearTicks.map((yr) => (
              <g key={yr} transform={`translate(${x(new Date(Date.UTC(yr, 0, 1)))},${INNER_H})`}>
                <line y2={5} className="axis-line" />
                <text y={18} className="tick-label" textAnchor="middle">
                  {yr}
                </text>
              </g>
            ))}
          </g>

          {/* Y axis */}
          <g transform={`translate(${M.left},${M.top})`}>
            {yTicks.map((t) => (
              <text key={t} x={-10} y={y(t)} dy="0.32em" className="tick-label" textAnchor="end">
                {t}
              </text>
            ))}
            <text
              className="axis-title"
              transform={`translate(${-M.left + 16},${INNER_H / 2}) rotate(-90)`}
              textAnchor="middle"
            >
              {unit}
            </text>
          </g>
        </svg>
      </div>

      <p className="chart-readout" role="status" data-testid="chart-readout">
        {readout}
      </p>
    </div>
  );
}
