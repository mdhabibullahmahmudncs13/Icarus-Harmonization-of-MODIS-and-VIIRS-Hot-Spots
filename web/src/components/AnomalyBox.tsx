/**
 * AnomalyBox — "is this unusual for this place and this time of year".
 *
 * Renders the percentile, the value, the day-of-year window and the years
 * that contributed, all from /api/anomaly. When a date is selected on the
 * chart or the calendar, the same day-of-year row is looked up in
 * /api/baseline so the observed value can be read against the record's own
 * percentiles. Lookups only; no statistic is computed here.
 *
 * The mock endpoint returns one fixed sample date, so the payload's own date
 * is shown rather than whatever was requested, and the sample is labelled.
 */
import { useMemo, type ReactElement } from "react";
import { baselineRowFor, dayOfYear } from "../charts/calendar";
import type { AnomalyResponse, BaselineResponse } from "../contract";

export interface AnomalyBoxProps {
  anomaly: AnomalyResponse;
  baseline: BaselineResponse;
  selectedDate: string | null;
  onViewSource: () => void;
}

function fmt(value: number, digits = 1): string {
  return Number.isFinite(value) ? value.toFixed(digits) : "n/a";
}

export function AnomalyBox({
  anomaly,
  baseline,
  selectedDate,
  onViewSource,
}: AnomalyBoxProps): ReactElement {
  const row = useMemo(
    () => (selectedDate !== null ? baselineRowFor(baseline, selectedDate) : null),
    [baseline, selectedDate],
  );
  const percentile = Number.isFinite(anomaly.percentile) ? anomaly.percentile : null;

  return (
    <section className="glass-tile anomaly-tile" id="anomaly" aria-labelledby="anomaly-title">
      <div className="figure-head">
        <div>
          <h2 id="anomaly-title">Is this unusual?</h2>
          <p className="figure-sub">
            {`${anomaly.date} against the same day of year across ${anomaly.years_used} years.`}
          </p>
        </div>
        <button type="button" className="ghost-btn" onClick={onViewSource}>
          View anomaly JSON
        </button>
      </div>

      <div className="anomaly-readout">
        <p className="anomaly-value">
          <span className="stat-value stat-value--lg">{fmt(anomaly.value, 0)}</span>
          <span className="anomaly-unit">
            {anomaly.value === 1 ? "cell-day" : "cell-days"} that day
          </span>
        </p>
        <p className="anomaly-percentile">
          {percentile === null ? (
            "Percentile unavailable for this date."
          ) : (
            <>
              <span className="stat-value stat-value--lg">{fmt(percentile)}</span>
              <span className="anomaly-unit">th percentile of the baseline window</span>
            </>
          )}
        </p>
      </div>

      {/* A hairline marker, not a filled progress track. */}
      {percentile !== null && (
        <div className="anomaly-scale" aria-hidden="true">
          <span className="anomaly-scale-track" />
          <span className="anomaly-scale-tick" style={{ left: `${percentile}%` }} />
          <span className="anomaly-scale-end">0</span>
          <span className="anomaly-scale-end anomaly-scale-end--right">100</span>
        </div>
      )}

      <dl className="fact-list">
        <div className="fact-row">
          <dt>Baseline window</dt>
          <dd className="stat-value">{`+/- ${anomaly.baseline_window} days`}</dd>
        </div>
        <div className="fact-row">
          <dt>Day-of-year window</dt>
          <dd className="stat-value">{`${anomaly.doy_range[0]} to ${anomaly.doy_range[1]}`}</dd>
        </div>
        <div className="fact-row">
          <dt>Years contributing</dt>
          <dd className="stat-value">{anomaly.years_used}</dd>
        </div>
      </dl>

      {row !== null && selectedDate !== null && (
        <div className="baseline-band">
          <h3 className="sweep-title">{`Baseline for day ${dayOfYear(selectedDate)} (${selectedDate})`}</h3>
          <ul className="sweep-list">
            <li className="sweep-chip">
              <span className="sweep-km">p05</span>
              <span className="stat-value">{row.p05}</span>
            </li>
            <li className="sweep-chip">
              <span className="sweep-km">p50</span>
              <span className="stat-value">{row.p50}</span>
            </li>
            <li className="sweep-chip">
              <span className="sweep-km">p95</span>
              <span className="stat-value">{row.p95}</span>
            </li>
          </ul>
        </div>
      )}

      {row === null && (
        <p className="figure-note empty-note">
          Select a day on the timeline or the calendar to read that day-of-year against the baseline
          percentiles.
        </p>
      )}

      <p className="figure-note">
        Mock mode returns one fixed sample date, so the date above is the payload's own. Live mode
        answers for the selected date.
      </p>
    </section>
  );
}
