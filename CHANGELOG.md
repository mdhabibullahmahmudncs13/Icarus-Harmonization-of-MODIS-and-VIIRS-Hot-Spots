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
