# Project Icarus — System Architecture

**Version:** 1.0 · **Date:** 05 October 2026 · **Status:** Baseline
**Related:** `docs/PRD.md`, `docs/TRD.md`, `docs/Icarus_Project_Build_Specification.docx`

---

## 1. Architecture Overview

Icarus is a four-layer system. All NASA data is acquired **before** the event (S0, network required). From then on the system is offline: the pipeline transforms cached raw data into harmonized Parquet, a single read-only FastAPI service answers DuckDB queries, and a static web app renders and caches results. An optional AI layer reads API JSON and narrates; it never computes.

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

---

## 2. Layer Responsibilities

| Layer | Responsibility | Network | Runtime |
|-------|----------------|---------|---------|
| Pre-fetch | Download and register raw files with checksums | Required (S0) | Pre-event batch |
| Data Cache | Store derived Parquet, calibration, tiles | None | Build-time artifact |
| FastAPI Service | Serve read-only analytics over DuckDB | Local/LAN | Long-running process |
| Static Web App | Map, calendar, panels, offline cache | Local/LAN, then offline | User session |
| Optional AI Layer | Retrieve and explain API output | Local/LAN | Optional process |

Layers are strictly ordered by runtime: the pipeline and cache exist before the event, the API and web app run during the session, and the AI layer is an optional observer on top. Each layer may only depend on the ones above it, which keeps the offline path intact when any optional layer is absent.

---

## 3. Component Specifications

| Component | Responsibilities | Must Not Do |
|-----------|------------------|-------------|
| **Pipeline** (`icarus.pipeline`) | Run S0–S9; write Parquet; write manifest and parameter hash; expose CLI entry points | Call external services at app runtime |
| **Core Library** (`icarus.core`) | Pure functions: grid, bins, coverage, calibration, climatology, anomaly, season | Perform I/O or depend on web frameworks |
| **API** (`icarus.api`) | FastAPI app; read-only; JSON responses; parameter-hash header | Mutate data or compute statistics |
| **Frontend** (`web/`) | MapLibre map; d3 calendar heatmap; polygon drawer; offline service worker | Call NASA APIs directly |
| **AI Agent** (optional) | MCP server exposing series, anomalies, critical-period tools; narrate from JSON | Compute statistics; fail loudly |

---

## 4. Data Flow Across Stages S0–S9

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
S9 Harmonize → cell_bin_h (h, source = MODIS|BRIDGE|VIIRS_CAL|NONE)
   → AOI aggregation → climatology → anomaly → critical period → API
```

S9 source logic: full MODIS coverage → `MODIS`; single MODIS satellite with bridge factor → `BRIDGE`; VIIRS with calibration → `VIIRS_CAL`; none → `NONE`.

---

## 5. Storage Layout and Lifecycle

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
    det/stream=*/year=*/part-*.parquet      # S1
    cell_day/year=*/part-*.parquet          # S5
    cell_bin/year=*/part-*.parquet          # S6
    avail.parquet, bin_coverage.parquet     # S7
    calib_factor.parquet, calib_boot.parquet # S8
    cell_bin_h/year=*/part-*.parquet        # S9
  tiles/
    basemap_<region>.pmtiles
  meta/
    params.yaml, params.hash, build_info.json
```

Lifecycle: `raw/` is append-only and checksummed; `derived/` is fully rebuildable from `raw/` + `config/params.yaml`; any change to the parameter hash invalidates downstream artifacts.

---

## 6. Deployment Topology

- **Single Docker image** containing API, frontend, and data cache. Optional volume mount for large data.
- **Targets:** laptop (field use), Raspberry Pi (local server), cloud VM (shared access).
- **Field mode:** the "server" is local on the laptop; no internet needed once data is cached.
- **Build:** created from a clean checkout; non-root container user.
- **Config:** `FIRMS_API_KEY` (S0 only), `PORT`, `DATA_DIR`, `LOG_LEVEL`, `DUCKDB_MEMORY`.

---

## 7. Offline Architecture and Degradation

Five layers:

1. **Service Worker (Workbox):** precache app shell; serve tiles cache-first; stale-while-revalidate for data.
2. **PMTiles basemap:** one file per region replaces thousands of tile requests; MapLibre reads PMTiles directly.
3. **DuckDB-WASM:** query GeoParquet in-browser; read COGs via range requests; load zarr chunks client-side.
4. **IndexedDB / OPFS:** hold large data; request persistent storage via `navigator.storage.persist()`.
5. **Download for Offline screen:** user picks area/layers; size estimate and progress; per-layer "data last updated" timestamp.

