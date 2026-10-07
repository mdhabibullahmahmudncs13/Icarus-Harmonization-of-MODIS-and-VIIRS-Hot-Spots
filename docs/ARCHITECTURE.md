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
An optional AI layer reads API JSON and narrates; it never computes.

```
[NASA Sources]  FIRMS Archive / UMD SFTP / MCD64CMQ / LAADS DAAC
        │  (S0: pre-event, network required)
        ▼
[Pre-fetch Layer]  data/raw/**  +  manifest.csv (sha256, rows, dates)
        │  (S1–S9: offline batch, Python + DuckDB)
        ▼
[Data Cache]  data/derived/*.parquet, data/calib/*.parquet, data/tiles/*.pmtiles
        │
        ▼
[FastAPI Service]  read-only; DuckDB queries; /api/v1/*
        │  HTTP (localhost or LAN)
        ▼
[Static Web App]  MapLibre + d3 calendar + service worker + OPFS cache
        │
        ▼
[Optional AI Layer]  reads API JSON, narrates; hidden if unavailable
```

Rule: a layer may depend only on the layers above it, which keeps the offline
path intact when any optional layer is absent.

---

## 2. Layer responsibilities

| Layer | Responsibility | Network | Runtime |
|-------|----------------|---------|---------|
| Pre-fetch | Download and register raw files with checksums | Required (S0) | Pre-event batch |
| Data Cache | Store derived Parquet, calibration, tiles | None | Build-time artifact |
| FastAPI Service | Serve read-only analytics over DuckDB | Local/LAN | Long-running process |
| Static Web App | Map, calendar, panels, offline cache | Local/LAN, then offline | User session |
| Optional AI Layer | Retrieve and explain API output | Local/LAN | Optional process |

Layers are strictly ordered by runtime: the pipeline and cache exist before the
event, the API and web app run during the session, and the AI layer is an
optional observer on top.

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
    grid.py         cell snapping and cell-day collapse
    harmonize.py    harmonization facade (grid, series, calibration)
    series_util.py  8-day bin rule
    availability.py stream epochs and outage calendar
    coverage.py     per-bin coverage and source tagging
    calibrate.py    multiplicative calibration + bootstrap
    baseline.py     day-of-year percentiles
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
tools/           # gen_mock.py, gen_golden.py, experiments.py
tests/           # unit, property, golden, contract
web/             # React app (src/, public/, tests/, e2e/)
landing/         # static landing page
config/params.yaml   # every tunable value
data/            # git-ignored: raw/ + derived/ + reference/
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
| Frontend (`web/`) | MapLibre map; d3 calendar; polygon drawer; offline service worker | Call NASA APIs directly |
| AI Agent (optional) | MCP server exposing series, anomalies, critical-period tools; narrate from JSON | Compute statistics; fail loudly |

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
| Ingest | Data Cache | Parquet files keyed by year/stream; `meta/params.hash` |
| Data Cache | API | Read-only DuckDB access over Parquet |
| API | Frontend | JSON over `/api/v1/*`; `params_hash` in body and header |
| API | AI Agent (MCP) | JSON tools: series, anomalies, critical-period |
| Frontend | Service Worker | Cache API + OPFS; versioned caches |
| Ingest | Manifest | Every raw file registered with sha256 |

The JSON boundary is the only cross-component contract; the AI layer consumes
exactly what the frontend consumes. Request and response bodies are defined in
`docs/TRD.md` §6.

**Request lifecycle (series query):** the frontend posts an AOI to
`/api/v1/series`. The API validates the geometry, resolves preset cells or
polygon coverage, runs a read-only DuckDB query over `cell_bin_h`, attaches
`params_hash` and bootstrap bands, and returns JSON. The service worker serves
the response stale-while-revalidate and caches it. The AI layer, if enabled,
reads the same JSON to narrate — it never issues its own query. Analysis
endpoints also accept `POST` because AOI geometries can be large; the optional
body carries `aoi`, `date`, and `bbox`, which take precedence over the query
parameters.

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
data/
  raw/                    # S0 output, never modified
    modis/MCD14ML.YYYYMM.*.txt.gz
    viirs_snpp/*.csv
    mcd64cmq/*.hdf
  manifest.csv            # file, bytes, sha256, rows, retrieved, url
  reference/
    outages.csv           # stream, start, end, reason
    streams.csv           # stream, bit, first_date, last_date
    regions.parquet       # preset AOIs (GeoParquet)
  derived/
    det/stream=*/year=*/part-*.parquet       # S1
    cell_day/year=*/part-*.parquet           # S5
    cell_bin/year=*/part-*.parquet           # S6
    avail.parquet, bin_coverage.parquet      # S7
    calib_factor.parquet, calib_boot.parquet # S8
    cell_bin_h/year=*/part-*.parquet         # S9
  tiles/
    basemap_<region>.pmtiles
  meta/
    params.yaml, params.hash, build_info.json
