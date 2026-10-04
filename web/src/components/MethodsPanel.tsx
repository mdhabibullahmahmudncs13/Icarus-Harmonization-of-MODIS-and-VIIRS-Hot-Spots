/**
 * MethodsPanel — the method and the citations (F5).
 *
 * Cell size, confidence filter and mapping, the collapse rule, the sensor
 * retirement notices, and every dataset with its id, FIRMS product name and
 * URL. Requirement 4 of AGENTS.md: every dataset is cited. Rendered from
 * /api/methods verbatim so the panel cannot drift from the payload.
 */
import type { ReactElement } from "react";
import type { MethodsResponse } from "../contract";

export interface MethodsPanelProps {
  methods: MethodsResponse;
  onViewSource: () => void;
}

export function MethodsPanel({ methods, onViewSource }: MethodsPanelProps): ReactElement {
  const { confidence_mapping: map } = methods;

  return (
    <section className="glass-tile methods-tile" id="methods" aria-labelledby="methods-title">
      <details className="methods-details">
        <summary className="methods-summary">
          <span>
            <span className="methods-title" id="methods-title">
              Methods and datasets
            </span>
            <span className="methods-hint">
              {`${methods.cell_km} km grid, confidence >= ${methods.min_confidence}, ${methods.datasets.length} cited datasets`}
            </span>
          </span>
          <span className="methods-chevron" aria-hidden="true" />
        </summary>

        <div className="methods-body">
          <dl className="fact-list">
            <div className="fact-row">
              <dt>Grid cell</dt>
              <dd className="stat-value">{`${methods.cell_km} km`}</dd>
            </div>
            <div className="fact-row">
              <dt>Confidence filter</dt>
              <dd className="stat-value">{`>= ${methods.min_confidence}`}</dd>
            </div>
            <div className="fact-row">
              <dt>VIIRS confidence map</dt>
              <dd className="stat-value">{`low ${map.l}, nominal ${map.n}, high ${map.h}`}</dd>
            </div>
          </dl>

          <h3 className="sweep-title">Collapse rule</h3>
          <p className="methods-rule">{methods.collapse_rule}</p>

          <h3 className="sweep-title">Notices</h3>
          <ul className="notice-list">
            {methods.notices.map((notice) => (
              <li key={notice}>{notice}</li>
            ))}
          </ul>

          <h3 className="sweep-title">Datasets</h3>
          <ul className="dataset-list">
            {methods.datasets.map((dataset) => (
              <li key={dataset.id} className="dataset-row">
                <span className="dataset-id">{dataset.id}</span>
                <span className="dataset-product">{dataset.product}</span>
                <a href={dataset.url} rel="noreferrer noopener">
                  {dataset.url}
                </a>
              </li>
            ))}
          </ul>

          <button type="button" className="ghost-btn" onClick={onViewSource}>
            View methods JSON
          </button>
        </div>
      </details>
    </section>
  );
}
