# Changelog

All notable changes to Project Icarus are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> This project is pre-implementation: the entries below cover the specification
> and documentation baseline. No software has been released yet.

---

## [Unreleased]

### Added

- Documentation baseline for the build-specification design:
  - `docs/PRD.md` — product requirements.
  - `docs/TRD.md` — technical requirements.
  - `docs/SYSTEM_ARCHITECTURE.md` — system architecture baseline.
  - `docs/ARCHITECTURE.md` — builder's architecture (module map, sequence, ADRs).
  - `docs/PARAMETERS.md` — full parameter registry.
  - `docs/DATA_DICTIONARY.md` — datasets, schemas, derived tables.
  - `docs/TESTING.md` — verification and validation strategy.
  - `docs/DEPLOYMENT.md` — deployment and offline runbook.
  - `docs/ROADMAP.md` — work breakdown and milestones.
  - `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`.
- Committed golden fixtures for the Phase 2 compute core (`tests/golden/*.json`),
  written by `tools/gen_golden.py` and guarded by `tests/test_golden.py`. A
  number that moves in the pipeline now fails the suite until the goldens are
  deliberately regenerated with `make golden`.

### Added

- `web/src/lib/source.ts` — one notice per data source, so a synthetic tier can
  never be labelled with another tier's name, plus the release guard that stops
  a release build from shipping on non-evidence data (`npm run build:release`
  fails unless `VITE_DATA=api`).
- `src/compute/availability.py` and `src/outages.json` — the S7 stream
  availability calendar: each stream's product epoch minus the explicit outage
  table.
- `src/compute/coverage.py` — the S7 coverage stage: per-bin coverage and
  `MODIS`/`BRIDGE`/`VIIRS_CAL`/`NONE` source tagging, all four classes reachable.
  `docs/contract.schema.json` gains `$defs/binSource` and `coverage`/`source` on
  `seriesPoint`; the mock generator, the `coverage_bins.json` golden, the
  frontend types and `aggregateToBins` all carry them, so the calendar hatches
  an under-observed bin instead of reading it as zero activity.
- `src/compute/calibrate.py` — the S8 multiplicative calibration, applied to
  `VIIRS_CAL` bins so that tag means calibration was applied.
- The demo fixture now contains the outage windows from `src/outages.json`
  (MODIS blanked 10-25 June 2019, every sensor 1-5 August 2019), so the offline
  calendar shows `BRIDGE`, `VIIRS_CAL` and the hatched `NONE` state.
- `metric=density` on `POST /api/v1/series` — the same counts divided by the
  number of grid cells covering `meta.region.bbox`
  (`harmonize.grid_cell_count`), so `harm_*` is the fraction of the region's
  cells active that day (0–1) and `raw_*` is detections per cell. The contract
  gains `$defs/densityPoint` and discriminates on `series.metric`; the
  endpoints whose payloads have no `metric` field still refuse `density` with
  422 `unsupported_metric` rather than silently answering in `cell_days`.
- The offline service worker (`web/public/sw.js`, registered in production
  builds by `web/src/lib/sw.ts`): versioned `icarus-*` caches, a precached
  shell, cache-first hashed assets and stale-while-revalidate data.
  `web/e2e/offline-cold-start.spec.ts` proves the §7 gate — with the browser
  offline the app still renders and the mode toggle still flips. Cached
  responses are stored without the server's `Vary: Origin` /
  `content-encoding` transport headers, which otherwise made an offline
  reload fail with `net::ERR_FAILED`, and the page reports its used
  resources to the worker because they are fetched before it activates.
