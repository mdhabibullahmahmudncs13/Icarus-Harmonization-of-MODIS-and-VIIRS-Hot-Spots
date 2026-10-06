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
  - `DOCS/PRD.md` — product requirements.
  - `DOCS/TRD.md` — technical requirements.
  - `DOCS/SYSTEM_ARCHITECTURE.md` — system architecture baseline.
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

### Changed

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

### Notes

- Baseline derived from `DOCS/Icarus_Project_Build_Specification.docx` v1.0.
- Numeric targets and dependency versions that are still open are marked
  "TBD — needs decision" rather than guessed.

---

## [1.0.0] — 2026-10-05

### Added

- `DOCS/Icarus_Project_Build_Specification.docx` v1.0 — the comprehensive build
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
