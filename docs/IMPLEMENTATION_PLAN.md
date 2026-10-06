# Implementation Plan — Frontend First

**Version:** 1.0 · **Date:** 05 October 2026 · **Status:** Baseline
**Approach:** build the frontend against mock data first, freeze the JSON
contract, then build compute, then the API, then swap mock for real data, then
harden offline. See `docs/ROADMAP.md` for the spec's work breakdown and
`docs/DESIGN.md`, `docs/ScreenFlow.md`, `docs/ApplicationFlow.md`,
`docs/UserFlow.md` for the frontend definition.

**Rule:** the killer demo comes first. A single **Raw | Harmonized** toggle must
visibly collapse the false sensor step. Everything else supports that moment.

---

## 1. Sequencing principle

```
Phase 0  Contract + mock        (freeze the JSON shapes)
Phase 1  Frontend on mock       <-- "make ready the frontend"
Phase 2  Compute                (deterministic science, tested)
Phase 3  API                    (serve the frozen contract)
Phase 4  Swap mock -> real data (one env var)
Phase 5  Offline hardening
Phase 6  Validation (E1-E9)
Phase 7  Release / demo
```

Frontend-first means the contract is exercised before the backend exists, and
swapping mock for real changes one variable — not the app.

---

## 2. Phase 0 — Contract + mock (foundation)

**Deliverable:** the JSON contract and generated mock payloads.

- Define the contract for: `meta`, `series`, `cells`, `baseline`, `anomaly`,
  `critical-period`, `validation`, `methods`, `aoi` (see
  `docs/ApplicationFlow.md` §4).
- Every payload includes `meta.source` (`mock | fixture | cache | live`) and the
  parameter hash.
- Mock generator: seed PRNG, generate **cell-day records first**, then
  aggregate, so series, cells, and calendar always agree. Tune so raw counts
  roughly triple at the sensor transition while harmonized counts stay
  comparable.
- Validate mock files against the schema in the generator itself.

### 2.1 Phase 0 artifacts

| Artifact | Path | Purpose |
|----------|------|---------|
| Contract schema | `docs/contract.schema.json` | Frozen JSON Schema (draft 2020-12), one `$defs` entry per payload |
| Mock generator | `tools/gen_mock.py` | Deterministic, stdlib-only generator; `--check` validates without writing |
| Mock payloads | `web/public/mock/*.json` | Nine payloads consumed by the frontend |
| Contract test | `tests/test_contract.py` | Validates every payload against the schema and asserts it is labelled `mock` |

Regenerate and verify:

```bash
python3 tools/gen_mock.py --out web/public/mock
python3 tools/gen_mock.py --check
python3 -m pytest tests/test_contract.py -q
```

### 2.2 Phase 0 status

- [x] Contract frozen (`docs/contract.schema.json`).
- [x] Deterministic mock generator (byte-identical on regeneration).
- [x] Nine payloads generated and schema-validated.
- [x] Contract test passing (20 cases).
- Measured step ratios on the generated mock: raw **3.81x**, harmonized
  **1.12x**; overlap raw/total ratio 0.36 vs harmonized 0.92.

**Exit:** all mock files validate; the raw series shows a clear step at the
sensor transition and the harmonized series does not.

---

## 3. Phase 1 — Frontend on mock data *(make ready the frontend)*

Build the shell and every screen from `docs/ScreenFlow.md` and `docs/DESIGN.md`,
running entirely on mock data with no network.

### 3.1 Milestones

| ID | Scope | Acceptance |
|----|-------|------------|
| **F1** Shell | App scaffold, design tokens, rail, brand block, source badge, mock banner, keyboard hint | App loads from mock files with **no network request** |
| **F2** Mode + hero series | `Raw \| Harmonized` control, hero chart, sensor epoch markers, animated transition, URL-synced mode | Toggle visibly removes the step; no refetch fires |
| **F3** Calendar | Years × 46-bin heatmap driven by the same mode, tooltip with value/units/coverage/source | Calendar updates on toggle without refetching |
| **F4** Map | Cell polygons shaded by mode, legend with units, AOI presets + polygon draw | Cells recolor on toggle |
| **F5** Evidence screens | Anomaly box, Critical period panel, Validation card, Methods panel, Provenance drawer | Every figure opens its source JSON |
| **F6** Quality | Five states per screen (loading/empty/error/offline/mock), responsive, keyboard, reduced motion | Passes §3.3 checks |

