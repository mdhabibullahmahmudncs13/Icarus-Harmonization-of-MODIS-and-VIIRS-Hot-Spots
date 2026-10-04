/**
 * HottestCells — the side panel beside the globe.
 *
 * Exactly the cells the globe draws, ordered by the active mode's count, so
 * the picture and the numbers are the same data. Selecting a row moves the
 * globe to that cell's coordinates; the row stays highlighted while the
 * globe is looking at it. Nothing here is computed — the counts come from
 * the payload verbatim.
 */
import { useMemo, type ReactElement } from "react";
import { formatCoord, formatCount, topSpots, totalFor } from "../globe/hotspots";
import type { GlobeSpot } from "../globe/globeSpec";
import type { Mode } from "../state/urlState";

export interface HottestCellsProps {
  spots: GlobeSpot[];
  mode: Mode;
  selectedId: string | null;
  onSelect: (spot: GlobeSpot) => void;
  /** `[west, south, east, north]` of the study region. */
  regionBounds: readonly [number, number, number, number];
  cellKm: number;
  dateRange: readonly [string, string];
  onViewSource: () => void;
}

const ROWS = 7;

export function HottestCells({
  spots,
  mode,
  selectedId,
  onSelect,
  regionBounds,
  cellKm,
  dateRange,
  onViewSource,
}: HottestCellsProps): ReactElement {
  const rows = useMemo(() => topSpots(spots, ROWS, mode), [spots, mode]);
  const total = useMemo(() => totalFor(spots, mode), [spots, mode]);
  const unit = mode === "raw" ? "detections" : "cell-days";
  const [west, south, east, north] = regionBounds;

  return (
    <aside className="hot-panel" aria-labelledby="hot-title">
      <div className="hot-head">
        <h2 className="hot-title" id="hot-title">
          <svg className="hot-flame" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
            <path
              d="M12 2c2.6 4 6.5 6.2 6.5 11a6.5 6.5 0 0 1-13 0C5.5 9.3 8 7 9.4 4.4c.2 2.4 1.6 3.4 2.6 4.1-.7-2 .2-4.6 0-6.5Z"
              fill="currentColor"
            />
          </svg>
          Hottest cells
        </h2>
        <p className="hot-sub">
          {`${spots.length.toLocaleString("en-US")} cells ≥ 1 detection on a ${cellKm} km grid`}
        </p>
      </div>

      <ol className="hot-list">
        {rows.map((spot) => {
          const value = mode === "raw" ? spot.raw : spot.harmonized;
          const selected = spot.id === selectedId;
          return (
            <li key={spot.id}>
              <button
                type="button"
                className="hot-row"
                aria-pressed={selected}
                data-testid="hot-row"
                onClick={() => onSelect(spot)}
              >
                <span className="hot-cell">{spot.id}</span>
                <span className="hot-value">
                  {formatCount(value)} <span className="hot-unit">{unit}</span>
                </span>
                <span className="hot-coord">{formatCoord(spot.lat, spot.lon)}</span>
              </button>
            </li>
          );
        })}
      </ol>

      <div className="hot-foot">
        <p className="hot-total">
          {`${formatCount(total)} ${unit} across the region, ${dateRange[0]} to ${dateRange[1]}.`}
        </p>
        <p className="hot-bounds">
          {`Region ${west}°E–${east}°E, ${south}°N–${north}°N. Mock values, not evidence.`}
        </p>
        <button type="button" className="ghost-btn" onClick={onViewSource}>
          View cells JSON
        </button>
      </div>
    </aside>
  );
}
