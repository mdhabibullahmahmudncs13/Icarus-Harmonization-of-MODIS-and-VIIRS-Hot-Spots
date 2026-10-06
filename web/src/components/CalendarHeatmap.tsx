import type { Mode } from '../contract/types';
import { rampColor, type Bin } from '../lib/series';
import { Icon } from './Icon';

function findBin(bins: Bin[], date: string): Bin | undefined {
  const exact = bins.find((b) => b.start === date);
  if (exact) return exact;
  return bins.find((b) => b.start <= date && date <= b.end);
}

export function CalendarHeatmap({
  bins,
  mode,
  selected,
  onSelect,
  onClear,
  theme = 'dark',
}: {
  bins: Bin[];
  mode: Mode;
  selected?: string | null;
  onSelect?: (date: string) => void;
  onClear?: () => void;
  theme?: 'dark' | 'light';
}) {
  if (bins.length === 0) return <p className="chart-empty">No calendar data.</p>;

  const years = [...new Set(bins.map((b) => b.year))].sort((a, b) => b - a);
  const byKey = new Map(bins.map((b) => [`${b.year}-${b.bin}`, b]));
  const pick = (b: Bin) => (mode === 'raw' ? b.raw : b.harmonized);
  const max = Math.max(...bins.map(pick), 1);
  const unit = mode === 'raw' ? 'detections' : 'cell-days';
  const active = selected ? findBin(bins, selected) : undefined;

  return (
    <>
      {active ? (
        <div className="calendar-strip" role="status">
          <span className="calendar-strip__title">
            {active.year} · bin {active.bin}
          </span>
          <span className="calendar-strip__meta">
            {active.start} → {active.end} · coverage {(active.coverage * 100).toFixed(0)}% ·{' '}
            {active.source}
          </span>
          <span className="calendar-strip__value">
            {pick(active)} {unit}
          </span>
          <button type="button" className="btn btn--quiet" onClick={onClear}>
            <Icon name="close" size={14} />
            Clear
          </button>
        </div>
      ) : null}

      <div className="calendar-scroll">
        <div className="calendar" role="group" aria-label="Burning activity calendar">
          {years.map((year) => (
            <div key={year} className="calendar__row" role="group" aria-label={`${year}`}>
              <span className="calendar__year">{year}</span>
              <div className="calendar__cells">
                {Array.from({ length: 46 }, (_, i) => i + 1).map((bin) => {
                  const b = byKey.get(`${year}-${bin}`);
                  if (!b) {
                    return <span key={bin} className="calendar__cell" aria-hidden="true" />;
                  }
                  const value = pick(b);
                  const t = value / max;
                  const low = b.coverage < 0.75;
                  const modelled = b.source === 'BRIDGE' || b.source === 'VIIRS_CAL';
                  const isSelected = selected === b.start;
                  return (
                    <button
                      key={bin}
                      type="button"
                      className={`calendar__cell${low ? ' calendar__cell--low' : ''}${
                        modelled ? ' calendar__cell--modelled' : ''
                      }${isSelected ? ' is-selected' : ''}`}
                      style={{ background: low ? undefined : rampColor(t, theme) }}
                      title={`${year} bin ${bin} · ${b.start} → ${b.end} · ${value} ${unit} · coverage ${(
                        b.coverage * 100
                      ).toFixed(0)}% · ${b.source}`}
                      data-source={b.source}
                      onClick={() => (isSelected ? onClear?.() : onSelect?.(b.start))}
                      aria-pressed={isSelected}
                      aria-label={`${year} bin ${bin}, ${b.start} to ${b.end}, ${value} ${unit}, coverage ${(
                        b.coverage * 100
                      ).toFixed(0)}%, ${low ? 'low coverage' : b.source}`}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="legend">
        <span>
          {mode === 'raw' ? 'Raw detections' : 'Harmonized cell-days'} per 8-day bin (46 bins per
          year)
        </span>
        <span>
          low
          <span
            className="legend__ramp"
            aria-hidden="true"
            style={{
              background: `linear-gradient(90deg, ${rampColor(0, theme)}, ${rampColor(
                0.5,
                theme,
              )}, ${rampColor(1, theme)})`,
            }}
          />
          high
        </span>
        <span>
          <span className="legend__swatch legend__hatch" /> hatched = low coverage, never zero
        </span>
        <span>
          <span
            className="legend__swatch"
            style={{ boxShadow: 'inset 0 0 0 1px var(--accent)' }}
          />{' '}
          outlined = modelled bin
        </span>
      </div>
    </>
  );
}
