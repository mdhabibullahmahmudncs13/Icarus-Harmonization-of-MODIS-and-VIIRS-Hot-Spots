/**
 * CalendarHeatmap — the burning-activity calendar (Implementation plan F3).
 *
 * A year x day-of-year grid driven by the same SeriesResponse the line chart
 * uses, so flipping Raw | Harmonized recolors it with no refetch. Each cell
 * is one calendar day; the ramp is bucketed from that mode's own maximum.
 * Clicking a day selects it (the selection lives in the URL), which is how
 * the calendar and the timeline stay one record.
 *
 * Nothing here is computed: every value comes from the payload verbatim.
 * Bucketing is presentation, not statistics.
 */
import { useMemo, useRef, useState, type ReactElement } from "react";
import { buildCalendar, MONTH_STARTS, rampLevel, daysInYear } from "../charts/calendar";
import type { SeriesResponse } from "../contract";
import type { Mode } from "../state/urlState";

const CELL = 3;
const STEP = 4;
const LEFT = 36;
const TOP = 15;
const UNIT: Record<Mode, string> = {
  raw: "detections",
  harmonized: "cell-days",
};

export interface CalendarHeatmapProps {
  series: SeriesResponse;
  mode: Mode;
  selectedDate: string | null;
  onSelectDate: (date: string) => void;
}

