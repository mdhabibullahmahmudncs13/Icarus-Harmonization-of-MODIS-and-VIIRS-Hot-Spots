import type { Mode } from '../contract/types';
import { rampColor, type Bin } from '../lib/series';

export function CalendarHeatmap({
  bins,
  mode,
  onSelect,
}: {
  bins: Bin[];
  mode: Mode;
  onSelect?: (date: string) => void;
}) {
  if (bins.length === 0) return <p className="chart-empty">No calendar data.</p>;

  const years = [...new Set(bins.map((b) => b.year))].sort((a, b) => b - a);
  const byKey = new Map(bins.map((b) => [`${b.year}-${b.bin}`, b]));
  const pick = (b: Bin) => (mode === 'raw' ? b.raw : b.harmonized);
  const max = Math.max(...bins.map(pick), 1);

  return (
    <>
      <div className="calendar" role="grid" aria-label="Burning activity calendar">
        {years.map((year) => (
          <div key={year} style={{ display: 'contents' }}>
            <span className="calendar__year">{year}</span>
            <div className="calendar__cells" role="row">
              {Array.from({ length: 46 }, (_, i) => i + 1).map((bin) => {
                const b = byKey.get(`${year}-${bin}`);
                if (!b) {
                  return <span key={bin} className="calendar__cell" aria-hidden="true" />;
                }
                const value = pick(b);
                const t = value / max;
                const low = b.coverage < 0.75;
                return (
                  <button
                    key={bin}
                    type="button"
                    className={`calendar__cell${low ? ' calendar__cell--low' : ''}`}
                    style={{ background: low ? undefined : rampColor(t) }}
                    title={`${year} bin ${bin} · ${b.start} → ${b.end} · ${value} ${
                      mode === 'raw' ? 'detections' : 'cell-days'
                    } · coverage ${(b.coverage * 100).toFixed(0)}%`}
                    onClick={() => onSelect?.(b.start)}
                    aria-label={`${year} bin ${bin}`}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="legend">
        <span>
          {mode === 'raw' ? 'Raw detections' : 'Harmonized cell-days'} per 8-day bin (46 bins
          per year)
        </span>
        <span>
          <span className="legend__swatch" style={{ background: rampColor(0) }} /> low
          <span className="legend__swatch" style={{ background: rampColor(0.5), marginLeft: 8 }} />
          mid
          <span className="legend__swatch" style={{ background: rampColor(1), marginLeft: 8 }} />
          high
        </span>
        <span>
          <span className="legend__swatch" style={{ background: 'var(--cov-missing)' }} /> hatched =
          low coverage, never zero
        </span>
      </div>
    </>
  );
}
