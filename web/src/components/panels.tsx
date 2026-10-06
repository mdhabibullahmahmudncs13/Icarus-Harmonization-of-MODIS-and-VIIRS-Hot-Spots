import type {
  AnomalyPayload,
  CriticalPeriodPayload,
  MethodsPayload,
  SourceKind,
  ValidationPayload,
} from '../contract/types';
import { Chip } from './shared';

const FLAG_COLOR: Record<AnomalyPayload['flag'], string> = {
  normal: 'var(--anom-normal)',
  elevated: 'var(--anom-elevated)',
  extreme: 'var(--anom-extreme)',
  not_scored: 'var(--text-muted)',
};

function Stat({
  label,
  value,
  small = false,
}: {
  label: string;
  value: string;
  small?: boolean;
}) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className={`stat__value${small ? ' stat__value--sm' : ''}`}>{value}</span>
    </div>
  );
}

export function AnomalyBox({ anomaly }: { anomaly: AnomalyPayload }) {
  const scored = anomaly.flag !== 'not_scored';
  return (
    <div className="card">
      <div className="card__head">
        <span className="card__title">Is this unusual?</span>
        <Chip color={FLAG_COLOR[anomaly.flag]} label={anomaly.flag.replace('_', ' ')} />
      </div>
      <div className="card__body">
        <div className="stat-grid">
          <Stat
            label={`value on ${anomaly.query.date}`}
            value={anomaly.value != null ? String(anomaly.value) : '—'}
          />
          <Stat
            label="percentile vs baseline"
            value={anomaly.percentile != null ? `${(anomaly.percentile * 100).toFixed(1)}%` : '—'}
          />
          <Stat
            label="baseline window"
            value={`±${anomaly.baseline_window} d`}
            small
          />
          <Stat label="years used" value={String(anomaly.years_used.length)} />
        </div>
        <p className="hint">
          Baseline {anomaly.doy_range[0]}–{anomaly.doy_range[1]} (day of year), area{' '}
          {anomaly.query.aoi}.
          {!scored && anomaly.reason ? ` Not scored: ${anomaly.reason.replace(/_/g, ' ')}.` : ''}
        </p>
      </div>
    </div>
  );
}

export function CriticalPeriodPanel({ critical }: { critical: CriticalPeriodPayload }) {
  if (critical.insufficient_activity) {
    return (
      <div className="card">
        <div className="card__head">
          <span className="card__title">Critical fire period</span>
        </div>
        <div className="card__body">
          <p className="empty">
            Insufficient activity for {critical.aoi} — no window can be reported for this period.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="card">
      <div className="card__head">
        <span className="card__title">Critical fire period</span>
        <span className="badge badge--outline">area {critical.aoi}</span>
      </div>
      <div className="card__body">
        <div className="stat-grid">
          <Stat label="onset bin" value={String(critical.onset_bin)} />
          <Stat label="peak bin" value={String(critical.peak_bin)} />
          <Stat label="end bin" value={String(critical.end_bin)} />
          <Stat label="window mass" value={critical.window ? `${(critical.window.mass * 100).toFixed(0)}%` : '—'} />
        </div>
        {critical.year_timing_deviation.length > 0 && (
          <p className="hint">
            Year-to-year timing deviation:{' '}
            {critical.year_timing_deviation
              .map((y) => `${y.year} ${y.days > 0 ? '+' : ''}${y.days}d`)
              .join(', ')}
          </p>
        )}
      </div>
    </div>
  );
}

export function ValidationCard({ validation }: { validation: ValidationPayload }) {
  const overlap = `${validation.overlap.years[0]}–${
    validation.overlap.years[validation.overlap.years.length - 1]
  }`;
  const line = (label: string, c: ValidationPayload['raw']) => (
    <div className="row" key={label}>
      <div>
        <div className="row__primary">{label}</div>
        <div className="row__secondary">
          Pearson {c.pearson?.toFixed(3) ?? '—'} · Spearman {c.spearman?.toFixed(3) ?? '—'}
        </div>
      </div>
      <div className="row__value">ratio {c.ratio?.toFixed(2) ?? '—'}</div>
    </div>
  );
  return (
    <div className="card">
      <div className="card__head">
        <span className="card__title">Validation — overlap {overlap}</span>
        <span className="badge badge--neutral">{validation.overlap.n_days} days</span>
      </div>
      <div className="card__body">
        {line('Raw MODIS vs raw VIIRS', validation.raw)}
        {line('Harmonized MODIS vs harmonized VIIRS', validation.harmonized)}
        <p className="hint">
          A higher harmonized correlation and a ratio closer to 1 means the sensors agree better
          after harmonization.
        </p>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">cell size</th>
              <th scope="col">raw r</th>
              <th scope="col">harmonized r</th>
            </tr>
          </thead>
          <tbody>
            {validation.cell_sweep.map((s) => (
              <tr key={s.cell_km}>
                <td>{s.cell_km} km</td>
                <td>{s.raw_correlation.toFixed(3)}</td>
                <td>{s.harmonized_correlation.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function MethodsPanel({ methods }: { methods: MethodsPayload }) {
  return (
    <div className="card">
      <div className="card__head">
        <span className="card__title">Methods</span>
      </div>
      <div className="card__body">
        <div className="stat-grid">
          <Stat label="cell size" value={`${methods.cell_km} km`} />
          <Stat label="confidence filter" value={`≥ ${methods.min_confidence}`} />
          <Stat
            label="VIIRS confidence mapping"
            value={`L ${methods.confidence_mapping.low} · N ${methods.confidence_mapping.nominal} · H ${methods.confidence_mapping.high}`}
            small
          />
        </div>
        <p className="hint">{methods.collapse_rule}</p>

        {methods.notices.map((n) => (
          <p key={n} className="hint">
            • {n}
          </p>
        ))}

        <div className="card__head" style={{ border: 0, padding: '18px 0 8px' }}>
          <span className="card__title">Datasets</span>
        </div>
        {methods.datasets.map((d) => (
          <div className="row" key={d.id}>
            <div>
              <div className="row__primary">{d.product}</div>
              <div className="row__secondary">
                {d.sensor} · {d.used_for}
              </div>
            </div>
            <a className="row__value" href={d.url} rel="noreferrer noopener" target="_blank">
              {d.id} ↗
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}

export function OfflinePanel({ source }: { source: SourceKind }) {
  return (
    <div className="card">
      <div className="card__head">
        <span className="card__title">Download for offline</span>
      </div>
      <div className="card__body">
        <p className="empty">
          Offline caching arrives in Phase 5. The app currently runs on {source} data served from
          this origin, so it works without any external request.
        </p>
      </div>
    </div>
  );
}
