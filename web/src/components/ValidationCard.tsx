/**
 * ValidationCard — the evidence that harmonization worked (F5).
 *
 * Shows how MODIS and VIIRS agree on the period both sensors observed. The
 * claim under test: harmonized counts track each other more closely than raw
 * counts, because the raw difference is the instrument, not the world. Every
 * number is rendered from /api/validation verbatim; nothing is recomputed
 * here.
 */
import type { ReactElement } from "react";
import type { ValidationResponse } from "../contract";

export interface ValidationCardProps {
  validation: ValidationResponse;
  onViewSource: () => void;
}

function fmt(value: number, digits = 3): string {
  return Number.isFinite(value) ? value.toFixed(digits) : "n/a";
}

export function ValidationCard({ validation, onViewSource }: ValidationCardProps): ReactElement {
  const { raw, harmonized, overlap, cell_sweep: sweep } = validation;

  return (
    <section className="glass-tile evidence-tile" id="evidence" aria-labelledby="validation-title">
      <div className="figure-head">
        <div>
          <h2 id="validation-title">Validation on the overlap</h2>
          <p className="figure-sub">
            {`MODIS and VIIRS both observed ${overlap.start} to ${overlap.end}. Harmonized counts should track each other more closely than raw counts do.`}
          </p>
        </div>
        <button type="button" className="ghost-btn" onClick={onViewSource}>
          View validation JSON
        </button>
      </div>

      <table className="stat-table">
        <caption className="visually-hidden">
          Correlation between MODIS and VIIRS daily counts on the overlap period
        </caption>
        <thead>
          <tr>
            <th scope="col">Series</th>
            <th scope="col">Pearson</th>
            <th scope="col">Spearman</th>
            <th scope="col">VIIRS : MODIS</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Raw detections</th>
            <td className="stat-value">{fmt(raw.pearson)}</td>
            <td className="stat-value">{fmt(raw.spearman)}</td>
            <td className="stat-value">{fmt(raw.ratio, 2)}x</td>
          </tr>
          <tr>
            <th scope="row">Harmonized cell-days</th>
            <td className="stat-value">{fmt(harmonized.pearson)}</td>
            <td className="stat-value">{fmt(harmonized.spearman)}</td>
            <td className="stat-value">{fmt(harmonized.ratio, 2)}x</td>
          </tr>
        </tbody>
      </table>

      <div className="sweep">
        <h3 className="sweep-title">Cell-size sweep</h3>
        <p className="figure-note">
          The harmonized correlation is recomputed across grid sizes, so the result is not an
          artifact of one cell.
        </p>
        <ul className="sweep-list">
          {sweep.map((row) => (
            <li key={row.cell_km} className="sweep-chip">
              <span className="sweep-km">{row.cell_km} km</span>
              <span className="stat-value">{fmt(row.harmonized_pearson)}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="figure-note">
        Values are read from the validation payload. Raw correlation is grid-independent; only the
        harmonized column changes across the sweep.
      </p>
    </section>
  );
}
