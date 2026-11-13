# Architecture

The single architecture document for Project Icarus: structure, runtime, and the
decision record. There is no separate system-architecture or application-flow
document. Neighbours: requirements in `docs/PRD.md` and `docs/TRD.md`, the
visual system in `docs/DESIGN.md`, screens and journeys in `docs/FLOWS.md`.
Design basis: `docs/Icarus_Project_Build_Specification.docx`.

---

## 1. Shape of the system

Icarus is a four-layer system. All NASA data is acquired **before** the event
(S0, network required). From then on the system is offline: the pipeline
transforms cached raw data into harmonized Parquet, a single read-only FastAPI
service answers DuckDB queries, and a static web app renders and caches results.

```
[NASA Sources]  FIRMS Archive / UMD SFTP / MCD64CMQ / LAADS DAAC
        │  (S0: pre-event, network required)
        ▼
[Pre-fetch Layer]  cache/raw/**  +  <source>.manifest.json (sha256, rows, dates)
        │  (S1–S9: offline batch, Python + DuckDB)
        ▼
[Data Cache]  cache/raw/*.parquet, demo_fixtures/detections.parquet
        │
        ▼
[FastAPI Service]  read-only; DuckDB queries; /api/v1/*
        │  HTTP (localhost or LAN)
        ▼
[Static Web App]  three.js globe + d3 calendar + service worker + cache
```

Rule: a layer may depend only on the layers above it, which keeps the offline
path intact when any layer is absent.

---

## 2. Layer responsibilities

| Layer | Responsibility | Network | Runtime |
|-------|----------------|---------|---------|
| Pre-fetch | Download and register raw files with checksums | Required (S0) | Pre-event batch |
| Data Cache | Store the acquired Parquet and the offline fixture | None | Build-time artifact |
| FastAPI Service | Serve read-only analytics over DuckDB | Local/LAN | Long-running process |
| Static Web App | Map, calendar, panels, offline cache | Local/LAN, then offline | User session |

Layers are strictly ordered by runtime: the pipeline and cache exist before the
event, and the API and web app run during the session.

---

## 3. Module map

```
src/
  acquire/       # S0: the only place NASA is called
    firms.py        FIRMS area API: products, pagination, manifest
    burned_area.py  MCD64A1 burned area (E8 external validation)
    safe.py         SAFE / UMD SFTP helpers
  compute/       # pure, deterministic, no I/O, no web framework
    schema.py       normalize detections; confidence mapping; stream bits
    harmonize.py    harmonization facade (grid, cell-days, series, calibration)
    series_util.py  8-day bin rule
    availability.py stream epochs and outage calendar
    coverage.py     per-bin coverage and source tagging
    calibrate.py    multiplicative calibration + bootstrap
    baseline.py     day-of-year helpers and percentiles
    anomaly.py      z-score and percentile-rank scoring
    season.py       critical-period onset/peak/end/window
    validate.py     raw vs harmonized overlap validation
    export.py       contract payload assembly
  api/           # read-only serving
    main.py         FastAPI app and routes
    dataset.py      DuckDB reads; dataset lifecycle
  validate/      # E1–E9 experiment harness
    experiments.py  experiment definitions and runners
    report.py       report assembly
  demo.py        # deterministic synthetic detections for the offline fixture
tools/           # gen_mock.py, gen_golden.py, experiments.py, export_payloads.py
tests/           # unit, property, golden, contract
web/             # the frontend: app at `/`, landing at `/landing.html`, one Vite build
config/params.yaml   # every tunable value
cache/            # git-ignored: the acquired data (raw/) and its manifests
demo_fixtures/    # the committed offline demo detections (tracked on purpose)
```

`compute/` is pure: values in, values out. All I/O and framework use live in
`acquire/`, `api/`, and `validate/`.

---

## 4. Component specifications

| Component | Responsibilities | Must not do |
|-----------|------------------|-------------|
| Ingest (`src/acquire`) | S0: download, checksum and register raw files; write the manifest | Run at app runtime |
| Compute (`src/compute`) | Pure functions: schema, grid, coverage, calibration, baseline, anomaly, season | Perform I/O or depend on web frameworks |
| API (`src/api`) | FastAPI app; read-only; JSON; parameter-hash header | Mutate data or compute statistics |
| Frontend (`web/`) | three.js globe map; d3 calendar; polygon drawer; offline service worker | Call NASA APIs directly |

---

## 5. Data flow S0–S9

```
S0 Acquire   → raw files + manifest (sha256, rows, retrieved, url)
S1 Normalize → det.parquet (unified schema, stream bits)
S2 Filter    → det_ok (quality rule per instrument)
S3 Mask      → det_clean (static/persistent sources removed)
S4 Snap      → cell indices (floor(lon*K), floor(lat*K))
S5 Collapse  → cell_day (stream_mask, n_det, max_frp)
S6 Bin       → cell_bin (46 eight-day bins/year, tile + month)
S7 Coverage  → avail, bin_day, bin_coverage
S8 Calibrate → calib_factor, calib_boot (bootstrap uncertainty)
S9 Harmonize → cell_bin_h
   → AOI aggregation → baseline → anomaly → critical period → API
```

