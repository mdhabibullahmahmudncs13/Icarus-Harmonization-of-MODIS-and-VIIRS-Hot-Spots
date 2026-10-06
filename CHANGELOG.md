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
- `src/compute/coverage.py` — the S7 availability/coverage stage: per-bin family
  coverage and `MODIS`/`VIIRS_CAL`/`NONE` source tagging (`BRIDGE` is in the
  vocabulary but not yet reachable). `docs/contract.schema.json` gains
  `$defs/binSource` and `coverage`/`source` on `seriesPoint`; the mock
  generator, the `coverage_bins.json` golden, the frontend types and
  `aggregateToBins` all carry them, so the calendar hatches an under-observed
  bin instead of reading it as zero activity.

### Changed

- The API data tier reads parquet through DuckDB (`read_parquet`) instead of a
  hand-rolled `pd.concat`; a multi-file cache glob is unioned in one query.
  Resolution order, `meta.source` values and the `NoDataError` → 503 behaviour
  are unchanged.
- The API's analysis endpoints honour a JSON body: `aoi`, `date` and `bbox`
  override the query parameters, and `metric`/`view` are validated so a caller
  cannot believe they changed anything. `metric=density` is refused rather than
  served as `cell_days`, since the density series does not exist yet.
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
