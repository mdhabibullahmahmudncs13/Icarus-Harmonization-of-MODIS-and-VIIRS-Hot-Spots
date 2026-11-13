import { useRef } from 'react';
import type { CellPoint, Mode } from '../contract/types';
import { cellExtent, rampColor } from '../lib/series';
import { closeRing, type Ring } from '../lib/polygon';

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

/**
 * The map's projection: pixel coordinates for a longitude and latitude.
 *
 * The drawing code needs the same mapping the cells are drawn with, so it
 * lives in one place and both use it.
 */
export interface Projection {
  x: (lon: number) => number;
  y: (lat: number) => number;
  lon: (px: number) => number;
  lat: (py: number) => number;
  lon0: number;
  lon1: number;
  lat0: number;
  lat1: number;
}

/**
 * The projection for a set of bounds.
 *
 * The extent is padded a little so the outermost cells are not flush with
 * the frame, and the aspect ratio is kept square: a degree of longitude is
 * shorter than a degree of latitude, so the scale is the same on both axes
 * and the shape is not stretched.
 */
export function projectionFor(bounds: [number, number, number, number]): Projection {
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
  return {
    x,
    y,
    lon: (px: number) => lon0 + (px - offX) / scale,
    lat: (py: number) => lat1 - (py - offY) / scale,
    lon0,
    lon1,
    lat0,
    lat1,
  };
}

export function RegionMap({
  cells,
  mode,
  theme = 'dark',
  polygon = null,
  onAddVertex = null,
  drawing = false,
}: {
  cells: CellPoint[];
  mode: Mode;
  theme?: 'dark' | 'light';
  /** The drawn area, drawn over the cells. */
  polygon?: Ring | null;
  /** Called with the longitude and latitude of a click, when drawing. */
  onAddVertex?: ((lon: number, lat: number) => void) | null;
  /** Is the map in drawing mode? */
  drawing?: boolean;
}) {
  // The SVG's own box, so a click can be turned back into a longitude and
  // latitude. `getBoundingClientRect` is the only honest way: the SVG is
  // scaled to the column width, so the viewBox units are not the pixels.
  const svgRef = useRef<SVGSVGElement>(null);

  if (cells.length === 0) return <p className="chart-empty">No cells in this window.</p>;

  // One pass over the cells for all four bounds and the maximum, rather than
  // five separate ones. `Math.max(...cells.map(...))` also blows the call
  // stack on a large area — the pilot extent is ~380,000 cells, well past
  // the argument limit a spread can take.
  const pick = (c: CellPoint) => (mode === 'raw' ? c.raw : c.harmonized);
  const { bounds, max, active } = cellExtent(cells, mode);

  const p = projectionFor(bounds);
  const { x, y } = p;
  const { lon0, lon1, lat0, lat1 } = p;

  const xTicks = ticks(lon0, lon1, niceStep(lon1 - lon0));
  const yTicks = ticks(lat0, lat1, niceStep(lat1 - lat0));

  const onClick = (event: React.MouseEvent<SVGSVGElement>) => {
    if (!onAddVertex || !drawing) return;
    const box = svgRef.current?.getBoundingClientRect();
    if (!box || box.width === 0) return;
    const px = ((event.clientX - box.left) / box.width) * W;
    const py = ((event.clientY - box.top) / box.height) * H;
    onAddVertex(p.lon(px), p.lat(py));
  };

  const ring = polygon && polygon.length > 0 ? closeRing(polygon) : null;
  const path = ring ? ring.map(([lon, lat]) => `${x(lon)},${y(lat)}`).join(' ') : '';

  return (
    <>
      <svg
        ref={svgRef}
        className={`map${drawing ? ' map--drawing' : ''}`}
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${cells.length} grid cells, ${active} with ${
          mode === 'raw' ? 'raw detections' : 'harmonized cell-days'
        } in this window, ${lonLabel(lon0)} to ${lonLabel(lon1)} and ${latLabel(
          lat0,
        )} to ${latLabel(lat1)}`}
        onClick={onClick}
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
        {ring ? (
          <g className="map__area">
            <polygon className="map__area-fill" points={path} />
            <polyline className="map__area-line" points={path} />
            {ring.map(([lon, lat], i) => (
              <circle key={i} className="map__area-point" cx={x(lon)} cy={y(lat)} r={4} />
            ))}
          </g>
        ) : null}
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
