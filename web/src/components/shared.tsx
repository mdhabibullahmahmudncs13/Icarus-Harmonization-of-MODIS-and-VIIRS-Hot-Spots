import type { MetaBlock, SourceKind } from '../contract/types';

const SOURCE_CLASS: Record<SourceKind, string> = {
  mock: 'badge badge--missing',
  fixture: 'badge badge--missing',
  cache: 'badge badge--outline',
  live: 'badge badge--accent',
};

export function SourceBadge({ source }: { source: SourceKind }) {
  const isEvidence = source === 'live' || source === 'cache';
  return (
    <span className={SOURCE_CLASS[source]} title={isEvidence ? 'Observed data' : 'Not evidence'}>
      {source}
    </span>
  );
}

export function MockBanner({ source }: { source: SourceKind }) {
  if (source !== 'mock' && source !== 'fixture') return null;
  return (
    <div className="mock-banner" role="status" aria-live="polite">
      <strong>Mock data.</strong>
      <span>
        Generated for the interface only. Not an observation and never used as evidence.
      </span>
    </div>
  );
}

export function KeyboardHint() {
  return (
    <p className="hint">
      Press <kbd>R</kbd>/<kbd>H</kbd> to switch modes, <kbd>T</kbd> for theme,{' '}
      <kbd>?</kbd> for all shortcuts.
    </p>
  );
}

export function Chip({ color, label }: { color: string; label: string }) {
  return (
    <span className="chip">
      <span className="chip__dot" style={{ background: color }} aria-hidden="true" />
      {label}
    </span>
  );
}

export function StatusCard({ meta, notice }: { meta: MetaBlock; notice?: string }) {
  return (
    <div className="status-card">
      <div>
        <SourceBadge source={meta.source} />
      </div>
      <div>cell {meta.cell_km} km</div>
      <div>hash {meta.params_hash}</div>
      <div>
        {meta.date_range[0]} → {meta.date_range[1]}
      </div>
      {notice ? <div>{notice}</div> : null}
    </div>
  );
}
