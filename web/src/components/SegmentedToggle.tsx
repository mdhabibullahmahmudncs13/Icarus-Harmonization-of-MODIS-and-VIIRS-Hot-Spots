/**
 * Segmented control: Raw | Harmonized (DESIGN.md §6.1).
 * Radio-group semantics (radiogroup + role=radio) so screen readers
 * announce state; arrow keys move selection, Space flips, R/H work
 * globally from App. The thumb slides between a black RAW fill and a
 * green HARMONIZED fill with a soft glow in the active color.
 */
import { useRef, type ReactElement } from "react";
import type { Mode } from "../state/urlState";

const MODES: readonly Mode[] = ["raw", "harmonized"] as const;

const LABELS: Record<Mode, string> = {
  raw: "Raw",
  harmonized: "Harmonized",
};

export interface SegmentedToggleProps {
  mode: Mode;
  onChange: (mode: Mode) => void;
}

export function SegmentedToggle({ mode, onChange }: SegmentedToggleProps): ReactElement {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const move = (from: number, delta: number): void => {
    const next = (from + delta + MODES.length) % MODES.length;
    onChange(MODES[next]);
    refs.current[next]?.focus();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, index: number): void => {
    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
        e.preventDefault();
        move(index, 1);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        e.preventDefault();
        move(index, -1);
        break;
      case " ":
        // DESIGN.md §6.1: Space flips the mode.
        e.preventDefault();
        move(index, 1);
        break;
      case "Home":
        e.preventDefault();
        onChange(MODES[0]);
        refs.current[0]?.focus();
        break;
      case "End":
        e.preventDefault();
        onChange(MODES[MODES.length - 1]);
        refs.current[MODES.length - 1]?.focus();
        break;
      default:
        break;
    }
  };

  return (
    <div className="segmented" role="radiogroup" aria-label="Count mode" data-testid="mode-toggle">
      <span className="segmented-thumb" aria-hidden="true" data-mode={mode} />
      {MODES.map((m, i) => (
        <button
          key={m}
          type="button"
          role="radio"
          aria-checked={m === mode}
          className="segment"
          data-mode={m}
          tabIndex={m === mode ? 0 : -1}
          onClick={() => onChange(m)}
          onKeyDown={(e) => onKeyDown(e, i)}
          ref={(el) => {
            refs.current[i] = el;
          }}
        >
          {LABELS[m]}
        </button>
      ))}
    </div>
  );
}