Degradation path: if the FastAPI server is unreachable → the backend is local (Docker on laptop/Raspberry Pi). If the AI layer is unavailable → it is hidden. User actions queue via Background Sync until connectivity returns.

---

## 8. Component Interfaces & Contracts

| Producer | Consumer | Contract |
|----------|----------|----------|
| Pipeline | Data Cache | Parquet files keyed by year/stream; `meta/params.hash` |
| Data Cache | API | Read-only DuckDB access over Parquet |
| API | Frontend | JSON over `/api/v1/*`; `params_hash` in body and header |
| API | AI Agent (MCP) | JSON tools: series, anomalies, critical-period |
| Frontend | Service Worker | Cache API + OPFS; versioned caches |
| S0 | Manifest | Every raw file registered with sha256 |

The JSON boundary is the only cross-component contract; the AI layer consumes exactly what the frontend consumes.

**Request lifecycle (series query):** the frontend posts an AOI to `/api/v1/series`. The API validates the geometry, resolves preset cells or polygon coverage, runs a read-only DuckDB query over `cell_bin_h`, attaches `params_hash` and bootstrap bands, and returns JSON. The service worker serves the response stale-while-revalidate and caches it; the AI layer, if enabled, may then read the same JSON to narrate — it never issues its own query. This ordering guarantees the map, the panels, and any narration are derived from one identical payload.

---

## 9. Failure Modes and Graceful Degradation

| Failure | Behaviour |
|---------|-----------|
| Network down after S0 | Full app works offline from cache. |
| API unreachable | Local Docker backend serves; if none, cached data is used; actions queue via Background Sync. |
| AI layer unavailable | Layer hidden; core app unaffected. |
| Insufficient overlap years | Calibration not applied; notice shown; H2 untestable. |
| Sparse calibration tiles | Shrinkage to regional ratio; fall-back to regional-only. |
| Low coverage bin | Hatched, excluded from baselines, never shown as "no fire". |
| Service worker eviction | `navigator.storage.persist()`; versioned caches; OPFS fallback. |
| Invalid AOI | HTTP 422 structured error; no computation performed. |

---

## 10. Security Boundaries and Trust Assumptions

- **Trust boundary:** the API is the only network-exposed surface; it is read-only.
- Data mount is read-only; the service cannot mutate source data.
- All AOI input is validated before any query (closed ring, ≥ 4 positions, within extent, no self-intersection, ≤ 100,000 cells).
- Request size limits and 30 s timeout bound resource use.
- `FIRMS_API_KEY` is read from the environment only — never committed, baked into images, or logged.
- Logs record path, duration, status; user AOI geometries are not logged.
- HTTPS with HSTS for any network communication.
- **Assumption:** the local/field deployment is trusted; network-exposed deployments are assumed to sit behind TLS and network controls.

---

## 11. Scalability, Determinism, and Resource Constraints

- **Scale:** columnar DuckDB on Parquet keeps queries fast without a server DB; pilot extent is 60–93°E, 5–36°N.
- **Hardware:** laptop-class, no GPUs.
- **Determinism:** sorted Parquet keys, fixed compression, seeded bootstrap, parameter hash on every artifact → identical inputs produce identical output bytes.
- **Bounded queries:** AOI cell cap and per-request timeout protect interactive latency.
- **Portability:** the same SQL runs in DuckDB (server) and DuckDB-WASM (browser) where feasible.
- **Rebuild cost:** the derived cache is fully rebuildable from `raw/` plus `config/params.yaml`; changing any parameter changes the hash and marks all downstream artifacts stale, which trades a bounded rebuild for guaranteed consistency.

---

## 12. Key Architecture Decisions and Rationale

| Decision | Rationale |
|----------|-----------|
| Four layers, pre-fetch before event | Demo must run offline; NASA access is fragile and slow (R1). |
| DuckDB over Parquet | Fast columnar analytics without a DB server; reuses SQL in-browser. |
| Read-only API | Removes a class of mutation and security risks; keeps the science in the pipeline. |
| Multiplicative calibration | Keeps values additive so arbitrary AOIs aggregate without recalibration. |
| Explicit coverage + source tags | Prevents modelled or uncovered data from being read as observed zero. |
| PMTiles basemap | One file per region enables true offline maps. |
| Deterministic code, optional LLM | Scientific claims must be reproducible; the LLM only narrates. |
| Single Docker image | Simplest deployable unit for laptop, Pi, and VM targets. |
