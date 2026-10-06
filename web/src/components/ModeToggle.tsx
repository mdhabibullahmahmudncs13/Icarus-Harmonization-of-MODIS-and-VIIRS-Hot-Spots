import type { Mode } from '../contract/types';

const OPTIONS: { id: Mode; label: string; short: string; key: string }[] = [
  { id: 'raw', label: 'Raw', short: 'R', key: 'R' },
  { id: 'harmonized', label: 'Harmonized', short: 'H', key: 'H' },
];

export function ModeToggle({
  mode,
  onChange,
  compact = false,
}: {
  mode: Mode;
  onChange: (mode: Mode) => void;
  compact?: boolean;
}) {
  return (
    <div className="mode" role="group" aria-label="Series mode">
      {OPTIONS.map((opt) => (
        <button
          key={opt.id}
          type="button"
          className="mode__btn"
          aria-pressed={mode === opt.id}
          aria-label={`${opt.label} (${opt.key})`}
          onClick={() => onChange(opt.id)}
          title={`${opt.label} (${opt.key})`}
        >
          {compact ? (
            <span aria-hidden="true">{opt.short}</span>
          ) : (
            opt.label
          )}
        </button>
      ))}
    </div>
  );
}
