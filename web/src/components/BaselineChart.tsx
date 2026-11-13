import { scaleLinear } from 'd3-scale';
import { extent } from 'd3-array';
import type { BaselinePayload } from '../contract/types';

const W = 900;
const H = 220;
const M = { top: 16, right: 18, bottom: 28, left: 48 };

/**
 * The seasonal baseline: how many cell-days this area normally sees on each
 * day of the year.
 *
 * The anomaly score answers "is this day unusual for this season" by
 * comparing the day against this curve, so the curve belongs next to the
 * score: the bands are the reference the day was ranked against, and the
 * marker is where the day landed inside them.
 */
export function BaselineChart({
  baseline,
  date,
}: {
  baseline: BaselinePayload;
  date: string | null;
}) {
  const points = baseline.baseline;
  if (points.length === 0) return <p className="chart-empty">No baseline for this area.</p>;

  const innerW = W - M.left - M.right;
  const innerH = H - M.top - M.bottom;
  const x = scaleLinear().domain([1, 366]).range([M.left, M.left + innerW]);
  const values = points.flatMap((p) => [p.p05, p.p95]);
  const maxY = extent(values)[1] ?? 1;
  const y = scaleLinear().domain([0, maxY]).nice().range([M.top + innerH, M.top]);

  const band = (lo: keyof (typeof points)[number], hi: keyof (typeof points)[number]) => {
    const upper = points.map((p) => `${x(p.doy).toFixed(1)},${y(p[hi] as number).toFixed(1)}`);
    const lower = points
      .map((p) => `${x(p.doy).toFixed(1)},${y(p[lo] as number).toFixed(1)}`)
      .reverse();
    return `M${upper.join(' L')} L${lower.join(' L')} Z`;
  };

  const line = (pick: (p: (typeof points)[number]) => number) =>
    points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.doy).toFixed(1)},${y(pick(p)).toFixed(1)}`).join(' ');

  const doy = date ? dayOfYear(date) : null;
  const marked = doy === null ? undefined : points.find((p) => p.doy === doy);
  const yTicks = y.ticks(4);
  const monthTicks = [1, 4, 7, 10, 12];

  return (
    <>
      <div className="chart-wrap">
        <div className="chart-scroll">
          <svg
            className="chart"
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label={`Seasonal baseline for this area across the year, from ${points[0].doy} to ${points[points.length - 1].doy} day of year`}
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

            {monthTicks.map((m) => (
              <text
                key={m}
                x={x(doyOfMonth(m))}
                y={H - 8}
                textAnchor="middle"
                fill="var(--text-muted)"
              >
                {monthName(m)}
              </text>
            ))}

            <path d={band('p05', 'p95')} fill="var(--accent)" opacity={0.1} />
            <path d={band('p25', 'p75')} fill="var(--accent)" opacity={0.18} />
            <path
              d={line((p) => p.p50)}
              fill="none"
              stroke="var(--series-harmonized)"
              strokeWidth={2}
              strokeLinejoin="round"
            />

            {marked && (
              <g pointerEvents="none">
                <line
                  x1={x(marked.doy)}
                  x2={x(marked.doy)}
                  y1={M.top}
                  y2={M.top + innerH}
                  stroke="var(--accent)"
                  strokeWidth={1.5}
                  strokeDasharray="3 3"
                />
                <circle
                  cx={x(marked.doy)}
                  cy={y(marked.p50)}
                  r={4}
                  fill="var(--accent)"
                  stroke="var(--bg)"
                  strokeWidth={1.5}
                />
              </g>
            )}
          </svg>
        </div>
      </div>

      <div className="legend">
        <span>
          <span className="legend__swatch" style={{ background: 'var(--accent)', opacity: 0.35 }} />
          Middle 50% (p25–p75)
        </span>
        <span>
          <span className="legend__swatch" style={{ background: 'var(--accent)', opacity: 0.18 }} />
          Central 90% (p05–p95)
        </span>
        <span>
          <span className="legend__swatch" style={{ background: 'var(--series-harmonized)' }} />
          Median (p50)
        </span>
      </div>
    </>
  );
}

/** The day of year of an ISO date, 1-366. */
export function dayOfYear(iso: string): number {
  const [year, month, day] = iso.split('-').map(Number);
  const start = Date.UTC(year, 0, 1);
  const current = Date.UTC(year, month - 1, day);
  return Math.round((current - start) / 86_400_000) + 1;
}

/** The day of year the given month starts on, in a non-leap year. */
function doyOfMonth(month: number): number {
  const lengths = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return lengths.slice(0, month - 1).reduce((a, b) => a + b, 0) + 1;
}

function monthName(month: number): string {
  return ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][
    month - 1
  ];
}