### 3.2 Screens to deliver

Overview, Calendar, Map, Anomalies, Critical period, Validation, Methods,
Offline (see `docs/ScreenFlow.md` §1).

### 3.3 Frontend acceptance checks

- **No third-party requests.** A Playwright test blocks all external hosts; the
  app still loads and works.
- **Toggle correctness.** Every view changes on mode change; no network request
  fires on toggle.
- **Contract validation.** Mock payloads validate against the shared schema.
- **Accessibility.** Keyboard-only operation of the mode control and date
  control; axe passes; focus always visible.
- **Release guard.** A release build fails if it is running on mock data.
- **Performance.** Toggle response under 100 ms with the full mock series.

### 3.4 Time-box

If the map (F4) slips, ship it with static polygons and no date control. Do not
let it delay F5. Keep the toggle demo intact above all.

### 3.5 Phase 1 status

The frontend runs on the Phase 0 mock payloads. Artifacts:

| Artifact | Path |
|----------|------|
| App shell | `web/src/App.tsx` |
| Rail / mode toggle / status | `web/src/components/Rail.tsx`, `ModeToggle.tsx`, `shared.tsx` |
| Charts | `web/src/components/SeriesChart.tsx`, `CalendarHeatmap.tsx`, `RegionMap.tsx` |
| Panels | `web/src/components/panels.tsx`, `ProvenanceDrawer.tsx` |
| Data layer | `web/src/data/DataSource.ts` |
| State (URL-synced) | `web/src/state/urlState.ts`, `useAppState.ts` |
| Pure logic | `web/src/lib/series.ts` |
| Design tokens | `web/src/styles/tokens.css`, `app.css` |
| Unit tests | `web/tests/series.test.ts`, `urlState.test.ts` |

Build and verify:

```bash
cd web
npm install
npm run typecheck      # tsc --noEmit
npm test               # vitest run
npm run build          # tsc + vite build
npm run preview        # serve dist/ on :4173
```

Status against the F1–F6 milestones:

- [x] **F1** shell — rail, brand, mode control, source badge, mock banner, keyboard hint
- [x] **F2** mode toggle + hero series with a VIIRS-transition marker, URL-synced
- [x] **F3** calendar heatmap (years x 46 bins, derived client-side from the daily series)
- [x] **F4** region map — cells shaded by mode, with a legend
- [x] **F5** anomaly, critical-period, validation and methods panels + provenance drawer
- [x] **F6** keyboard shortcuts (1–8, R/H, T, P, Ctrl/Cmd+B, Esc), loading/empty/error states, dark default
- [x] **F6** keyboard shortcuts (1–8, R/H, T, P, Ctrl/Cmd+B, Esc), loading/empty/error states, dark default
- [x] Release guard — `npm run build:release` fails when the build would run on
      non-evidence data (§3.3)
- [x] No-third-party-request check — `web/e2e/no-third-party.spec.ts` (Playwright)
      blocks and records every host that is not the preview server, then still
      exercises the shell and the mode toggle; it replaces the manual read of
      the browser's network log. A canary run confirmed the interception
      catches an injected external request. Run with:
      `cd web && ./node_modules/.bin/vite build && ./node_modules/.bin/playwright test`

**Source-accurate banner.** The non-evidence banner used to say "Mock data" for
any source that was not evidence, including the `fixture` tier. Each source now
has its own notice, defined once in `web/src/lib/source.ts` and asserted by
`web/tests/source.test.ts`, so a tier can never be labelled with another tier's
name.

**Responsive fix.** A 390 px viewport showed horizontal overflow: the collapsed
rail kept its content's width and the main column could not shrink below its
content. `minmax(0, 1fr)` on the shell tracks, `min-width: 0` on the grid's
children, and a 640 px breakpoint removed it — all six views now report
`scrollWidth == viewport` at 390 px, and the desktop rail is unchanged at 244 px.

Verified this session: `tsc --noEmit` clean; 26 vitest cases pass (16 prior +
10 new); `vite build` succeeds and `vite build --mode release` exits 1 when
`VITE_DATA` is not `api`. The built app loads in a browser, the mode toggle flips
`aria-pressed` and updates the hash without a refetch, keyboard navigation reaches all
eight views, and the console is clean.

---

## 4. Phase 2 — Compute (`src/compute`, deterministic)

1. Normalize MODIS/VIIRS to one schema; map VIIRS l/n/h to numeric via a single
   documented constant.
