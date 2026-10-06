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
- [ ] Frontend acceptance checks not yet automated (no-third-party-request Playwright test, release guard)

Verified this session: `tsc --noEmit` clean; 16 vitest cases pass; `vite build` succeeds
(186 kB JS / 61 kB gzip); the built app loads in a browser, the mode toggle flips
`aria-pressed` and updates the hash without a refetch, keyboard navigation reaches all
eight views, the validation panel renders the mock's raw 0.992 / harmonized 0.997
correlations, and the console is clean.

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
- [ ] Coverage/bridge stages (S7/S8) — those belong to the calibration work, not this phase

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
| Data tier | `src/api/dataset.py` | Cache-then-fixture resolution, `OFFLINE=1` forces the fixture |
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
- [ ] DuckDB queries — the data tier still reads parquet through pandas
- [ ] `POST` bodies: the analysis endpoints accept POST, but the geometry body
      `docs/ApplicationFlow.md` describes is not implemented (query params only)
- [ ] Coverage/`source` per bin (`docs/TESTING.md` §9) — needs the S7 stage

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

**Found, not fixed:** the app still shows its static "Mock data" banner when the
source badge says `fixture`. That is the Phase 1 mock-banner/release-guard item
(§3.3) and it is now a live inconsistency rather than a latent one.

---

## 6. Phase 4 — Swap mock for real data

1. Run the pipeline and point the frontend at the API (one env var).
2. Fix shape differences by changing code, never by loosening the schema.
3. **Check the finding:** the real raw series must show the step and the
   harmonized series must reduce it. If not, investigate before polishing —
   the whole project rests on this.
4. Report validation numbers honestly.
5. Lock scope; apply the cut order if behind (§9).

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

---

## 8. Phase 6 — Validation (E1–E9)

Run and document the pre-registered experiments (see `docs/TESTING.md` §9).
Report negative results. Each result ships with a figure, a table, and
limitations.

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
  references.
