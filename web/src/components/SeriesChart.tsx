import { useRef, useState } from 'react';
import { scaleLinear } from 'd3-scale';
import { extent } from 'd3-array';
import type { Mode, SeriesPoint } from '../contract/types';
import { modeValue } from '../lib/series';

const W = 900;
const H = 280;
const M = { top: 18, right: 18, bottom: 30, left: 48 };

export function SeriesChart({
  rows,
  mode,
  transition,
}: {
  rows: SeriesPoint[];
  mode: Mode;
  transition: string;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);

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

  const indexAt = (clientX: number): number | null => {
    const svg = svgRef.current;
    if (!svg) return null;
    const rect = svg.getBoundingClientRect();
    if (rect.width === 0) return null;
    const userX = ((clientX - rect.left) / rect.width) * W;
    const frac = (userX - M.left) / innerW;
    const idx = Math.round(frac * (rows.length - 1));
    return Math.max(0, Math.min(rows.length - 1, idx));
  };

  const tipLeft = (): number => {
    const wrap = wrapRef.current;
    const svg = svgRef.current;
    if (!wrap || !svg || hover === null) return 0;
    const wrapBox = wrap.getBoundingClientRect();
    const svgBox = svg.getBoundingClientRect();
    const raw = svgBox.left - wrapBox.left + (x(hover) / W) * svgBox.width;
    const half = 96;
    return Math.max(half, Math.min(wrapBox.width - half, raw));
  };

  const point = hover === null ? null : rows[hover];

  return (
    <>
      <div className="chart-wrap" ref={wrapRef}>
        <div className="chart-scroll">
          <svg
            ref={svgRef}
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
                <text x={M.left - 10} y={y(t) + 4} textAnchor="end" fill="var(--text-muted)">
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
              strokeLinejoin="round"
            />
            <path
              d={line((r) => r.harm_total)}
              fill="none"
              stroke="var(--series-harmonized)"
              strokeWidth={mode === 'harmonized' ? 2.4 : 1.2}
              opacity={mode === 'harmonized' ? 1 : 0.35}
              strokeLinejoin="round"
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
                <text x={x(transitionIdx) + 6} y={M.top + 13} fill="var(--accent)">
                  VIIRS begins
                </text>
              </>
            )}

            {point && (
              <g pointerEvents="none">
                <line
                  x1={x(hover!)}
                  x2={x(hover!)}
                  y1={M.top}
                  y2={M.top + innerH}
                  stroke="var(--text-muted)"
                  strokeWidth={1}
                  strokeDasharray="3 3"
                />
                <circle
                  cx={x(hover!)}
                  cy={y(modeValue(point, mode))}
                  r={4}
                  fill={mode === 'raw' ? 'var(--series-raw)' : 'var(--series-harmonized)'}
                  stroke="var(--bg)"
                  strokeWidth={1.5}
                />
              </g>
            )}

            <rect
              className="chart__hit"
              x={M.left}
              y={M.top}
              width={innerW}
              height={innerH}
              onPointerMove={(e) => setHover(indexAt(e.clientX))}
              onPointerLeave={() => setHover(null)}
            />
          </svg>
        </div>

        {point && (
          <div className="chart-tip" style={{ left: `${tipLeft()}px` }} aria-hidden="true">
            <b>{point.date}</b>
            <span className="chart-tip__row">
              <span className="legend__swatch" style={{ background: 'var(--series-raw)' }} />
              raw {point.raw_total}
            </span>
            <span className="chart-tip__row">
              <span
                className="legend__swatch"
                style={{ background: 'var(--series-harmonized)' }}
              />
              harmonized {point.harm_total}
            </span>
          </div>
        )}
      </div>

      <div className="legend">
        <span>
          <span className="legend__swatch" style={{ background: 'var(--series-raw)' }} />
          Raw detections / day
        </span>
        <span>
          <span className="legend__swatch" style={{ background: 'var(--series-harmonized)' }} />
          Harmonized cell-days / day
        </span>
        <span>
          latest day:{' '}
          <strong style={{ color: 'var(--text)' }}>
            {modeValue(rows[rows.length - 1], mode)}
          </strong>
        </span>
      </div>
    </>
  );
}
