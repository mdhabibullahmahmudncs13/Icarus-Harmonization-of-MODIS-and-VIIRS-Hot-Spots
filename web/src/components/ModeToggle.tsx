import type { Mode } from '../contract/types';

const OPTIONS: { id: Mode; label: string; key: string }[] = [
  { id: 'raw', label: 'Raw', key: 'R' },
  { id: 'harmonized', label: 'Harmonized', key: 'H' },
];

export function ModeToggle({
  mode,
  onChange,
}: {
  mode: Mode;
  onChange: (mode: Mode) => void;
}) {
  return (
    <div className="mode" role="group" aria-label="Series mode">
      {OPTIONS.map((opt) => (
        <button
          key={opt.id}
          type="button"
          className="mode__btn"
          aria-pressed={mode === opt.id}
          onClick={() => onChange(opt.id)}
          title={`${opt.label} (${opt.key})`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
