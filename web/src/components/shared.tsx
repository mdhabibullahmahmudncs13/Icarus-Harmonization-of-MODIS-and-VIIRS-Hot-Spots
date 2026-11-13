import { Component, useEffect, useRef, type ErrorInfo, type ReactNode } from 'react';
import type { MetaBlock, SourceKind } from '../contract/types';
import { bannerFor, sourceNotice } from '../lib/source';
import { Icon } from './Icon';

const SOURCE_CLASS: Record<SourceKind, string> = {
  mock: 'badge badge--missing',
  fixture: 'badge badge--missing',
  cache: 'badge badge--outline',
  live: 'badge badge--accent',
};

export function SourceBadge({ source }: { source: SourceKind }) {
  const isEvidence = sourceNotice(source).isEvidence;
  return (
    <span className={SOURCE_CLASS[source]} title={isEvidence ? 'Observed data' : 'Not evidence'}>
      {source}
    </span>
  );
}

/**
 * The non-evidence banner. It names the source it is actually showing, so the
 * fixture tier is never labelled "mock" (`docs/IMPLEMENTATION_PLAN.md` §3.3).
 * Evidence sources need no banner and render nothing.
 */
export function MockBanner({ source }: { source: SourceKind }) {
  const notice = bannerFor(source);
  if (notice === null) return null;
  return (
    <div className="mock-banner" role="status" aria-live="polite">
      <strong>{notice.title}</strong>
      <span>{notice.body}</span>
    </div>
  );
}

export function KeyboardHint() {
  return (
    <p className="hint">
      Press <kbd>R</kbd>/<kbd>H</kbd> to switch modes, <kbd>1</kbd>–<kbd>8</kbd> for views,{' '}
      <kbd>?</kbd> for all shortcuts.
    </p>
  );
}

export function Chip({ color, label }: { color: string; label: string }) {
  return (
    <span className="chip">
      <span className="chip__dot" style={{ background: color, color }} aria-hidden="true" />
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
      <div>
        hash <code>{meta.params_hash}</code>
      </div>
      <div>
        {meta.date_range[0]} → {meta.date_range[1]}
      </div>
      {notice ? <div>{notice}</div> : null}
    </div>
  );
}

export function LoadingSkeleton() {
  return (
    <div className="card" aria-busy="true" aria-live="polite">
      <div className="card__body skeleton">
        <span className="skel skel--title" />
        <span className="skel skel--line" />
        <span className="skel skel--chart" />
        <span className="skel skel--line" />
        <span className="sr-only">Loading data…</span>
      </div>
    </div>
  );
}

/**
 * Catches a render that throws, so a bad payload shows a message instead of
 * a blank page.
 *
 * A fetch that fails is reported through the error state, but a throw during
 * render — a payload the app could not read — has nowhere else to go: React
 * unmounts the tree and the user sees nothing at all.
 */
export class RenderBoundary extends Component<
  { children: ReactNode },
  { message: string | null }
> {
  override state: { message: string | null } = { message: null };

  static getDerivedStateFromError(error: unknown): { message: string } {
    return { message: error instanceof Error ? error.message : String(error) };
  }

  override componentDidCatch(error: unknown, info: ErrorInfo): void {
    console.error('render failed', error, info.componentStack);
  }

  override render(): ReactNode {
    if (this.state.message === null) return this.props.children;
    return (
      <div className="card">
        <div className="card__body error">
          <strong>Could not draw this view</strong>
          <span>{this.state.message}</span>
        </div>
      </div>
    );
  }
}

const SHORTCUTS: { keys: string[]; label: string }[] = [
  { keys: ['1', '…', '8'], label: 'Jump to a view (Overview → Offline)' },
  { keys: ['R'], label: 'Raw detections mode' },
  { keys: ['H'], label: 'Harmonized cell-days mode' },
  { keys: ['T'], label: 'Toggle dark / light theme' },
  { keys: ['P'], label: 'Open provenance for this view' },
  { keys: ['?'], label: 'Open this shortcut list' },
  { keys: ['Ctrl', 'B'], label: 'Collapse or expand the rail' },
  { keys: ['Esc'], label: 'Close the drawer or this dialog' },
];

export function HelpDialog({ onClose }: { onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal__head">
          <h2 className="modal__title" id="help-title">
            Keyboard shortcuts
          </h2>
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
        <div className="kbd-list">
          {SHORTCUTS.map((row) => (
            <div className="kbd-row" key={row.label}>
              <span>{row.label}</span>
              <span className="kbd-row__keys">
                {row.keys.map((k) => (
                  <kbd key={k}>{k}</kbd>
                ))}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