export function CalendarHeatmap({
  series,
  mode,
  selectedDate,
  onSelectDate,
}: CalendarHeatmapProps): ReactElement {
  // One render pass per toggle. Wrapping mode in useDeferredValue was measured
  // and reverted: useMemo only skips buildCalendar, so React still rebuilt all
  // ~8.7k cell vnodes in the urgent pass, then again in the deferred one.
  const model = useMemo(() => buildCalendar(series, mode), [series, mode]);
  const svgRef = useRef<SVGSVGElement>(null);
  const [cursor, setCursor] = useState<{ year: number; doy: number } | null>(null);

  const width = LEFT + 366 * STEP + 2;
  const height = TOP + model.years.length * STEP + 4;
  const unit = UNIT[mode];

  const active = cursor ?? (selectedDate !== null ? { ...doyOf(selectedDate, model.years) } : null);
  const activeValue = active !== null ? model.valueAt(active.year, active.doy) : null;
  const activeDate = active !== null ? model.dateAt(active.year, active.doy) : null;

  const readout =
    active !== null && activeDate !== null
      ? `${activeDate}: ${activeValue ?? 0} ${unit}. Enter selects this day.`
      : "Each row is one year, each column one calendar day. Hover or focus a day to read it; click to select it.";

  const move = (dDay: number, dYear: number): void => {
    if (active === null) {
      setCursor({ year: model.years[0], doy: 1 });
      return;
    }
    const yi = Math.max(
      0,
      Math.min(model.years.length - 1, model.years.indexOf(active.year) + dYear),
    );
    const doy = Math.max(1, Math.min(366, active.doy + dDay));
    setCursor({ year: model.years[yi], doy });
  };

  /**
   * Map a pointer event to a day in the grid.
   *
   * One handler for the whole calendar. Attaching onMouseEnter and onClick
   * to every cell put two function props on each of ~8.7k rects on every
   * render, which is a large part of why the toggle repaint measured 220 ms.
   */
  const hitTest = (clientX: number, clientY: number): { year: number; doy: number } | null => {
    const svg = svgRef.current;
    if (svg === null) return null;
    const rect = svg.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return null;
    const x = ((clientX - rect.left) / rect.width) * width;
    const y = ((clientY - rect.top) / rect.height) * height;
    const row = Math.floor((y - TOP) / STEP);
    const col = Math.floor((x - LEFT) / STEP);
    if (row < 0 || row >= model.years.length || col < 0 || col >= 366) return null;
    const year = model.years[row];
    if (year === undefined) return null;
    const doy = col + 1;
    return model.dateAt(year, doy) !== null ? { year, doy } : null;
  };

  return (
    <div className="calendar">
      <div className="chart-scroll">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${width} ${height}`}
          className="cal-svg"
          role="img"
          tabIndex={0}
          data-testid="calendar"
          onMouseMove={(e) => {
            const hit = hitTest(e.clientX, e.clientY);
            if (hit === null) return;
            // Return the previous object when nothing changed, so a mouse
            // that stays inside one cell does not re-render the calendar.
            setCursor((prev) =>
              prev !== null && prev.year === hit.year && prev.doy === hit.doy ? prev : hit,
            );
          }}
          onClick={(e) => {
            const hit = hitTest(e.clientX, e.clientY);
            if (hit === null) return;
            const date = model.dateAt(hit.year, hit.doy);
            if (date !== null) onSelectDate(date);
          }}
          aria-label={`Burning-activity calendar, ${unit}. One row per year, one column per day. Use arrow keys to inspect days and Enter to select one.`}
          onKeyDown={(e) => {
            if (e.key === "ArrowRight") {
              e.preventDefault();
              move(1, 0);
            } else if (e.key === "ArrowLeft") {
              e.preventDefault();
              move(-1, 0);
            } else if (e.key === "ArrowDown") {
              e.preventDefault();
              move(0, 1);
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              move(0, -1);
            } else if (e.key === "Enter" && active !== null && activeDate !== null) {
              e.preventDefault();
              onSelectDate(activeDate);
            } else if (e.key === "Escape") {
              setCursor(null);
            }
          }}
        >
          {/* Month ticks */}
          {MONTH_STARTS.map((month) => (
            <text key={month.label} className="cal-month" x={LEFT + (month.doy - 1) * STEP} y={10}>
              {month.label}
            </text>
          ))}

          {model.years.map((year, yi) => {
            const y = TOP + yi * STEP;
            const days = daysInYear(year);
            return (
              <g key={year}>
                <text className="cal-year" x={LEFT - 6} y={y + CELL} textAnchor="end">
                  {year}
                </text>
                {Array.from({ length: days }, (_, i) => i + 1).map((doy) => {
                  const value = model.valueAt(year, doy);
                  const date = model.dateAt(year, doy);
                  const x = LEFT + (doy - 1) * STEP;
                  if (value === null || date === null) {
                    return (
                      <rect
                        key={doy}
                        className="cal-missing"
                        x={x}
                        y={y}
                        width={CELL}
                        height={CELL}
                      />
                    );
                  }
                  const level = rampLevel(value, model.max);
                  const isSelected = date === selectedDate;
                  const isActive = active !== null && active.year === year && active.doy === doy;
                  return (
                    <rect
                      key={doy}
                      className={`cal-cell cal-level-${level}${
                        isSelected ? " is-selected" : isActive ? " is-active" : ""
                      }`}
                      x={x}
                      y={y}
                      width={CELL}
                      height={CELL}
                      data-testid="cal-cell"
                      data-date={date}
                    />
                  );
                })}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="cal-foot">
        <p className="chart-readout" role="status" data-testid="calendar-readout">
          {readout}
        </p>
        <p className="cal-key" aria-hidden="true">
          <span>0</span>
          <i className="cal-key-swatch cal-level-1" />
          <i className="cal-key-swatch cal-level-3" />
          <i className="cal-key-swatch cal-level-5" />
          <i className="cal-key-swatch cal-level-6" />
          <span>
            {model.max} {unit}
          </span>
        </p>
      </div>
    </div>
  );
}

/** Map an ISO date to the year + day-of-year the calendar grid uses. */
function doyOf(iso: string, years: number[]): { year: number; doy: number } {
  const d = new Date(`${iso}T00:00:00Z`);
  const year = d.getUTCFullYear();
  const doy = Math.round((d.getTime() - Date.UTC(year, 0, 1)) / 86400000) + 1;
  return { year: years.includes(year) ? year : (years[years.length - 1] ?? year), doy };
}
