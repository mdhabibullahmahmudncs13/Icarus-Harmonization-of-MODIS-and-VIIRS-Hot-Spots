import { useEffect } from 'react';
import type { MetaBlock } from '../contract/types';
import { SourceBadge } from './shared';

export function ProvenanceDrawer({
  open,
  meta,
  label,
  payload,
  onClose,
}: {
  open: boolean;
  meta: MetaBlock | null;
  label: string;
  payload: unknown;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="drawer-backdrop" onClick={onClose} role="presentation">
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Provenance"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="card__head" style={{ padding: '0 0 12px', border: 0 }}>
          <span className="card__title">Provenance — {label}</span>
          <button type="button" className="nav-item" style={{ marginLeft: 'auto' }} onClick={onClose}>
            Close (Esc)
          </button>
        </div>
        {meta ? (
          <div className="status-card" style={{ marginBottom: 12 }}>
            <div>
              <SourceBadge source={meta.source} />
            </div>
            <div>generated_at {meta.generated_at}</div>
            <div>params_hash {meta.params_hash}</div>
            <div>cell_km {meta.cell_km}</div>
            <div>
              date_range {meta.date_range[0]} → {meta.date_range[1]}
            </div>
          </div>
        ) : null}
        <pre>{JSON.stringify(payload, null, 2)}</pre>
      </aside>
    </div>
  );
}
