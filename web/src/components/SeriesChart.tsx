import { scaleLinear } from 'd3-scale';
import { extent } from 'd3-array';
import type { Mode, SeriesPoint } from '../contract/types';
import { modeValue } from '../lib/series';

const W = 900;
const H = 260;
const M = { top: 16, right: 16, bottom: 28, left: 44 };

export function SeriesChart({
  rows,
  mode,
  transition,
}: {
  rows: SeriesPoint[];
  mode: Mode;
  transition: string;
}) {
  if (rows.length === 0) return <p className="chart-empty">No series data.</p>;

  const innerW = W - M.left - M.right;
  const innerH = H - M.top - M.bottom;
  const x = scaleLinear()
    .domain([0, rows.length - 1])
    .range([M.left, M.left + innerW]);
  const maxY = extent(rows.flatMap((r) => [r.raw_total, r.harm_total]))[1] ?? 1;
  const y = scaleLinear()
    .domain([0, maxY])
    .nice()
    .range([M.top + innerH, M.top]);

  const line = (pick: (r: SeriesPoint) => number) =>
    rows.map((r, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(pick(r)).toFixed(1)}`).join(' ');

  const transitionIdx = rows.findIndex((r) => r.date >= transition);
  const yTicks = y.ticks(4);
  const firstYear = Number(rows[0].date.slice(0, 4));
  const lastYear = Number(rows[rows.length - 1].date.slice(0, 4));
  const yearTicks: number[] = [];
  for (let yy = firstYear; yy <= lastYear; yy++) yearTicks.push(yy);

  return (
    <>
      <svg
        className="chart"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Daily ${
          mode === 'raw' ? 'raw detections' : 'harmonized cell-days'
        }, ${firstYear} to ${lastYear}`}
      >
        {yTicks.map((t) => (
          <g key={t}>
            <line
              x1={M.left}
              x2={M.left + innerW}
              y1={y(t)}
              y2={y(t)}
              stroke="var(--border)"
              strokeWidth={1}
            />
            <text x={M.left - 8} y={y(t) + 4} textAnchor="end" fontSize={10} fill="var(--text-muted)">
              {t}
            </text>
          </g>
        ))}

        {yearTicks.map((yy) => {
          const idx = rows.findIndex((r) => r.date.startsWith(String(yy)));
          if (idx < 0) return null;
          return (
            <text
              key={yy}
              x={x(idx)}
              y={H - 8}
              textAnchor="middle"
              fontSize={10}
              fill="var(--text-muted)"
            >
              {yy}
            </text>
          );
        })}

        <path
          d={line((r) => r.raw_total)}
          fill="none"
          stroke="var(--series-raw)"
          strokeWidth={mode === 'raw' ? 2.4 : 1.2}
          opacity={mode === 'raw' ? 1 : 0.35}
        />
        <path
          d={line((r) => r.harm_total)}
          fill="none"
          stroke="var(--series-harmonized)"
          strokeWidth={mode === 'harmonized' ? 2.4 : 1.2}
          opacity={mode === 'harmonized' ? 1 : 0.35}
        />

        {transitionIdx > 0 && (
          <>
            <line
              x1={x(transitionIdx)}
              x2={x(transitionIdx)}
              y1={M.top}
              y2={M.top + innerH}
              stroke="var(--accent)"
              strokeDasharray="4 4"
              strokeWidth={1}
            />
            <text
              x={x(transitionIdx) + 4}
              y={M.top + 12}
              fontSize={10}
              fill="var(--accent)"
            >
              VIIRS begins
            </text>
          </>
        )}
      </svg>

      <div className="legend">
        <span>
          <span className="legend__swatch" style={{ background: 'var(--series-raw)' }} />
          Raw detections / day
        </span>
        <span>
          <span className="legend__swatch" style={{ background: 'var(--series-harmonized)' }} />
          Harmonized cell-days / day
        </span>
        <span className="chip__dot" style={{ background: mode === 'raw' ? 'var(--series-raw)' : 'var(--series-harmonized)' }} />
        <span>active: {modeValue(rows[rows.length - 1], mode)} (latest day)</span>
      </div>
    </>
  );
}
