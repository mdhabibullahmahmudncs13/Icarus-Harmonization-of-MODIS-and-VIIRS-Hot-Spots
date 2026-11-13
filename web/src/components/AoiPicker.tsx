import type { AoiPayload } from '../contract/types';

/**
 * The preset-region picker (docs/FLOWS.md §Journey 1, "select preset region
 * (Rail > region)").
 *
 * The presets come from the dataset the app already loaded — the ``aoi``
 * payload is one of the nine the contract defines — so the picker never has a
 * second list to keep in step with the API's.
 */
export function AoiPicker({
  aoi,
  presets,
  onChange,
  disabled = false,
}: {
  aoi: string;
  presets: AoiPayload['presets'];
  onChange: (aoi: string) => void;
  disabled?: boolean;
}) {
  if (presets.length === 0) return null;
  return (
    <label className="aoi-picker">
      <span className="aoi-picker__label">Region</span>
      <select
        className="aoi-picker__select"
        value={aoi}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Region"
      >
        {presets.map((preset) => (
          <option key={preset.id} value={preset.id}>
            {preset.name}
          </option>
        ))}
      </select>
    </label>
  );
}