S9 source logic: full MODIS coverage → `MODIS`; single MODIS satellite with a
bridge factor → `BRIDGE`; VIIRS with calibration → `VIIRS_CAL`; none → `NONE`.

Each stage's inputs, outputs, parameters, and algorithm are specified in
`docs/TRD.md` §4–5; the diagram above is the architectural view only.

---

## 6. Component interfaces and contracts

| Producer | Consumer | Contract |
|----------|----------|----------|
| Ingest | Data Cache | Parquet files under `cache/raw/`; a per-source manifest with sha256 |
| Data Cache | API | Read-only DuckDB access over Parquet |
| API | Frontend | JSON over `/api/v1/*`; `params_hash` in body and header |
| Frontend | Service Worker | Cache API; versioned caches |
| Ingest | Manifest | Every raw file registered with sha256 |

The JSON boundary is the only cross-component contract. Request and response
bodies are defined in `docs/TRD.md` §6.

**Request lifecycle (series query):** the frontend posts an AOI to
`/api/v1/series`. The API validates the geometry, resolves preset cells or
polygon coverage, runs a read-only DuckDB query over the harmonized
detections, attaches `params_hash` and bootstrap bands, and returns JSON. The
service worker serves the response stale-while-revalidate and caches it.
Analysis endpoints also accept `POST` because AOI geometries can be large; the
optional body carries `aoi`, `date`, and `bbox`, which take precedence over the
query parameters.

---

## 7. Data source, startup, and runtime state

At startup the app chooses one source and labels it everywhere:

| Source | When | Badge |
|--------|------|-------|
| `api` | A reachable API is configured | `live` / `cache` |
| `mock` | Development / design work | `mock` |
| `fixture` | API has no cache and no key, or `OFFLINE=1` | `fixture` |

Selection order: explicit override → reachable API → mock. The chosen source is
reported by the API's `meta.source` and shown in the source badge and provenance
drawer. Mock/fixture data is never presented as evidence.

```
1. Load app shell (rail, mode control, empty panels)
2. GET /meta                     -> extent, years, streams, params_hash
3. Apply defaults (region, metric=density, view=harmonized)
4. POST /api/v1/series           -> hero chart + calendar
5. Idle requests: /api/v1/aoi    -> preset list
6. Register service worker       -> precache shell (offline-ready)
```

Steps 4–5 degrade independently: a failed series request shows an error state
without blocking the shell. The headline chart is served in `metric=density`
(the startup default); any other metric is `cell_days`.

Runtime state lives in the URL hash, so any view is deep-linkable and the back
button works:

| State | Values | Persistence |
|-------|--------|-------------|
| `view` | overview, calendar, map, anomalies, critical, validation, methods, offline | URL hash |
| `mode` | raw, harmonized | URL hash |
| `aoi` | preset id or GeoJSON polygon | URL |
| `date` | selected date/bin | URL |
| `theme` | dark (default), light | local storage |

---

## 8. Storage layout and lifecycle

```
cache/                     # git-ignored: the acquired data and its manifests
  raw/                     # S0 output, never modified
    MODIS_SP.parquet
    VIIRS_SNPP_SP.parquet
    VIIRS_NOAA20_SP.parquet
    VIIRS_NOAA21_NRT.parquet
    <source>.manifest.json # per-source manifest (files, rows, sha256)
  burned_area/             # E8 external validation
    raw/, derived.parquet
demo_fixtures/
  detections.parquet       # the committed offline demo detections
config/
  params.yaml              # every tunable value
```

The API reads `cache/raw/*.parquet` (or `demo_fixtures/detections.parquet`)
and harmonizes in memory; there is no separate `derived/` tree on disk, and
no `meta/` directory — `params_hash` is derived from the bytes of
`config/params.yaml` at request time (`src/compute/params.py`).

Lifecycle: `cache/raw/` is append-only and checksummed; the served series is
fully rebuildable from it plus `config/params.yaml`; any change to the
parameter hash invalidates downstream artifacts.

---

## 9. Deployment topology

- **A source checkout**, run directly: the API from `src.api.main`, the frontend from `web/dist/` or the Vite dev server.
- **Targets:** laptop (field use), Raspberry Pi (local server), cloud VM (shared access).
- **Field mode:** the "server" is local on the laptop; no internet needed once the cache is built.
- **Build:** `make venv` for the Python environment, `npm run build` in `web/` for the frontend.
- **Config:** `FIRMS_MAP_KEY` (acquisition only), `OFFLINE`, and `VITE_DATA`/`VITE_API_BASE` for the frontend build.

