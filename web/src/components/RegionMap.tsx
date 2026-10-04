/**
 * RegionMap — the study region's own grid cells, as a flat map (plan F4).
 *
 * Sizes and colours come from the `cells` payload and follow the Raw |
 * Harmonized toggle, so the same 144 cells are read either as detections or
 * as distinct cell-days, with the legend naming the unit. Nothing is
 * recomputed here: the backend did the geometry, and the colour bucket is
 * presentation.
 *
 * The map is declared `role="img"`: its rectangles duplicate what the
 * busiest-cells table beside it already lists, so making 144 squares
 * individually focusable would add 144 tab stops without adding a control.
 * The table is the keyboard path to the same selection.
 */
import { useMemo, useState, type ReactElement } from "react";
import { buildCellMap, CELL_UNIT } from "../charts/cells";
import type { CellsResponse } from "../contract";
import type { Mode } from "../state/urlState";

export interface RegionMapProps {
  cells: CellsResponse;
  mode: Mode;
  selectedId: string | null;
  onSelect: (cellId: string, lat: number, lon: number) => void;
}

export function RegionMap({ cells, mode, selectedId, onSelect }: RegionMapProps): ReactElement {
  const model = useMemo(() => buildCellMap(cells, mode), [cells, mode]);
  const [hovered, setHovered] = useState<string | null>(null);
  const unit = CELL_UNIT[mode];

  const hoveredRect =
    hovered === null ? null : (model.rects.find((rect) => rect.cell_id === hovered) ?? null);

  const readout =
    hoveredRect === null
      ? `Each square is one ${cells.meta.cell_km} km cell, shaded by ${unit} over ${cells.meta.date_range[0]} to ${cells.meta.date_range[1]}. The table beside it lists every cell.`
      : `${hoveredRect.cell_id}: ${hoveredRect.value} ${unit}. Click to look at this cell on the globe.`;

  return (
    <div className="map">
      <div className="map-stage">
        <svg
          viewBox={`0 0 ${model.width} ${model.height}`}
          className="map-svg"
          role="img"
          data-testid="region-map"
          aria-label={`Map of the study region: ${model.rects.length} grid cells of ${cells.meta.cell_km} km, shaded by ${unit}. The table beside it lists the same cells.`}
          onMouseLeave={() => setHovered(null)}
        >
          <rect className="map-ground" x={0} y={0} width={model.width} height={model.height} />
          {model.rects.map((rect) => (
            <rect
              key={rect.cell_id}
              className={`map-cell map-level-${rect.level}${rect.cell_id === selectedId ? " is-selected" : ""}`}
              x={rect.x}
              y={rect.y}
              width={rect.width}
              height={rect.height}
              data-testid="map-cell"
              data-cell-id={rect.cell_id}
              onMouseEnter={() => setHovered(rect.cell_id)}
              onClick={() => onSelect(rect.cell_id, rect.lat, rect.lon)}
            />
          ))}
        </svg>
      </div>

      <div className="cal-foot">
        <p className="chart-readout" role="status" data-testid="map-readout">
          {readout}
        </p>
        <p className="cal-key" aria-hidden="true">
          <span>0</span>
          <i className="cal-key-swatch map-level-1" />
          <i className="cal-key-swatch map-level-3" />
          <i className="cal-key-swatch map-level-5" />
          <i className="cal-key-swatch map-level-6" />
          <span>
            {model.max} {unit}
          </span>
        </p>
      </div>
    </div>
  );
}