2. Grid assignment and cell-day collapse (`docs/ARCHITECTURE.md` §2).
3. Raw and harmonized series; seasonal baseline (day-of-year percentiles).
4. Anomaly rank; overlap validation and cell-size sweep.
5. Tests: unit at edges, property (idempotence, row-order invariance,
   duplicates), golden files; a synthetic set where VIIRS ≈ 3× MODIS in-cell,
   asserting harmonized matches while raw does not.

**Exit:** tests pass; validation numbers produced; no network access in
`src/compute`.

### 4.1 Phase 2 status

Artifacts:

| Module | Responsibility |
|--------|----------------|
| `src/compute/schema.py` | Normalized `Detection`, stream bits, `VIIRS_CONFIDENCE`, S2 quality filter |
| `src/compute/grid.py` | S4 grid snap, S5 cell-day collapse/merge, daily series, per-cell totals |
| `src/compute/baseline.py` | Day-of-year helpers, `percentile`, seasonal baseline |
| `src/compute/anomaly.py` | z-score + percentile rank, elevated/extreme/not-scored flags |
| `src/compute/season.py` | Critical fire period (onset, peak, end, window mass) |
| `src/compute/validate.py` | Pearson/Spearman/ratio, overlap validation, cell-size sweep |
| `src/compute/series_util.py` | 46-bin day-of-year helper |
| `tools/gen_golden.py` | Writes the committed goldens; `--check` fails on drift |
| `tests/golden/*.json` | Committed output of the deterministic pipeline |
| `tests/test_compute.py` | 21 unit, property and golden cases |
| `tests/test_golden.py` | 23 golden-drift and harmonization-mechanism cases |

Run and verify:

```bash
python3 -m pytest tests/test_compute.py tests/test_golden.py -q
python3 -m pytest -q
python3 -m tools.gen_golden --check   # or: make golden  (regenerate on drift)
```

Status:

- [x] Normalized schema + single documented VIIRS confidence mapping
- [x] Grid snap and cell-day collapse (bitmask, n_det, max_frp)
- [x] Raw and harmonized series; per-cell totals
- [x] Seasonal baseline (day-of-year percentiles)
- [x] Anomaly z-score with `sigma_floor`, percentile rank, flags
- [x] Critical-period detection with the insufficient-activity case
- [x] Overlap validation and cell-size sweep
- [x] Unit edges, property invariants (idempotence, row-order, duplicates), golden scenario
- [x] Golden files committed as fixtures (`tests/golden/*.json`, guarded by `tests/test_golden.py`)
- [x] Coverage stage (S7) — per-stream availability from the product epochs and
      the outage table; `MODIS`/`BRIDGE`/`VIIRS_CAL`/`NONE` source tagging
      (`src/compute/coverage.py`, `src/compute/availability.py`)
- [x] Multiplicative calibration (S8) — `r(t, m)` with the kappa shrinkage,
      applied to VIIRS-anchored bins (`src/compute/calibrate.py`)

The goldens cover both canonical inputs: the step scenario (series, cells,
seasonal baseline, critical period) and the two overlap validators
(`identical_cell_days` and `synthetic_detections`), plus a `headline` file with
the step and agreement ratios. They are committed JSON rather than parquet so
they are readable in a diff and outside `.gitignore`.

**Note — what a golden test asserts.** `tests/test_golden.py` recomputes each
payload and compares it to the committed file, so any number that moves fails
the suite until the goldens are deliberately regenerated. `tests/test_compute.py`
reads the committed `step_series.json` for its headline ratio assertion rather
than regenerating the scenario in-test.

**Note — deliberate extension over the spec.** The spec's `cell_day` stores a
single combined `n_det`, which cannot yield per-stream *detection* totals. Each
`CellDay` here also carries `n_modis` and `n_viirs` so the raw series is
derivable in one pass. `n_det` remains the combined total and is unchanged.

Verified this session: `make lint` clean; 179 tests pass, of which 21 are
`test_compute.py` and 23 are `test_golden.py`; no network access anywhere in
`src/compute`. The committed goldens record a raw step of 3.00x against a
harmonized step of 1.00x on the same cells, a 3.0x-to-1.0x collapse on the
identical-sensor overlap, and a Pearson of 0.707 raw to 0.901 harmonized on
the noisy overlap. Drift is proven caught: perturbing `step_series.json` fails
both `pytest tests/test_golden.py` and `python3 -m tools.gen_golden --check`,
and `make golden` restores the file byte-for-byte.

