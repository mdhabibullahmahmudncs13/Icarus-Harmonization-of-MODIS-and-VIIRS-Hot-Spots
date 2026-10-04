/**
 * Provenance drawer: every figure opens the JSON behind it (plan,
 * principle 6). Non-modal side drawer; Escape closes it and focus returns
 * to the trigger via the close button.
 */
import { useEffect, useRef, type ReactElement } from "react";

export interface ProvenanceDrawerProps {
  open: boolean;
  /** Human title of the figure, e.g. "Daily counts". */
  title: string;
  /** The raw JSON payload behind the figure. */
  payload: unknown;
  onClose: () => void;
}

export function ProvenanceDrawer({
  open,
  title,
  payload,
  onClose,
}: ProvenanceDrawerProps): ReactElement | null {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="drawer"
      role="dialog"
      aria-modal="false"
      aria-label={`Source JSON for ${title}`}
      data-testid="provenance-drawer"
    >
      <div className="drawer-header">
        <h2>Source JSON — {title}</h2>
        <button type="button" className="drawer-close" onClick={onClose} ref={closeRef}>
          Close
        </button>
      </div>
      <p className="drawer-note">
        Exactly the payload this figure was rendered from, as delivered by the data source.
      </p>
      <pre className="drawer-json" tabIndex={0}>
        <code>{JSON.stringify(payload, null, 2)}</code>
      </pre>
    </div>
  );
}
