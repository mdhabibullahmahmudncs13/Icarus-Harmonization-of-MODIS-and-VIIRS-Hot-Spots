# Roadmap

How Project Icarus gets built, in order, with the deliverable and the MVP cut for
each work package. Derived from
`DOCS/Icarus_Project_Build_Specification.docx` §13.

Guiding order: **reproducible data first, then the pipeline, then the API, then
the frontend, then offline hardening and submission.** The harmonization result —
the collapsing step change — must be proven early, because the whole project
rests on it.

---

## 1. Work breakdown

| WP | Content | Weeks | Deliverable | MVP cut |
|----|---------|-------|-------------|---------|
| WP0 | Setup: repo, access keys, outage/stream tables, OpenAPI draft, mock JSON | 1 | Repo with CI; OpenAPI draft | Mock data and contract only |
| WP1 | Ingest S0–S1 for the pilot sub-region; manifest | 1–2 | `det.parquet` and manifest | One year pair per stream |
| WP2 | Pipeline S2–S5 (quality, mask, grid, cell-day) | 2–4 | `cell_day/` parquet | One full year pair |
| WP3 | S6–S8 (binning, coverage, calibration) | 4–6 | `cell_bin/`, `calib_factor.parquet` | Full pipeline, one year |
| WP4 | S9 + AOI aggregation, climatology, anomaly; API endpoints | 6–7 | `cell_bin_h/`, API | Harmonized view + anomalies |
| WP5 | Critical period, frontend, offline mechanism | 7–8 | Web app, service worker | Full MVP with offline |
| WP6 | Experiments, validation, documentation | 8–9 | E1–E9 report | All M requirements |
| WP7 | Demo prep, fallback video, final polish | 9–10 | Demo video, release | Offline demo working |

---

## 2. Milestones and gates

| Milestone | Gate | Evidence |
|-----------|------|----------|
| M0 — Contract frozen | Mock JSON validates; OpenAPI draft matches the API | Contract tests pass |
| M1 — Data on disk | Raw parquet for all pilot streams; manifest verified | `verify-manifest` clean |
| M2 — Pipeline complete | S0–S9 run end-to-end on one year pair | Golden-file tests pass |
| M3 — Harmonization proven | Artificial step shrinks (E1); offset reduced (E2) | E1/E2 figures |
| M4 — API + frontend | Series, anomalies, critical period render | E2E + contract tests pass |
| M5 — Offline | Cold start with network off; fallback video recorded | AC-3, AC-6 |
| M6 — Release | All M requirements pass; E1–E8 reported | AC-1 … AC-7 |

---

## 3. WP detail

### WP0 — Setup (week 1)

Repo, CI (lint + test on push), `.env.example`, `config/params.yaml` skeleton,
outage and stream reference tables, an OpenAPI draft, and contract JSON used by
both the frontend mocks and the API tests.

**Exit:** CI green on an empty skeleton; every interface has a name.

### WP1 — Ingest (weeks 1–2)

S0 acquisition (resumable, checksummed) and S1 normalization to the unified
detection schema.

**Risk:** downloads are slow or blocked (R1). Start immediately; scope to the
pilot sub-region.

### WP2 — Core pipeline (weeks 2–4)

S2 quality filter, S3 static mask, S4 grid snap, S5 cell-day collapse. Pure
functions in `src/core/`; orchestration in `src/pipeline/`.

**Exit:** `cell_day/` parquet for the pilot extent; unit + property tests.

### WP3 — Binning, coverage, calibration (weeks 4–6)

S6 8-day bins, S7 availability/coverage, S8 multiplicative calibration with
bootstrap.

**Exit:** `cell_bin/`, `bin_coverage`, `calib_factor`, `calib_boot`.

### WP4 — Harmonize + API (weeks 6–7)

S9 harmonized values with source tags; AOI aggregation; climatology, anomaly,
and critical-period endpoints under `/api/v1`.

**Exit:** read-only API serving the contract; earliest view of the step collapse.

### WP5 — Frontend + offline (weeks 7–8)

MapLibre map with PMTiles, d3 calendar, anomaly and critical-period panels,
provenance panel, offline manager, service worker (Workbox).

**Exit:** full MVP runs offline from a cold start.

### WP6 — Validation (weeks 8–9)

Run and document E1–E9 (`docs/TESTING.md` §9). Report honestly, including
negative results.

### WP7 — Release (weeks 9–10)

Demo video and fallback recording, provenance verification, final polish,
submission materials.

---

## 4. Cut order (if behind)

From the specification, in this order:

1. Reduce the region (already scoped to the pilot box).
2. Shorten the time range — keep a window that includes the sensor transition.
3. Drop the anomaly engine; keep harmonization.
4. Replace live queries with static Parquet and fixtures.

Keep the harmonization result and the offline demo intact to the end.

---

## 5. Out of scope (this cycle)

- Burned-area mapping (MCD64CMQ is a validation reference only).
- Fire-spread modelling and emissions estimation.
- Real-time alerting / notifications.
- Global deployment.

---

## 6. Open product/technical decisions

- Preset AOIs included at launch and their geometry ownership.
- Minimum device profile for the field demo.
- Whether the AI narration layer ships in the launch demo.
- Export formats (CSV / GeoJSON) and licensing.
- Numeric performance budgets and pinned dependency versions.