---

## 5. Phase 3 — API (`src/api`)

- FastAPI endpoints matching the frozen contract exactly; read-only; DuckDB.
- Every response carries `params_hash` and truthful `meta.source`.
- Contract tests: call every endpoint, validate against the shared schema;
  invalid AOI → 422 `{code, message, field}`.
- Offline-first: prefer cache, fall back to fixture; `OFFLINE=1` forces fixture.

**Exit:** contract tests pass; the frontend can run with `VITE_DATA=api`.

### 5.1 Phase 3 status

Artifacts:

| Artifact | Path | Purpose |
|----------|------|---------|
| Routes | `src/api/main.py` | Nine payloads under `/api/v1`, unversioned aliases kept |
| Data tier | `src/api/dataset.py` | Cache-then-fixture resolution through DuckDB, `OFFLINE=1` forces the fixture |
| Availability | `src/compute/availability.py`, `src/outages.json` | S7: stream epochs minus the outage table |
| Coverage stage | `src/compute/coverage.py` | S7: per-bin coverage and source tagging |
| Calibration | `src/compute/calibrate.py` | S8: multiplicative VIIRS-to-MODIS factor |
| Payload builders | `src/compute/export.py` | The contract JSON, shared with the static export |
| AOI presets | `src/aoi_presets.json` | One preset list for the API and the mock generator |
| Contract tests | `tests/test_api.py`, `tests/test_export.py` | Every payload against `$defs` |

Run and verify:

```bash
python3 -m pytest tests/test_api.py tests/test_export.py -q
python3 -m pytest -q
OFFLINE=1 python3 -m uvicorn src.api.main:app --port 8000
```

Status:

- [x] All nine contract payloads served under `/api/v1`
- [x] Every response validated against `$defs` (not a second, disagreeing alias)
- [x] `params_hash` on every payload, identical across one request's payloads
- [x] Truthful `meta.source`; `OFFLINE=1` forces the fixture tier
- [x] No network tier: the suite answers with sockets blocked
- [x] 422 on a malformed window/bbox; 404 outside the data range
- [x] The frontend runs against the API (`VITE_DATA=api`) — verified in a browser
- [x] `POST` bodies: `aoi`, `date` and `bbox` are honoured and override the
      query parameters; body and query share one validator
- [x] Every failure is `{code, message, field}` (422 `unknown_aoi`,
      `unsupported_metric`, `invalid_bbox`, `invalid_window`, `invalid_request`)
- [x] DuckDB data tier — the cache and the fixture are read through DuckDB's
      `read_parquet` on one reused connection, which also unions a multi-file
      cache glob in one query
- [x] Coverage/`source` per bin (`docs/TESTING.md` §7) — the S7 stage, with all
      four source classes reachable
- [x] VIIRS-anchored bins are calibrated (S8) rather than only tagged
- [x] `metric=density` is served by `/api/v1/series` — the same counts divided
      by the region's grid-cell count (`harmonize.grid_cell_count`), so
      `harm_*` is the 0–1 active-cell fraction and `raw_*` detections per cell.
      The contract discriminates `$defs/densityPoint` from `$defs/seriesPoint`
      on `series.metric`, and the endpoints whose payloads carry no `metric`
      still refuse `density` (422 `unsupported_metric`) rather than ignore it

**The defect this phase fixed.** The API served pre-migration payload shapes
(`rows`, `raw_pearson`, `h`/`l`/`n`, `overlap.{start,end}`, no `params_hash`)
while the contract, the mock generator and the frontend's own types agreed on
the `$defs` shapes. Two schema definition families existed — `$defs` and a
draft-07 `definitions` alias — so `tests/test_api.py` validated the API against
one and `tests/test_contract.py` validated the mock against the other, and both
suites passed over payloads that could not interoperate. The alias is removed,
the builders emit the contract, and every test now validates against `$defs`.

**No schema change was needed for the season window.** `$defs/criticalPeriod`
already admitted `window: null` (its `start_bin` is bounded to 1-46, so no zero
window exists), which is what the mock generator emits and the frontend types
allow. The first implementation of `build_critical_period` invented a zero
window and failed validation; it now emits `null` with
`insufficient_activity: true`, matching the contract. The only change to
`docs/contract.schema.json` is the removal of the `definitions` alias.

