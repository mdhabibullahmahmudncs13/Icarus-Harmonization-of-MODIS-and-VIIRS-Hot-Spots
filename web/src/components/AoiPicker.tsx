import type { AoiPayload } from '../contract/types';
import { CUSTOM_AOI } from '../lib/polygon';

/**
 * The preset-region picker (docs/FLOWS.md §Journey 1, "select preset region
 * (Rail > region)").
 *
 * The presets come from the dataset the app already loaded — the ``aoi``
 * payload is one of the nine the contract defines — so the picker never has a
 * second list to keep in step with the API's.
 *
 * "Custom area" is not a region: it is the drawn shape (FR-16). It is
 * offered here so the user can see that the area they drew is the one in
 * force, and so picking a preset again goes back to a preset.
 */
export function AoiPicker({
  aoi,
  presets,
  onChange,
  onCustom,
  disabled = false,
}: {
  aoi: string;
  presets: AoiPayload['presets'];
  onChange: (aoi: string) => void;
  /** Called when the user picks the custom area. */
  onCustom?: () => void;
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
        onChange={(e) => {
          if (e.target.value === CUSTOM_AOI) {
            onCustom?.();
            return;
          }
          onChange(e.target.value);
        }}
        aria-label="Region"
      >
        {presets.map((preset) => (
          <option key={preset.id} value={preset.id}>
            {preset.name}
          </option>
        ))}
        <option value={CUSTOM_AOI}>Custom area…</option>
      </select>
    </label>
  );
}