- Phase 4 — the app now runs on real FIRMS data. The three archive products
  (`MODIS_SP`, `VIIRS_SNPP_SP`, `VIIRS_NOAA20_SP`) plus NOAA-21 as
  `VIIRS_NOAA21_NRT` (the Area API serves no `VIIRS_NOAA21_SP`, only NRT for
  that satellite — the product table names the source that actually exists)
  are downloaded through
  `src/acquire` into `cache/raw/*.parquet` — the SP archive alone is
  1,378,592 detections, 2003-01-02 → 2026-06-28 — and the frontend points at the API with
  `VITE_DATA=api`; the badge reads `cache` with `params_hash f4b82ef0c728`.
  The finding holds on real data: pre (2010–11) vs post (2013–14) the raw
  total jumps **5.42×** (34.0 → 184.1 detections/day) while the MODIS-only
  activity control is 0.92×, and harmonization cuts the jump to **3.77×**
  (18.2 → 68.5 cell-days/day). Overlap validation over 15 years / 4,665 days:
  Pearson 0.779 → 0.823, ratio 6.54 → 4.02 (Spearman 0.822 → 0.812).
  Harmonization reduces but does not eliminate the real-data step — the
  residual is VIIRS's temporal density inside already-covered cells, not
  newly covered land. `docs/IMPLEMENTATION_PLAN.md` §6.1 records it in full.
- Phase 6 — the E1–E9 validation experiments (`src/validate/experiments.py`,
  run by `python -m tools.experiments`, i.e. `make validate`). `docs/VALIDATION.md`
  ships a table, an SVG figure and limitation notes per experiment, with the
  machine-readable results in `validation/results.json`; `tests/test_experiments.py`
  covers the harness on the deterministic synthetic input. Honest outcomes on
  the current cache (1,484,296 detections, VIIRS join 2012-01-20): E1 the
  artificial step shrinks 3.15× → 1.16× (the observed two-year-window step
  3.03× → 2.12×); E2 **partial** — calibration cuts the leave-one-year-out
  median |log offset| from 1.61 to 0.39, still above the report's pre-registered
  0.25 ceiling; E3 the `c_min` sweep moves the kept fraction by 0.10 and the
  step by 0.13; E4 a static mask at `min_days` 32 would remove 4.0% of
  cell-days; E5 quantile mapping (0.41) beats multiplicative (0.54) and
  log-log (0.63) in-sample; E6 the seasonal peak bin is stable across
  daily/weekly/8-day; E7 the VIIRS-to-MODIS ratio grows 3.08 → 4.23 as NOAA-20
  and NOAA-21 join S-NPP; E8 **not run** — no MCD64CMQ burned-area data is
  bundled and it needs Earthdata authentication, so it is reported as a
  limitation rather than an invented r²; E9 cache 216.3 MiB, API payload
  latency 1.30 s, with Lighthouse and a real-device cold start not run.
- `docs/REFERENCES.md` — dataset provenance (FIRMS products and routes, with
  attribution), the project's AI-use policy (deterministic code performs the
  science; no model in the path; synthetic data always labelled) and the method
  bibliography, closing the "documents datasets, AI use, and references" item
  of `docs/IMPLEMENTATION_PLAN.md` §11.

### Changed

- E8 external validation now runs instead of reporting a limitation. MODIS
  **MCD64A1 v061** burned area (500 m, monthly, HDF4) is fetched through
  `earthaccess` with an Earthdata Login token and regridded to 0.25° by the new
  `src/acquire/burned_area.py` (the plan's 0.25° CMG product, MCD64CMQ, is not
  published to CMR, so `earthaccess` cannot discover it). The result is honest:
  on the 2019 slice the cell-level r² is **0.342**, below the 0.5 target, while
  region-level monthly totals reach r² = 0.868 — seasonal timing validates, the
  spatial target does not. Adds `pyhdf` (the only HDF4 reader available here;
  rasterio's bundled GDAL has no HDF4 driver) and `earthaccess` to `make venv`.
- The API data tier reads parquet through DuckDB (`read_parquet`) on a single
  process-wide connection instead of a hand-rolled `pd.concat`; a multi-file
  cache glob is unioned in one query. Resolution order, `meta.source` values
  and the `NoDataError` → 503 behaviour are unchanged.
- `/api/v1/series` is continuous over the dataset's date range (a day with no
  detections is a zero count, not a missing day), and S7 `coverage`/`source`
  are computed from the availability calendar rather than from detections.