**S7 coverage is a property of the observing calendar, not of the detections.**
`src/compute/availability.py` builds `a(s, d)` from the FIRMS product epochs
minus the outage table (`src/outages.json`); `src/compute/coverage.py` rolls
that up into per-bin `both_frac`/`cov_modis`/`cov_viirs` and tags the bin
`MODIS` (both MODIS satellites up), `BRIDGE` (one), `VIIRS_CAL` (VIIRS only) or
`NONE` (none). All four classes are reachable and the demo fixture exercises
each, so the calendar hatches a `NONE` bin instead of reading it as zero — the
series is continuous, so an outage bin still has rows to hatch. This closes the
earlier limitations: availability is the acquisition calendar rather than an
observation-day proxy, and `BRIDGE` is emitted from a real single-satellite
window instead of being reserved.

**S8 calibration makes `VIIRS_CAL` true.** `src/compute/calibrate.py` implements
`r(t, m) = (M(t, m) + kappa * r_reg(m)) / (V(t, m) + kappa)` over 1-degree tiles
and calendar months (kappa = 50), and `build_series` scales the VIIRS counts of
a `VIIRS_CAL` bin by the month's AOI factor. `VIIRS_CAL` now means calibration
was applied, not merely that VIIRS had coverage.

**The demo fixture shows the outages.** `python -m src.demo` blanks MODIS for a
10-25 June 2019 window and every sensor for 1-5 August 2019, matching the
outage table, so the offline calendar shows `BRIDGE`, `VIIRS_CAL` and the
hatched `NONE` state without any network.

**DuckDB data tier, with the connection reused.** The cache and the fixture are
read through DuckDB's `read_parquet` on one process-wide in-memory connection;
the fixed connection cost previously dominated a single-file read. Measured:
~11 ms vs ~2 ms on the committed fixture and ~10 ms vs ~8 ms across an
eight-file cache — a flat fixed cost against pandas' per-file scaling, and the
dataset is read once per process behind the existing cache. Resolution order,
`meta.source` values and the `NoDataError`→503 behaviour are unchanged and
covered by `tests/test_dataset.py` plus `tests/test_api.py`.

Verified this session: `make lint` clean; 201 tests pass. `OFFLINE=1` uvicorn
served all nine `/api/v1` routes plus `/api/meta`, each validated against
`$defs` with a format checker; one request yields one `params_hash`. Built with
`VITE_DATA=api`, the app loaded in headless Chromium and its own
`ApiDataSource` fetched `/api/meta` and the eight `/api/v1` payloads, all 200,
with the source badge reading `fixture`; every request went to the local app or
the local API and no third-party host was contacted. Validation rendered
Pearson 0.844 raw vs 0.953 harmonized (ratio 4.19 -> 1.33), the critical period
onset bin 4 / peak 11 / mass 87%, and the anomaly panel reported `not scored`
with its reason. No console errors or page errors.

**Closed since:** the "Mock data" banner that stood over the `fixture` tier is
fixed — the banner names its source and the release guard refuses a non-evidence
release build (§3.5).

---

## 6. Phase 4 — Swap mock for real data

1. Run the pipeline and point the frontend at the API (one env var).
2. Fix shape differences by changing code, never by loosening the schema.
3. **Check the finding:** the real raw series must show the step and the
   harmonized series must reduce it. If not, investigate before polishing —
   the whole project rests on this.
4. Report validation numbers honestly.
5. Lock scope; apply the cut order if behind (§9).

### 6.1 Phase 4 status

