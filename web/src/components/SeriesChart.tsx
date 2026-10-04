/**
 * Hero series chart: daily counts 2003-2026, sensor epochs marked.
 *
 * One line, drawn from the currently shown values. Switching mode eases
 * every value from the raw series to the harmonized one over ~600 ms so the
 * false step at the sensor transition visibly collapses; with
 * prefers-reduced-motion it swaps instantly. The chart only ever reads the
 * single fetched SeriesResponse — switching mode never touches the network.
 */
import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import { scaleLinear, scaleUtc } from "d3-scale";
import { line } from "d3-shape";
import type { SeriesResponse, Sensor } from "../contract";
import type { Mode } from "../state/urlState";

const W = 960;
const H = 400;
const M = { top: 28, right: 24, bottom: 48, left: 72 };
const INNER_W = W - M.left - M.right;
const INNER_H = H - M.top - M.bottom;
const DAY_MS = 86400000;
const TRANSITION_MS = 600;

const UNIT: Record<Mode, string> = {
  raw: "detections per day",
  harmonized: "cell-days per day",
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

/** Ease in-out cubic. */
function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
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

  // Memoized geometry — computed once for the single fetched payload.
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

    // Sensor epoch marker: earliest VIIRS epoch (a mock placeholder date).
    const viirsStarts = sensors
      .filter((s) => s.family === "VIIRS")
      .map((s) => s.start)
      .sort();
    const viirsStart = viirsStarts.length > 0 ? viirsStarts[0] : null;

    const selectedIdx =
      selectedDate !== null ? series.rows.findIndex((r) => r.date === selectedDate) : -1;

    return { dates, rawVals, harmVals, x, y, yTicks, yearTicks, viirsStart, selectedIdx };
  }, [series, sensors, selectedDate]);

  const { dates, rawVals, harmVals, x, y, yTicks, yearTicks, viirsStart, selectedIdx } = geo;
  const unit = UNIT[mode];

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

  const pathD = useMemo(() => {
    const gen = line<number>()
      .x((_, i) => x(dates[i]))
      .y((v) => y(v));
    return gen(shown) ?? "";
  }, [shown, x, y, dates]);

  const idxFromClientX = (clientX: number): number => {
    const svg = svgRef.current;
    if (!svg) return 0;
    const rect = svg.getBoundingClientRect();
    const px = ((clientX - rect.left) / rect.width) * W - M.left;
    const t = x.invert(Math.max(0, Math.min(INNER_W, px))).getTime();
    const idx = Math.round((t - dates[0].getTime()) / DAY_MS);
    return Math.max(0, Math.min(dates.length - 1, idx));
  };

  const hoverIdx2 = hoverIdx; // narrowed local for rendering
  const viirsX = viirsStart !== null ? x(new Date(`${viirsStart}T00:00:00Z`)) : null;
  const selectedX = selectedIdx >= 0 ? x(dates[selectedIdx]) : null;

  const readout =
    hoverIdx2 !== null
      ? `${series.rows[hoverIdx2].date} — ${Math.round(shown[hoverIdx2])} ${unit}`
      : "Hover or focus the chart to read a day; click to select the date.";

  return (
    <div className="chart">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="chart-svg"
        role="img"
        tabIndex={0}
        aria-label={`Daily counts chart, ${unit}. Use left and right arrow keys to inspect days, Enter to select a date.`}
        data-testid="series-chart"
        onKeyDown={(e) => {
          const last = dates.length - 1;
          if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
            e.preventDefault();
            const delta = e.key === "ArrowRight" ? 1 : -1;
            const base = hoverIdx2 ?? (e.key === "ArrowRight" ? -1 : last);
            setHoverIdx(Math.max(0, Math.min(last, base + delta)));
          } else if (e.key === "Home") {
            e.preventDefault();
            setHoverIdx(0);
          } else if (e.key === "End") {
            e.preventDefault();
            setHoverIdx(last);
          } else if (e.key === "Enter" && hoverIdx2 !== null) {
            e.preventDefault();
            onSelectDate(series.rows[hoverIdx2].date);
          } else if (e.key === "Escape") {
            setHoverIdx(null);
          }
        }}
      >
        <g transform={`translate(${M.left},${M.top})`}>
          {/* Horizontal gridlines */}
          {yTicks.map((t) => (
            <line key={t} x1={0} x2={INNER_W} y1={y(t)} y2={y(t)} className="gridline" />
          ))}

          {/* Sensor epoch marker — mock placeholder date, labelled as such */}
          {viirsX !== null && (
            <g className="epoch" data-testid="epoch-marker">
              <line x1={viirsX} x2={viirsX} y1={-6} y2={INNER_H} className="epoch-line" />
              <text x={viirsX + 6} y={-12} className="epoch-label">
                VIIRS starts (mock placeholder)
              </text>
            </g>
          )}

          {/* Selected date marker (from the URL) */}
          {selectedX !== null && (
            <line x1={selectedX} x2={selectedX} y1={0} y2={INNER_H} className="selected-line" />
          )}

          {/* The series line */}
          <path
            d={pathD}
            className="series-line"
            data-testid="series-line"
            data-mode={mode}
            fill="none"
          />

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
              if (hoverIdx2 !== null) onSelectDate(series.rows[hoverIdx2].date);
            }}
          />

          {/* Hover hairline, point and tooltip */}
          {hoverIdx2 !== null && (
            <g className="hover-group" pointerEvents="none">
              <line
                x1={x(dates[hoverIdx2])}
                x2={x(dates[hoverIdx2])}
                y1={0}
                y2={INNER_H}
                className="hover-line"
              />
              <circle
                cx={x(dates[hoverIdx2])}
                cy={y(shown[hoverIdx2])}
                r={3.5}
                className="hover-dot"
              />
              <g
                transform={`translate(${
                  x(dates[hoverIdx2]) > INNER_W * 0.7
                    ? x(dates[hoverIdx2]) - 178
                    : x(dates[hoverIdx2]) + 10
                },${Math.max(4, y(shown[hoverIdx2]) - 44)})`}
              >
                <rect width={168} height={40} rx={4} className="tooltip-box" />
                <text x={8} y={16} className="tooltip-date">
                  {series.rows[hoverIdx2].date}
                </text>
                <text x={8} y={32} className="tooltip-value">
                  {Math.round(shown[hoverIdx2])} {unit}
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
            transform={`translate(${-M.left + 14},${INNER_H / 2}) rotate(-90)`}
            textAnchor="middle"
          >
            {unit}
          </text>
        </g>
      </svg>

      <p className="chart-readout" role="status" data-testid="chart-readout">
        {readout}
      </p>
    </div>
  );
}