```

Lifecycle: `raw/` is append-only and checksummed; `derived/` is fully
rebuildable from `raw/` + `config/params.yaml`; any change to the parameter hash
invalidates downstream artifacts.

---

## 9. Deployment topology

- **Single Docker image** containing API, frontend, and data cache. Optional volume mount for large data.
- **Targets:** laptop (field use), Raspberry Pi (local server), cloud VM (shared access).
- **Field mode:** the "server" is local on the laptop; no internet needed once data is cached.
- **Build:** created from a clean checkout; non-root container user.
- **Config:** `FIRMS_API_KEY` (S0 only), `PORT`, `DATA_DIR`, `LOG_LEVEL`, `DUCKDB_MEMORY`.

The runbook (build, deploy, smoke test) is `docs/DEPLOYMENT.md`.

---

## 10. Offline architecture and degradation

Five layers:

1. **Service Worker (Workbox):** precache app shell; serve tiles cache-first; stale-while-revalidate for data.
2. **PMTiles basemap:** one file per region replaces thousands of tile requests; MapLibre reads PMTiles directly.
3. **DuckDB-WASM:** query GeoParquet in-browser; read COGs via range requests; load zarr chunks client-side.
4. **IndexedDB / OPFS:** hold large data; request persistent storage via `navigator.storage.persist()`.
5. **Download for Offline screen:** user picks area/layers; size estimate and progress; per-layer "data last updated" timestamp.

Degradation path: if the FastAPI server is unreachable → the backend is local
(Docker on laptop/Raspberry Pi). If the AI layer is unavailable → it is hidden.
User actions queue via Background Sync until connectivity returns.

---

## 11. Failure modes and graceful degradation

| Failure | Behaviour |
|---------|-----------|
| Network down after S0 | Full app works offline from cache. |
| API unreachable | Local Docker backend serves; if none, cached data is used; actions queue via Background Sync. |
| AI layer unavailable | Layer hidden; core app unaffected. |
| Insufficient overlap years | Calibration not applied; notice shown. |
| Sparse calibration tiles | Shrinkage to regional ratio; fall-back to regional-only. |
| Low coverage bin | Hatched, excluded from baselines, never shown as "no fire". |
| Service worker eviction | `navigator.storage.persist()`; versioned caches; OPFS fallback. |
| Invalid AOI | HTTP 422 structured error (`{code, message, field}`); no computation performed. |

The per-screen loading / empty / error / offline / mock states are in
`docs/FLOWS.md`.

---

## 12. Security boundaries and trust assumptions

- **Trust boundary:** the API is the only network-exposed surface; it is read-only.
- Data mount is read-only; the service cannot mutate source data.
- All AOI input is validated before any query (closed ring, ≥ 4 positions, within extent, no self-intersection, ≤ 100,000 cells).
- Request size limits and a 30 s timeout bound resource use.
- `FIRMS_API_KEY` is read from the environment only — never committed, baked into images, or logged.
- Logs record path, duration, status; user AOI geometries are not logged.
- HTTPS with HSTS for any network communication.
- **Assumption:** the local/field deployment is trusted; network-exposed deployments are assumed to sit behind TLS and network controls.

---

## 13. Scalability, determinism, and constraints

- **Scale:** columnar DuckDB on Parquet keeps queries fast without a server DB; pilot extent is 60–93°E, 5–36°N.
- **Hardware:** laptop-class, no GPUs.
- **Determinism:** same raw inputs + same `params_hash` ⇒ identical output bytes (sorted Parquet keys, fixed compression, seeded bootstrap, hash recorded on every artifact).
- **Bounded queries:** AOI cell cap and per-request timeout protect interactive latency.
- **Portability:** the same SQL runs in DuckDB (server) and DuckDB-WASM (browser) where feasible.
- **Rebuild cost:** the derived cache is fully rebuildable from `raw/` plus `config/params.yaml`; changing any parameter changes the hash and marks all downstream artifacts stale, which trades a bounded rebuild for guaranteed consistency.
- **Constraint:** `data/raw/` is never modified after acquisition.

---

## 14. Architecture decision records

| # | Decision | Rationale |
|---|----------|-----------|
| ADR-1 | Pre-fetch before the event | The demo must run offline; NASA access is slow and fragile. |
| ADR-2 | DuckDB over Parquet | Fast columnar analytics without a DB server; reuses SQL in-browser. |
| ADR-3 | Read-only API | Removes mutation risk; keeps the science in the pipeline. |
| ADR-4 | Multiplicative calibration | Keeps values additive so arbitrary AOIs aggregate without recalibration. |
| ADR-5 | Explicit coverage + source tags | Prevents modelled or uncovered data from reading as observed zero. |
| ADR-6 | PMTiles basemap | One file per region enables true offline maps. |
| ADR-7 | Deterministic code; optional LLM | Claims must be reproducible; the LLM only narrates. |
| ADR-8 | Single Docker image | Simplest unit for laptop, Pi, and VM targets. |
| ADR-9 | 8-day bins (46/year) | Follows the MODIS composite convention; aligns with the reference record. |
| ADR-10 | `params.yaml` + hash | Makes every result reproducible and invalidates downstream outputs safely. |