- [x] Pipeline run on real FIRMS data — the three archive products
      (`MODIS_SP`, `VIIRS_SNPP_SP`, `VIIRS_NOAA20_SP`) plus NOAA-21 as
      `VIIRS_NOAA21_NRT` (the Area API serves no `VIIRS_NOAA21_SP` — it
      answers `Invalid source.` — so NRT is the only source FIRMS offers
      for that satellite; the product table and this plan were corrected
      rather than leaving a source that can never download), downloaded
      through `src/acquire` into `cache/raw/*.parquet`; the drivers are
      `cache/download.sh` and `cache/download_n21.sh` (two products at a
      time, retries with backoff against NASA's throttle). The merged
      cache holds the SP archive products — **1,378,592 detections**,
      2003-01-02 → 2026-06-28, 3,054 chunk parquets — with NOAA-21 NRT
      (epoch starts 2023) downloading separately.
- [x] Frontend pointed at the API (one env var:
      `VITE_DATA=api VITE_API_BASE=…`) — the badge reads `cache`,
      `params_hash f4b82ef0c728`, and `/api/v1/*` serves all six views.
- [x] Shape differences fixed in code, never by loosening the schema —
      MODIS CSVs carry `brightness`, VIIRS carries `bright_ti4`; a plain
      glob made DuckDB reject every request. Fixed with
      `read_parquet(..., union_by_name = true)` in
      `src/api/dataset.py`, guarded by
      `tests/test_dataset.py::test_read_parquet_unions_products_that_do_not_share_a_csv_shape`.
- [x] **Check the finding** — pre (2010–11, MODIS-only) vs post
      (2013–14): raw total **34.0 → 184.1 detections/day = 5.42×**;
      harmonized total **18.2 → 68.5 cell-days/day = 3.77×**; the
      MODIS-only activity control is **0.92×**, so the jump is
      sensor-driven, not burning-driven. First VIIRS detection:
      2012-01-20. Mechanism: inside MODIS-supported cells the factor is
      3.65× while VIIRS-novel cells add only ~2/day — the residual step
      is VIIRS's temporal density (more days / more inside-cell events),
      not newly covered land.
- [x] Browser verification on the real cache — the overview chart shows
      the raw step with the “VIIRS begins” marker (pre-2012 peaks
      ≈2,000/day, post-2012 peaks 5,000–10,000/day), the harmonized mode
      overlays a visibly flatter series, and flipping Raw ⇄ Harmonized
      issues **zero new requests** (both series ship in one payload).
      The validation card reports the overlap numbers below.
- [x] Report validation numbers honestly — overlap over 15 years / 4,665
      days: Pearson **0.779 → 0.823**, Spearman 0.822 → 0.812, ratio
      **6.54 → 4.02**. Harmonization **reduces but does not eliminate**
      the real-data step; the calibration shrinks the sensor jump by
      about a third and lifts linear agreement, while rank agreement is
      essentially flat. This is the honest result and it ships as-is.

---

## 7. Phase 5 — Offline hardening

- Commit the minimum demo set as fixtures; precompute the demo payloads.
- Package the basemap as PMTiles; serve locally.
- Service worker (Workbox): precache shell, cache-first tiles,
  stale-while-revalidate data, versioned caches.
- Self-host every font, glyph, sprite, and library.
- Show the source badge (`live`/`cache`/`fixture`) throughout.
- Backend portable: FastAPI + cache in one command / one Docker image.
- **Gate:** a cold start with the network off succeeds on a real device.
  Record a fallback video.

### 7.1 Phase 5 status

- [x] Service worker (`web/public/sw.js`, registered by `web/src/lib/sw.ts`
      in production builds): versioned `icarus-*` caches, the shell
      precached, cache-first hashed assets, stale-while-revalidate for
      `/mock/` and `/api/`, network-first navigations with the cached shell
      as the offline fallback. The page reports the resources it used (the
      nine mock payloads by name, plus the performance timeline) so the
      first visit caches them deterministically — they are fetched before
      the worker activates and would otherwise be missed. Cached responses
      are stored without the preview server's `Vary: Origin` and
      `content-encoding` transport headers, which otherwise made an offline
      reload fail with `net::ERR_FAILED`.
- [x] Cold start with the network off — the gate above, automated:
      `web/e2e/offline-cold-start.spec.ts` waits for the worker to cache the
      app, sets the browser offline and reloads; the shell, the data and the
      Raw | Harmonized toggle all come from the caches. (A real-device run
      and the fallback video are still to be recorded for the demo.)
- [x] Self-host every font, glyph, sprite and library — there is nothing
      external to host: the app uses the system font stack and bundled
      dependencies only, which `web/e2e/no-third-party.spec.ts` proves by
      blocking every other host.
- [x] Source badge shown throughout (`web/src/lib/source.ts`).
- [x] Minimum demo set committed as fixtures (`demo_fixtures/detections.parquet`).
- [ ] Package the basemap as PMTiles — not applicable yet: the map is
      client-side SVG polygons and requests no tiles at all. Revisit when a
      MapLibre basemap lands; the no-third-party test is what keeps it honest.
- [ ] Backend portable as one Docker image — `make demo` is one command, but
      the image `docs/DEPLOYMENT.md` §1 describes does not exist yet.
- [ ] Real-device cold start and the recorded fallback video — need a device.

---

## 8. Phase 6 — Validation (E1–E9)

Run and document the pre-registered experiments (see `docs/TESTING.md` §9).
Report negative results. Each result ships with a figure, a table, and
limitations.

### 8.1 Phase 6 status

Implemented in `src/validate/experiments.py`, run by `python -m tools.experiments`
(`make validate`) over the served detections; the report is `docs/VALIDATION.md`,
with figures under `validation/figures/` and machine-readable results in
`validation/results.json`. `tests/test_experiments.py` covers the harness on the
deterministic synthetic input.

- [x] E1 — step-change detection: the artificial cell-day step at the join
      shrinks **3.15× → 1.16×**; the observed two-year-window step shrinks
      3.03× → 2.12× (a different window from §6.1, and noted as such).
- [x] E2 — calibration residual offset: **partial**. Leave-one-year-out the
      median |log offset| falls 1.61 → 0.39, an improvement that still sits
      above this report's pre-registered 0.25 ceiling.
- [x] E3 — quality threshold: sweeping `c_min` {20,30,40,50} moves the kept
      fraction by 0.10 and the harmonized step by 0.13 — the result is not
      threshold-fragile.
- [x] E4 — static-mask sensitivity: `min_days` {8,16,32} would remove 0.8%,
      1.8% and 4.0% of cell-days respectively (the pipeline itself applies no
      mask).
- [x] E5 — non-linear calibration: quantile mapping (0.41) beats
      multiplicative (0.54) and log-log (0.63) in-sample; quantile mapping is
      optimistic by construction and flagged.
- [x] E6 — temporal resolution: daily / weekly / 8-day agree on the seasonal
      peak bin.
- [x] E7 — VIIRS inclusion: the VIIRS-to-MODIS cell-day ratio grows
      3.08 → 4.23 as NOAA-20 and NOAA-21 join S-NPP.
- [x] E8 — external validation: **partial, and honestly so**. MODIS
      **MCD64A1 v061** burned area (500 m, monthly) is fetched through
      `earthaccess` with an Earthdata Login token and regridded to 0.25° by
      `src/acquire/burned_area.py` (the 0.25° CMG product in the original plan,
      MCD64CMQ, is not in CMR so it cannot be discovered). Over the 2019 slice
      (36 granules, 12 months, pilot bbox) the decision rule's cell-level r² is
      **0.342** (r = 0.585, Spearman 0.373, n = 1,949 cell-months) — **below the
      0.5 target** — while region-level monthly totals agree strongly at
      r² = 0.868. Seasonal timing is validated; the spatial cell-level target is
      not met. Only 2019 is fetched so far; widen the window before treating it
      as final.
- [x] E9 — offline performance: cache 216.3 MiB / 6,988 files, `/api/v1/series`
      payload 1.30 s. Lighthouse PWA score and a real-device cold start remain
      unmeasured (see §7.1).

---

## 9. Cut order (if behind)

1. Reduce the region.
2. Shorten the time range — keep a window that includes the sensor transition.
3. Drop the anomaly engine; keep harmonization.
4. Replace live queries with static Parquet and fixtures.

Never cut the toggle demo or the offline cold start.

---

## 10. Dependencies and risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Contract drifts between mock and API | Integration pain | One shared schema; contract tests in CI |
| Mock numbers leak into the demo | Misleading | Mock banner + release guard; fixtures labelled |
| Sensor step not visible in real data | Demo weakens | Check early in Phase 4; adjust cell size; report honestly |
| Map/offline tile work overruns | Lost days | Static polygons first; PMTiles only in Phase 5 |
| Third-party request breaks offline | Demo fails | Playwright external-host block test |
| Parameter change silently alters outputs | Non-reproducible | Hash every artifact; regenerate on change |

---

## 11. Definition of done

- The mode toggle switches every view between raw and harmonized with no network
  request, and the step visibly disappears.
- All statistics come from tested `src/compute` functions; every figure opens
  its source JSON.
- `make cache`, `make demo` (offline), and `make test` pass; cold start works
  with the network off.
- The validation card shows raw and harmonized correlations from the overlap.
- The repo is public, Apache-2.0, and documents datasets, AI use, and
  references — `docs/REFERENCES.md` (datasets, the no-LLM-in-the-science
  policy, and the bibliography), with field detail in `docs/DATA_DICTIONARY.md`.
  The root `README.md` and `LICENSE` were intentionally retired in `c8781da`;
  Apache-2.0 is still the stated intent and should be restored before release.
