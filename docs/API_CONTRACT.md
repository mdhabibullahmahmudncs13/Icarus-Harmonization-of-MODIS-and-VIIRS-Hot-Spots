# Icarus API contract

Version 1. Draft. Source of truth: the zod schemas in
[`web/src/contract/schemas.ts`](../web/src/contract/schemas.ts), exported as
JSON Schema to [`contract.schema.json`](contract.schema.json) by
`npm run contract:export` (from `web/`). Python contract tests validate API
responses against `definitions.<endpoint>` in that file; the mock files in
`web/public/mock/` are validated against the same schemas at generation time.

Every endpoint below is a `GET` and returns JSON. Every response — without
exception — starts with the same `meta` block, so no figure can ever be shown
without its provenance.

## The `meta` block (present on every response)

| Field | Type | Meaning |
|---|---|---|
| `source` | `"mock" \| "live" \| "cache" \| "fixture"` | Where this payload's data came from. The UI shows it as a source badge; `mock` also triggers the persistent "Mock data" banner. |
| `generated_at` | ISO 8601 timestamp | When the payload was produced. |
| `region.bbox` | `[west, south, east, north]` in degrees | The region the payload covers. Default region: Bangladesh box `[88, 20, 93, 27]`. |
| `cell_km` | number | Grid cell size in kilometres used for harmonization (default 5.5). |
| `min_confidence` | number | Confidence filter applied to detections, numeric, after VIIRS `l/n/h` mapping (default 50). |
| `date_range` | `[start, end]`, ISO dates | Inclusive date range this dataset covers. |

## `GET /api/meta`

Region, parameters and sensor epochs. Used by the app shell: the source
badge, the chart's sensor-epoch markers, and the methods panel.

Extra fields beyond `meta`:

- `sensors[]` — one entry per sensor epoch:
  - `product` — FIRMS sensor product name (for example "VIIRS 375 m NOAA-20").
  - `family` — `"MODIS"` or `"VIIRS"`.
  - `start` — ISO date the epoch begins.
  - `end` — ISO date the epoch ends, or `null` if ongoing.

**Caveat:** epoch dates in the mock payload are placeholders marked
`// TODO verify against FIRMS docs` in the generator. They must not be
presented as facts in the UI until verified against the FIRMS documentation.

## `GET /api/series`

Daily counts. One fetch of this endpoint feeds every chart and the calendar,
so switching between raw and harmonized never refetches.

Extra fields: `rows[]`, one per day:

| Field | Type | Meaning |
|---|---|---|
| `date` | ISO date | The day. |
| `raw_modis`, `raw_viirs`, `raw_total` | non-negative integer | Raw detections that day per sensor family and total. Raw = count of detections. |
| `harm_modis`, `harm_viirs`, `harm_total` | non-negative integer | Harmonized counts per family and total. Harmonized = distinct cell-days. |

Units shown in the UI: raw → "detections per day"; harmonized →
"cell-days per day".

## `GET /api/cells?start&end`

Grid cells for the map over a date window.

Query parameters:

- `start` — ISO date, inclusive. Optional; defaults to the dataset's first date.
- `end` — ISO date, inclusive. Optional; defaults to the dataset's last date.

Extra fields: `rows[]`, one per grid cell:

- `cell_id` — stable string identifier of the cell.
- `bounds` — `[west, south, east, north]` in degrees; the API works out grid
  geometry so the frontend never does.
- `raw` — raw detections inside the cell over the window.
- `harmonized` — distinct cell-days inside the cell over the window.
- `peak_frp` — peak fire radiative power among the cell's detections, in MW.

## `GET /api/baseline`

Seasonal baseline: percentiles of the daily series for each day of year.

Extra fields:

- `window_days` — half-width, in days, of the day-of-year window used when
  estimating each day's percentiles.
- `years_used` — how many years contributed to the estimates.
- `rows[]` — one row per day of year: `doy` (1–366), `p05`, `p25`, `p50`,
  `p75`, `p95` — non-negative counts.

## `GET /api/anomaly?date&bbox`

Answers "is this date unusual?".

Query parameters:

- `date` — ISO date to judge (required).
- `bbox` — `[west, south, east, north]` (optional; defaults to the region).

Extra fields:

- `date` — the judged date, echoed.
- `value` — the observed value for that day (same units as the active series).
- `percentile` — 0–100, where the value sits against the day-of-year baseline.
- `baseline_window` — half-width in days of the baseline window used.
- `doy_range` — `[start, end]` day-of-year window used.
- `years_used` — how many years contributed.

## `GET /api/validation`

Overlap-period validation: how well the two sensors agree before and after
harmonization.

Extra fields:

- `overlap` — `{ start, end }` ISO dates of the MODIS/VIIRS overlap examined.
- `raw` — correlation of raw MODIS vs raw VIIRS daily counts:
  `pearson`, `spearman` (both −1…1) and `ratio` (mean VIIRS / mean MODIS).
- `harmonized` — same three statistics for harmonized MODIS vs harmonized
  VIIRS. The harmonized correlation should beat the raw one.
- `cell_sweep[]` — the cell-size sensitivity check: `cell_km`, `raw_pearson`,
  `harmonized_pearson`.

## `GET /api/methods`

Content for the methods panel.

Extra fields:

- `cell_km` — grid cell size used (5.5 by default).
- `min_confidence` — confidence filter (50 by default).
- `confidence_mapping` — `{ l: 25, n: 60, h: 90 }`, the VIIRS
  low/nominal/high to numeric mapping applied before filtering.
- `collapse_rule` — plain-language description of the cell-day collapse.
- `notices[]` — standing notices, for example: Suomi-NPP data ends
  1 Nov 2026; MODIS is being retired; prefer VIIRS on NOAA-20 and NOAA-21.
- `datasets[]` — citations: `id`, `product` (FIRMS sensor product name),
  `url`.

## Exported JSON Schema

`docs/contract.schema.json` is JSON Schema draft-07 with one definition per
endpoint under `definitions`:

```python
import json
from jsonschema import validate

schema = json.load(open("docs/contract.schema.json"))
validate(instance=series_response, schema=schema["definitions"]["series"])
```

Regenerate it whenever the zod schemas change (`npm run contract:export`).