- The API's analysis endpoints honour a JSON body: `aoi`, `date` and `bbox`
  override the query parameters, and `metric`/`view` are validated so a caller
  cannot believe they changed anything. `metric=density` is served by the
  series payload (Added above); every other endpoint still refuses it rather
  than answering in `cell_days`.
- Every API failure is now `{code, message, field}` (`unknown_aoi`,
  `unsupported_metric`, `invalid_bbox`, `invalid_window`, `invalid_request`),
  including FastAPI's own parameter-validation errors.
- The layout no longer overflows at narrow widths: the shell tracks are
  `minmax(0, 1fr)` with `min-width: 0` on their children, and a 640px breakpoint
  collapses the rail further.
- The API now serves the frozen contract: all nine payloads under `/api/v1`
  (`meta`, `series`, `cells`, `baseline`, `anomalies`, `critical-period`,
  `validation`, `methods`, `aoi`), each carrying `params_hash`. The unversioned
  `/api/*` paths remain as aliases and the analysis endpoints also accept POST,
  as `docs/ApplicationFlow.md` and `docs/DEPLOYMENT.md` describe.

### Fixed

- The API had been serving pre-migration payload shapes (`rows`,
  `raw_pearson`, `h`/`l`/`n`, `overlap.{start,end}`, no `params_hash`) that
  neither the mock payloads nor the frontend's types used. The draft-07
  `definitions` alias in `docs/contract.schema.json` let two suite halves
  validate against two disagreeing definitions, which hid it; the alias is
  removed and every test validates against `$defs`. The frontend now runs
  against the API with `VITE_DATA=api`.
- The non-evidence banner said "Mock data" for the `fixture` tier as well; it
  now names the source it is actually showing.
- The `aoi` field of an analysis POST body now also accepts the AOI object
  `docs/TRD.md` §6.1 defines (`{type: "preset", id}`); the smoke-test body in
  `docs/DEPLOYMENT.md` §8 had been rejected with "Input should be a valid
  string" before any route ran. Custom geometry is refused with 422
  `invalid_request` rather than silently falling back to the default area.
- `GET /meta` — the root alias `docs/TRD.md` §6 lists and the smoke test in
  `docs/DEPLOYMENT.md` §8 curls; only `/api/meta` and `/api/v1/meta` were
  routed, so the runbook's own check answered 404.
- The acquisition layer could never resume after a transient NASA throttle:
  `download_chunk` wrote *any* payload — including the `invalid map_key.`
  error page — to its CSV cache before parsing it, so one bad response made
  every later run raise on the poisoned file instead of re-fetching. The CSV
  is now written only after it parses as fire data, and an already-poisoned
  cache falls through to a live fetch. This is what stalled `make cache` at
  457 chunks.
- The real cache could not be read at all: MODIS CSVs carry `brightness` and
  VIIRS CSVs carry `bright_ti4`, so a plain `read_parquet` glob failed on the
  schema mismatch and every `/api/v1/*` route answered 500. The union is now
  requested explicitly (`union_by_name = true` in `src/api/dataset.py`) with
  `tests/test_dataset.py::test_read_parquet_unions_products_that_do_not_share_a_csv_shape`
  guarding it; the contract was never loosened to accommodate the shape.

### Notes

- Baseline derived from `docs/Icarus_Project_Build_Specification.docx` v1.0.
- Numeric targets and dependency versions that are still open are marked
  "TBD — needs decision" rather than guessed.

---

## [1.0.0] — 2026-10-05

### Added

- `docs/Icarus_Project_Build_Specification.docx` v1.0 — the comprehensive build
  specification (objectives, architecture, data sources, harmonization
  algorithms, calibration, anomaly detection, API, storage, validation plan,
  security, and risk register).

---

## How to use this file

- Add entries under `## [Unreleased]` as you work.
- Group changes under `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, or
  `Security`.
- On release, move entries into a new version section with today's date and
  update the comparison links.
- Do not claim work that has not been done. Report negative results and known
  gaps here too.
