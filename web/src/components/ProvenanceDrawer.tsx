import { useEffect, useRef } from 'react';
import type { MetaBlock } from '../contract/types';
import { Icon } from './Icon';
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
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
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
        aria-label={`Provenance — ${label}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="drawer__head">
          <span className="card__title">
            Provenance — {label}
          </span>
          <button
            ref={closeRef}
            type="button"
            className="btn btn--quiet"
            style={{ marginLeft: 'auto' }}
            onClick={onClose}
          >
            <Icon name="close" size={15} />
            Close
          </button>
        </div>
        {meta ? (
          <div className="status-card" style={{ marginBottom: 14 }}>
            <div>
              <SourceBadge source={meta.source} />
            </div>
            <div>
              generated_at <code>{meta.generated_at}</code>
            </div>
            <div>
              params_hash <code>{meta.params_hash}</code>
            </div>
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
