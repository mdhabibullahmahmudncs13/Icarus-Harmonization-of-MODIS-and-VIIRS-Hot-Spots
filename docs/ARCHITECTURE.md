# Architecture

How the system is structured to be built. `docs/SYSTEM_ARCHITECTURE.md` is the
high-level baseline; this document is the builder's view — module map, data flow,
sequence, and decision records. Design basis:
`docs/Icarus_Project_Build_Specification.docx`.

---

## 1. Shape of the system

Four layers, strictly ordered by runtime:

```
[NASA Sources]  FIRMS Archive / UMD SFTP / MCD64CMQ / LAADS DAAC
        │  (S0: pre-event, network required)
        ▼
[Pre-fetch]     data/raw/**  +  manifest.csv (sha256, rows, dates)
        │  (S1–S9: offline batch, Python + DuckDB)
        ▼
[Data Cache]    data/derived/*.parquet, data/calib/*.parquet, data/tiles/*.pmtiles
        │
        ▼
[FastAPI]       read-only; DuckDB queries; /api/v1/*
        │  HTTP (localhost or LAN)
        ▼
[Static Web App]  MapLibre + d3 calendar + service worker + OPFS
        │
        ▼
[Optional AI]   reads API JSON, narrates; hidden if unavailable
```

Rule: a layer may depend only on the layers above it. This keeps the offline
path intact when any optional layer is absent.

---

## 2. Module map

```
src/
  core/          # pure, tested, no I/O
    grid.py         floor(lon·K), floor(lat·K), cell_centre, area_weight
    bins.py         day-of-year -> bin (46/year)
    coverage.py     availability, family and joint coverage
    calib.py        multiplicative factors + bootstrap
    anomaly.py      baseline, z-score, percentile rank, flags
    season.py       critical-period onset/peak/end/window
  pipeline/      # I/O orchestration
    s0_acquire.py ... s9_harmonize.py, cli.py
  api/           # read-only serving
    main.py, models.py, aoi.py, queries.py
  sql/           # .sql shared by API and (stretch) browser
web/
  src/  public/  sw/  tests/
tests/
  unit/  property/  golden/  e2e/
config/
  params.yaml
```

`core/` is pure: values in, values out. All I/O and framework use live in
`pipeline/` and `api/`.

---

## 3. Component specifications

| Component | Responsibilities | Must not do |
|-----------|------------------|-------------|
| Pipeline | Run S0–S9; write Parquet; write manifest and parameter hash; CLI | Call external services at app runtime |
| Core Library | Pure functions: grid, bins, coverage, calibration, climatology, anomaly, season | Perform I/O or depend on web frameworks |
| API | FastAPI app; read-only; JSON; parameter-hash header | Mutate data or compute statistics |
| Frontend | MapLibre map; d3 calendar; polygon drawer; offline service worker | Call NASA APIs directly |
| AI Agent (optional) | MCP server exposing series, anomalies, critical-period tools; narrate from JSON | Compute statistics; fail loudly |

---

## 4. Data flow S0–S9

```
S0 Acquire    raw + manifest (sha256, rows, retrieved, url)
S1 Normalize  det.parquet (unified schema, stream bits)
S2 Filter     det_ok (quality rule per instrument)
S3 Mask       det_clean (static sources removed)
S4 Snap       cell indices
S5 Collapse   cell_day (stream_mask, n_det, max_frp)
S6 Bin        cell_bin (46 bins/year, tile + month)
S7 Coverage   avail, bin_day, bin_coverage
S8 Calibrate  calib_factor, calib_boot
S9 Harmonize  cell_bin_h (h, source)
   -> AOI aggregation -> climatology -> anomaly -> critical period -> API
```

Each stage: named inputs, named outputs, a parameter list, and a test.

---

## 5. Request sequence (series query)

```
Browser ──POST /api/v1/series──► API
  API ──validate AOI──────────────► (reject -> 422 {code,message,field})
  API ──DuckDB read (read-only)──► cell_bin_h
  API ──attach params_hash + bands─► JSON
Browser ◄──200 JSON────────────── API
  Service Worker: stale-while-revalidate cache
  AI layer (optional): reads the same JSON to narrate; no separate query
```

The map, the panels, and any narration are derived from one identical payload.

---

## 6. Storage layout

```
data/
  raw/        # S0 output, never modified (append-only, checksummed)
  manifest.csv
  reference/  # outages.csv, streams.csv, regions.parquet
  derived/    # det, cell_day, cell_bin, avail, bin_coverage,
              # calib_factor, calib_boot, cell_bin_h (Parquet)
  tiles/      # basemap_<region>.pmtiles
  meta/       # params.yaml, params.hash, build_info.json
```

`derived/` is fully rebuildable from `raw/` + `config/params.yaml`.

---

## 7. Offline architecture

1. Service Worker (Workbox): precache shell; tiles cache-first; data
   stale-while-revalidate.
2. PMTiles basemap: one file per region.
3. DuckDB-WASM: query GeoParquet in-browser; COG range requests; zarr chunks.
4. IndexedDB / OPFS: large data; `navigator.storage.persist()`.
5. Download-for-offline screen: area/layer picker, size estimate, per-layer
   timestamps.

Degradation: API unreachable → local Docker backend; AI unavailable → hidden;
actions queue via Background Sync.

---

## 8. Failure modes

| Failure | Behaviour |
|---------|-----------|
| Network down after S0 | Full app works offline from cache |
| API unreachable | Local Docker backend; cached data; queued actions |
| AI unavailable | Hidden; core unaffected |
| < 5 overlap years | Calibration not applied; notice shown |
| Sparse calibration tiles | Shrinkage to regional ratio; regional fall-back |
| Low coverage bin | Hatched, excluded from baselines, never "no fire" |
| Service worker eviction | `persist()`, versioned caches, OPFS fallback |
| Invalid AOI | 422 structured error; no computation |

---

## 9. Architecture decision records

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

---

## 10. Constraints

- Laptop-class hardware, no GPUs.
- Pilot extent 60–93°E, 5–36°N (South Asia).
- One Docker image; read-only data mount.
- `data/raw/` is never modified after acquisition.
- Determinism: identical inputs + identical hash ⇒ identical output bytes.
