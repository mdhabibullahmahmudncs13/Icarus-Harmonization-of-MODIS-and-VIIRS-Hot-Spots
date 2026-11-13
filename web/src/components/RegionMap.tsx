import type { CellPoint, Mode } from '../contract/types';
import { cellExtent, rampColor } from '../lib/series';

const W = 720;
const H = 420;
const RAMP_FLOOR = 0.14;
const MARGIN = { top: 12, right: 14, bottom: 34, left: 74 };

function cellFill(value: number, max: number, theme: 'dark' | 'light'): string {
  if (value <= 0) return 'var(--cov-missing)';
  const t = Math.max(0, Math.min(1, value / max));
  return rampColor(RAMP_FLOOR + (1 - RAMP_FLOOR) * t, theme);
}

function niceStep(span: number): number {
  const raw = span / 6;
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const n = raw / pow;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * pow;
}

function ticks(lo: number, hi: number, step: number): number[] {
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) {
    out.push(Math.round(v * 100) / 100);
  }
  return out;
}

const lonLabel = (v: number) => `${Math.abs(v).toFixed(0)}°${v < 0 ? 'W' : 'E'}`;
const latLabel = (v: number) => `${Math.abs(v).toFixed(0)}°${v < 0 ? 'S' : 'N'}`;

export function RegionMap({
  cells,
  mode,
  theme = 'dark',
}: {
  cells: CellPoint[];
  mode: Mode;
  theme?: 'dark' | 'light';
}) {
  if (cells.length === 0) return <p className="chart-empty">No cells in this window.</p>;

  // One pass over the cells for all four bounds and the maximum, rather than
  // five separate ones. `Math.max(...cells.map(...))` also blows the call
  // stack on a large area — the pilot extent is ~380,000 cells, well past
  // the argument limit a spread can take.
  const pick = (c: CellPoint) => (mode === 'raw' ? c.raw : c.harmonized);
  const { bounds, max, active } = cellExtent(cells, mode);
  const [west, south, east, north] = bounds;

  const padX = (east - west) * 0.03 || 0.05;
  const padY = (north - south) * 0.05 || 0.05;
  const lon0 = west - padX;
  const lon1 = east + padX;
  const lat0 = south - padY;
  const lat1 = north + padY;

  const plotW = W - MARGIN.left - MARGIN.right;
  const plotH = H - MARGIN.top - MARGIN.bottom;
  const scale = Math.min(plotW / (lon1 - lon0), plotH / (lat1 - lat0));
  const offX = MARGIN.left + (plotW - (lon1 - lon0) * scale) / 2;
  const offY = MARGIN.top + (plotH - (lat1 - lat0) * scale) / 2;
  const x = (lon: number) => offX + (lon - lon0) * scale;
  const y = (lat: number) => offY + (lat1 - lat) * scale;

  const xTicks = ticks(lon0, lon1, niceStep(lon1 - lon0));
  const yTicks = ticks(lat0, lat1, niceStep(lat1 - lat0));

  return (
    <>
      <svg
        className="map"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${cells.length} grid cells, ${active} with ${
          mode === 'raw' ? 'raw detections' : 'harmonized cell-days'
        } in this window, ${lonLabel(lon0)} to ${lonLabel(lon1)} and ${latLabel(
          lat0,
        )} to ${latLabel(lat1)}`}
      >
        <g aria-hidden="true">
          {xTicks.map((t) => (
            <g key={`x${t}`}>
              <line className="map__grid" x1={x(t)} y1={MARGIN.top} x2={x(t)} y2={H - MARGIN.bottom} />
              <text className="map__tick" x={x(t)} y={H - MARGIN.bottom + 16} textAnchor="middle">
                {lonLabel(t)}
              </text>
            </g>
          ))}
          {yTicks.map((t) => (
            <g key={`y${t}`}>
              <line className="map__grid" x1={MARGIN.left} y1={y(t)} x2={W - MARGIN.right} y2={y(t)} />
              <text
                className="map__tick"
                x={MARGIN.left - 8}
                y={y(t) + 3.5}
                textAnchor="end"
              >
                {latLabel(t)}
              </text>
            </g>
          ))}
        </g>
        {cells.map((c) => {
          const [w, s, e, n] = c.bounds;
          const rectX = x(w);
          const rectY = y(n);
          const width = Math.max(x(e) - rectX, 0.5);
          const height = Math.max(y(s) - rectY, 0.5);
          return (
            <rect
              key={c.cell_id}
              className="map__cell"
              x={rectX}
              y={rectY}
              width={width}
              height={height}
              fill={cellFill(pick(c), max, theme)}
            >
              <title>{`${c.cell_id} · ${pick(c)} ${
                mode === 'raw' ? 'detections' : 'cell-days'
              } · peak FRP ${c.peak_frp ?? 'n/a'} MW`}</title>
            </rect>
          );
        })}
      </svg>
      <div className="legend">
        <span>
          {cells.length} cells · {active} with activity
        </span>
        <span>
          <span className="legend__swatch" style={{ background: 'var(--cov-missing)' }} />
          none
          <span
            className="legend__ramp"
            aria-hidden="true"
            style={{
              background: `linear-gradient(90deg, ${rampColor(RAMP_FLOOR, theme)}, ${rampColor(
                RAMP_FLOOR + (1 - RAMP_FLOOR) * 0.5,
                theme,
              )}, ${rampColor(1, theme)})`,
            }}
          />
          low → high
        </span>
      </div>
    </>
  );
}
