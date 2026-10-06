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

export function AnomalyBox({ anomaly }: { anomaly: AnomalyPayload }) {
  const scored = anomaly.flag !== 'not_scored';
  return (
    <div className="card">
      <div className="card__head">
        <span className="card__title">Is this unusual?</span>
        <Chip color={FLAG_COLOR[anomaly.flag]} label={anomaly.flag.replace('_', ' ')} />
      </div>
      <div className="card__body">
        <div className="row" style={{ padding: 0, borderBottom: 0 }}>
          <div>
            <div className="row__primary">{anomaly.query.date}</div>
            <div className="row__secondary">area {anomaly.query.aoi}</div>
          </div>
          <div className="row__value">{anomaly.value ?? '—'}</div>
        </div>
        <div className="row" style={{ padding: 0, borderBottom: 0 }}>
          <div className="row__secondary">percentile</div>
          <div className="row__value">
            {anomaly.percentile != null ? `${(anomaly.percentile * 100).toFixed(1)}%` : '—'}
          </div>
        </div>
        <div className="row" style={{ padding: 0, borderBottom: 0 }}>
          <div className="row__secondary">baseline window</div>
          <div className="row__value">±{anomaly.baseline_window} days ({anomaly.doy_range[0]}–{anomaly.doy_range[1]})</div>
        </div>
        <div className="row" style={{ padding: 0, borderBottom: 0 }}>
          <div className="row__secondary">years used</div>
          <div className="row__value">{anomaly.years_used.length}</div>
        </div>
        {!scored && anomaly.reason ? (
          <p className="hint">Not scored: {anomaly.reason.replace(/_/g, ' ')}.</p>
        ) : null}
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
          <p className="empty">Insufficient activity for {critical.aoi}: no window returned.</p>
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
        <div className="row" style={{ padding: 0 }}>
          <div className="row__secondary">onset bin</div>
          <div className="row__value">{critical.onset_bin}</div>
        </div>
        <div className="row" style={{ padding: 0 }}>
          <div className="row__secondary">peak bin</div>
          <div className="row__value">{critical.peak_bin}</div>
        </div>
        <div className="row" style={{ padding: 0 }}>
          <div className="row__secondary">end bin</div>
          <div className="row__value">{critical.end_bin}</div>
        </div>
        <div className="row" style={{ padding: 0 }}>
          <div className="row__secondary">window mass</div>
          <div className="row__value">
            {critical.window ? `${(critical.window.mass * 100).toFixed(0)}%` : '—'}
          </div>
        </div>
        {critical.year_timing_deviation.length > 0 && (
          <p className="hint">
            Year-to-year timing deviation: {critical.year_timing_deviation.map((y) => `${y.year} ${y.days > 0 ? '+' : ''}${y.days}d`).join(', ')}
          </p>
        )}
      </div>
    </div>
  );
}

export function ValidationCard({ validation }: { validation: ValidationPayload }) {
  const row = (label: string, c: ValidationPayload['raw']) => (
    <div className="row" style={{ padding: '8px 0' }}>
      <div className="row__primary">{label}</div>
      <div className="row__secondary">
        Pearson {c.pearson?.toFixed(3) ?? '—'} · Spearman {c.spearman?.toFixed(3) ?? '—'}
      </div>
      <div className="row__value">ratio {c.ratio?.toFixed(2) ?? '—'}</div>
    </div>
  );
  return (
    <div className="card">
      <div className="card__head">
        <span className="card__title">Validation — overlap {validation.overlap.years[0]}–{validation.overlap.years[validation.overlap.years.length - 1]}</span>
        <span className="badge badge--neutral">{validation.overlap.n_days} days</span>
      </div>
      <div className="card__body">
        {row('Raw MODIS vs raw VIIRS', validation.raw)}
        {row('Harmonized MODIS vs harmonized VIIRS', validation.harmonized)}
        <p className="hint">
          A higher harmonized correlation and a ratio closer to 1 means the sensors agree
          better after harmonization.
        </p>
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 8, fontSize: 12 }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', color: 'var(--text-muted)', fontWeight: 500 }}>cell size</th>
              <th style={{ textAlign: 'right', color: 'var(--text-muted)', fontWeight: 500 }}>raw r</th>
              <th style={{ textAlign: 'right', color: 'var(--text-muted)', fontWeight: 500 }}>harmonized r</th>
            </tr>
          </thead>
          <tbody>
            {validation.cell_sweep.map((s) => (
              <tr key={s.cell_km}>
                <td>{s.cell_km} km</td>
                <td style={{ textAlign: 'right' }}>{s.raw_correlation.toFixed(3)}</td>
                <td style={{ textAlign: 'right' }}>{s.harmonized_correlation.toFixed(3)}</td>
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
        <div className="row" style={{ padding: 0 }}>
          <div className="row__secondary">cell size</div>
          <div className="row__value">{methods.cell_km} km</div>
        </div>
        <div className="row" style={{ padding: 0 }}>
          <div className="row__secondary">confidence filter</div>
          <div className="row__value">≥ {methods.min_confidence}</div>
        </div>
        <div className="row" style={{ padding: 0 }}>
          <div className="row__secondary">VIIRS mapping</div>
          <div className="row__value">
            l {methods.confidence_mapping.low} · n {methods.confidence_mapping.nominal} · h{' '}
            {methods.confidence_mapping.high}
          </div>
        </div>
        <p className="hint">{methods.collapse_rule}</p>

        {methods.notices.map((n) => (
          <p key={n} className="hint">
            • {n}
          </p>
        ))}

        <div className="card__head" style={{ border: 0, padding: '16px 0 8px' }}>
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
              {d.id}
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
          Offline caching arrives in Phase 5. The app currently runs on {source} data served
          from this origin, so it works without any external request.
        </p>
      </div>
    </div>
  );
}