The runbook (install, run, smoke test) is `docs/DEPLOYMENT.md`.

---

## 10. Offline architecture and degradation

Two layers, both implemented:

1. **Service Worker** (`web/public/sw.js`): precaches the app shell (`/`, `/index.html`, `/landing.html`), keeps a versioned shell cache and a versioned data cache, and serves the shell from cache when the network is gone.
2. **Resource report** (`web/src/lib/sw.ts`): on load, the page tells the worker which resources it used — the hashed assets and the nine mock payloads — so the worker caches them itself rather than waiting for a fetch event it may never see.

The basemap is a set of NASA Earth images under `web/public/earth/`, not
PMTiles; there is no in-browser DuckDB-WASM or IndexedDB/OPFS layer. The
offline screen reports the worker's cache state (cache name, entry count, size)
read from the Cache API — there is no download manager (FR-19, PRD §6).

Degradation path: if the API is unreachable, the app falls back to the cached
payloads the service worker holds. The backend is local in every deployment
model, so there is no remote service to fall back from.

---

## 11. Failure modes and graceful degradation

| Failure | Behaviour |
|---------|-----------|
| Network down after the cache is built | Full app works offline from the service worker's caches. |
| API unreachable | The app shows the cached payloads; the error is reported per panel. |
| Insufficient overlap years | Calibration not applied; notice shown. |
| Sparse calibration tiles | Shrinkage to regional ratio; fall-back to regional-only. |
| Low coverage bin | Hatched, excluded from baselines, never shown as "no fire". |
| Service worker eviction | Versioned caches, re-primed by the next online visit. |
| Invalid AOI | HTTP 422 structured error (`{code, message, field}`); no computation performed. |
| AOI too large | HTTP 422 `aoi_too_large`, refused before any query runs. |
| Request over the timeout | HTTP 503 `timeout`. |

The per-screen loading / empty / error / offline / mock states are in
`docs/FLOWS.md`.

---

## 12. Security boundaries and trust assumptions

- **Trust boundary:** the API is the only network-exposed surface; it is read-only.
- The service reads the Parquet cache; nothing in the request path writes to it.
- All AOI input is validated before any query (a known preset id, or a bbox of four degrees with `west<east` and `south<north`, over at most `api.max_aoi_cells` grid cells).
- Request size limits and a 30 s timeout bound resource use.
- `FIRMS_MAP_KEY` is read from the environment only — never committed or logged.
- CORS allows the loopback dev (`:5174`) and preview (`:4173`) origins only; no wildcard.
- HTTPS is a deployment concern: terminate TLS in front of the API. The service itself speaks plain HTTP.
- **Assumption:** the local/field deployment is trusted; network-exposed deployments are assumed to sit behind TLS and network controls.

---

## 13. Scalability, determinism, and constraints

- **Scale:** columnar DuckDB on Parquet keeps queries fast without a server DB; pilot extent is 60–93°E, 5–36°N.
- **Hardware:** laptop-class, no GPUs.
- **Determinism:** same raw inputs + same `params_hash` ⇒ identical output bytes (sorted Parquet keys, fixed compression, seeded bootstrap, hash recorded on every artifact).
- **Bounded queries:** AOI cell cap and per-request timeout protect interactive latency.
- **Rebuild cost:** the derived cache is fully rebuildable from `cache/raw/` plus `config/params.yaml`; changing any parameter changes the hash and marks all downstream artifacts stale, which trades a bounded rebuild for guaranteed consistency.
- **Constraint:** `cache/raw/` is never modified after acquisition.

---

## 14. Architecture decision records

| # | Decision | Rationale |
|---|----------|-----------|
| ADR-1 | Pre-fetch before the event | The demo must run offline; NASA access is slow and fragile. |
| ADR-2 | DuckDB over Parquet | Fast columnar analytics without a DB server; reuses SQL in-browser. |
| ADR-3 | Read-only API | Removes mutation risk; keeps the science in the pipeline. |
| ADR-4 | Multiplicative calibration | Keeps values additive so arbitrary AOIs aggregate without recalibration. |
| ADR-5 | Explicit coverage + source tags | Prevents modelled or uncovered data from reading as observed zero. |
| ADR-6 | NASA Earth basemap images | Shipped with the app, so the map works with no network and no tile server. |
| ADR-7 | Deterministic code, no LLM | Claims must be reproducible, so every number is computed in the pipeline. |
| ADR-8 | Source checkout, no container image | The API is a local process over a local cache; there is nothing to image. |
| ADR-9 | 8-day bins (46/year) | Follows the MODIS composite convention; aligns with the reference record. |
| ADR-10 | `params.yaml` + hash | Makes every result reproducible and invalidates downstream outputs safely. |
