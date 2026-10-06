import { scaleLinear } from 'd3-scale';
import type { CellPoint, Mode } from '../contract/types';
import { rampColor } from '../lib/series';

const W = 720;
const H = 420;

export function RegionMap({
  cells,
  mode,
  bbox,
}: {
  cells: CellPoint[];
  mode: Mode;
  bbox: [number, number, number, number];
}) {
  if (cells.length === 0) return <p className="chart-empty">No cells in this window.</p>;

  const [west, south, east, north] = bbox;
  const x = scaleLinear().domain([west, east]).range([0, W]);
  const y = scaleLinear().domain([south, north]).range([H, 0]);
  const pick = (c: CellPoint) => (mode === 'raw' ? c.raw : c.harmonized);
  const max = Math.max(...cells.map(pick), 1);

  return (
    <>
      <svg
        className="map"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Grid cells shaded by ${mode} activity`}
      >
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
              fill={rampColor(pick(c) / max)}
            >
              <title>{`${c.cell_id} · ${pick(c)} ${mode === 'raw' ? 'detections' : 'cell-days'} · peak FRP ${c.peak_frp ?? 'n/a'} MW`}</title>
            </rect>
          );
        })}
      </svg>
      <div className="legend">
        <span>{cells.length} active cells · {mode === 'raw' ? 'raw detections' : 'harmonized cell-days'}</span>
        <span>
          <span className="legend__swatch" style={{ background: rampColor(0) }} /> low
          <span className="legend__swatch" style={{ background: rampColor(1), marginLeft: 8 }} />
          high
        </span>
      </div>
    </>
  );
}
