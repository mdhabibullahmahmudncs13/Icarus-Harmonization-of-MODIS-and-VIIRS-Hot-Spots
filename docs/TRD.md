# Project Icarus — Technical Requirements Document (TRD)

**Version:** 1.0 · **Date:** 05 October 2026 · **Status:** Baseline for implementation
**Related:** `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/Icarus_Project_Build_Specification.docx`

---

## 1. Overview & Traceability

This TRD specifies the engineering requirements for the deterministic harmonization pipeline, the read-only API, and the offline-capable frontend.

| PRD goal | TRD sections |
|----------|--------------|
| G1 reproducible ingestion | §3, §4, §8 |
| G2 remove VIIRS step change | §4 (S5, S8), §5 |
| G3 quantify cross-sensor offset | §4 (S8), §5 |
| G4 separate activity/anomaly/coverage | §4 (S7), §6, §7 |
| G5 validate against truth | §9 |
| G6 offline operation | §7 |

---

## 2. Technology Stack

| Area | Choice | Version / note |
|------|--------|----------------|
| Backend language | Python | 3.11+ |
| Analytical engine | DuckDB | Embedded, over Parquet |
| API framework | FastAPI | OpenAPI docs, type-safe |
| Storage format | Parquet | Sorted keys, fixed compression (determinism) |
| Frontend | React + TypeScript + Vite | Bundled locally, no CDN |
| Map | three.js on a NASA Earth texture | No tile server, so the map works offline |
| Calendar / charts | d3-array + d3-scale, hand-drawn SVG | 46-bin calendar |
| Offline cache | Hand-rolled service worker + Cache API | Cache-first assets, stale-while-revalidate data |
| Basemap | NASA Earth images | Shipped under `web/public/earth/` |
| Deployment | Source checkout | API from `src.api.main`; frontend is a static build |

Exact dependency pin versions live in `web/package.json` and the `DEPS` list
in the `Makefile`; both are pinned.

---

## 3. Data Model & Schemas

### 3.1 Normalized Detection Schema (post-S1)

| Field | Type | Description |
|-------|------|-------------|
| acq_date | DATE | Acquisition date (UTC) |
| acq_time | TIME | Acquisition time (UTC) HH:MM |
| lon | FLOAT | Longitude [−180, 180) |
| lat | FLOAT | Latitude [−90, 90] |
| frp | FLOAT | Fire Radiative Power (MW); VIIRS may be null |
| conf_num | SMALLINT | MODIS confidence 0–100 |
| conf_class | VARCHAR(1) | VIIRS class: l / n / h |
| hs_type | SMALLINT | MODIS type (0 = fire, 2 = persistent, 3 = urban) |
| instrument | ENUM | MODIS or VIIRS |
| sat | ENUM | Terra (T), Aqua (A), S-NPP, N20, N21 |
| stream | ENUM | MOD_T, MOD_A, VIIRS_SNPP, VIIRS_N20, VIIRS_N21 |
| stream_bit | INT | 1, 2, 4, 8, 16 |

### 3.2 Stream Bit Definitions

| Stream | Bit | Role in default config |
|--------|-----|------------------------|
| MOD_T | 1 | MODIS reference family |
| MOD_A | 2 | MODIS reference family |
| VIIRS_SNPP | 4 | Primary VIIRS stream |
| VIIRS_N20 | 8 | Ingested, not used by default |
| VIIRS_N21 | 16 | Ingested, not used by default |

### 3.3 Core DuckDB Tables

| Table | Stage | Key columns |
|-------|-------|-------------|
| det | S1 | stream, instrument, sat, acq_date, acq_time, lon, lat, frp, conf_num, conf_class, hs_type, stream_bit |
| det_ok | S2 | det rows passing quality filter |
| det_clean | S3 | det_ok with static cells removed |
| cell_day | S4–S5 | cell_x, cell_y, d, stream_mask, n_det, max_frp |
| cell_bin | S6 | cell_x, cell_y, yr, bin, tx, ty, mon, ad_modis, ad_mod_t, ad_mod_a, ad_snpp |
| avail | S7 | stream, d, available (0/1) |
| bin_day | S7 | d, yr, bin, t_ok, a_ok, v_ok |
| bin_coverage | S7 | yr, bin, n_days, avail_t, avail_a, both_frac, cov_modis, cov_viirs |
| calib_factor | S8 | tx, ty, mon, m_sum, v_sum, r |
| calib_boot | S8 | draw, tx, ty, mon, r |
| cell_bin_h | S9 | cell_x, cell_y, yr, bin, mon, h, source |

---

## 4. Pipeline Specification (S0–S9)

Each stage is deterministic, idempotent, reads named inputs, writes named outputs, has a parameter list, and has a test.

| Stage | Input → Output | Parameters | Failure / fallback |
|-------|----------------|------------|--------------------|
| **S0 Acquire** | NASA sources → `cache/raw/**` + `<source>.manifest.json` | source URLs, pilot extent | Skip already-manifested (sha256) files; S0 runs pre-event with network. |
| **S1 Normalize** | raw → in-memory det (Parquet) | product-specific parsers, stream map | Unknown product version → recorded in manifest, parsing error surfaced. |
| **S2 Quality filter** | det → det_ok | c_min, modis_allowed_types, viirs_classes | c_min default 50. |
| **S3 Static mask** | det_ok → det_clean | fine_K, min_days | Removes cells with ≥ min_days distinct dates/year. Sensitive to repeated agri-burning (tested E4). |
| **S4 Grid snap** | det_clean → cell indices | cell_km, reference_latitude_deg | Floor semantics; boundary detections go to higher index. |
| **S5 Cell-day collapse** | det_clean → cell_day | (stream bits) | Idempotent; row-order invariant. |
| **S6 Temporal binning** | cell_day → cell_bin | bin_days=8 | bin(n) = min(⌊(n−1)/8⌋+1, 46). |
| **S7 Availability/coverage** | cell_bin + outages → avail, bin_day, bin_coverage | cov_min, zero_detection_rule | Low coverage excluded from baselines; never described as "no fire". |
| **S8 Calibration** | overlap bins → calib_factor, calib_boot | kappa, tile_deg, min_overlap_bins_per_year, min_overlap_years, bootstrap_B, bootstrap_seed | If < 5 overlap years, calibration field not applied; notice shown. |
| **S9 Harmonize** | cell_bin + coverage + calib → cell_bin_h | reference_family, viirs_primary | source = NONE when no stream meets coverage. |

---

## 5. Algorithms

### 5.1 Quality Filter (S2)

```
keep(MODIS) = [conf_num >= c_min] AND [hs_type = 0 OR hs_type IS NULL]
keep(VIIRS) = [conf_class IN {n, h}]
```
Default `c_min = 50`.

### 5.2 Static Mask (S3)

A fine grid of `fine_K = 200` cells/degree; a fine cell is masked for year y if it has ≥ `min_days = 16` distinct acquisition dates in that year.

### 5.3 Grid Snapping (S4)

Cells are `cell_km = 5.5` km wide. The latitude step is `cell_km / 111` degrees; the longitude step is that divided by `cos(reference_latitude_deg)`, so an east-west cell stays near the stated size at the region's representative latitude.

```
Δlat = cell_km / 111
Δlon = Δlat / cos(reference_latitude_deg)
cell_y = floor(lat / Δlat)
cell_x = floor(lon / Δlon)
area_weight w_c = cos(lat_c)
```

This is an approximation, not a geodesic: one reference latitude keeps the grid a clean partition, and cells shrink east-west away from it.

### 5.4 Temporal Binning (S6)

```
bin(n) = min(floor((n - 1) / 8) + 1, 46)     n = day of year 1–366
A_S(c, y, b) = Σ_{d ∈ bin} F_S(c, d)         range 0..days_in_bin
```

### 5.5 Coverage (S7)

```
a(s, d) ∈ {0,1}:   0 if outside active period, in outage table, or zero detections that day
cov_s(y, b) = (1/n_days) × Σ_d a(s, d)
cov_fam(y, b) = max over s in family of cov_s(y, b)
cov_min = 0.75 (6 of 8 days)
```

### 5.6 Multiplicative Calibration (S8)

```
r_reg(m) = Σ_t M(t, m) / Σ_t V(t, m)                    regional ratio
r(t, m)  = (M(t, m) + κ × r_reg(m)) / (V(t, m) + κ)     κ = 50
if V(t, m) = 0: r(t, m) = r_reg(m)
```
Strata = 1° × 1° tiles × calendar month. Multiplicative keeps sums additive so AOI values aggregate without recalibration.

### 5.7 Bridge Factors (single → dual MODIS)

```
q_s(t, m) = (Σ A_MODIS + κ × q_reg,s(m)) / (Σ A_s + κ)
```
Bridge-derived bins are tagged `BRIDGE` and outlined distinctly.

### 5.8 Anomaly (S9 post-processing)

```
X = ln(1 + 1000 × D)                                    scale = 1000
μ(b) = Σ_j w_j × mean(X over R(b + j))                  smoothing = (0.25, 0.5, 0.25)
σ(b) = sqrt(Σ_j w_j × var(X over R(b + j)))             j ∈ {−1, 0, +1}
z(y*, b) = (X(y*, b) − μ(b)) / max(σ(b), σ_floor)       σ_floor = 0.1
```
Reference set excludes the target year; minimum `min_reference = 8` values else no score. Flags: Elevated when `z ≥ 2.0 AND P ≥ 0.90`; Extreme when `z ≥ 3.0`.

### 5.9 Critical Fire Period

```
m(b) = mean over years of D(y, b) (non-low-coverage bins), smoothed as above
Q(b) = Σ_{j=1..b} m(j) / Σ_{j=1..46} m(j)
onset = smallest b with Q(b) ≥ 0.10
peak  = argmax m(b)
end   = smallest b with Q(b) ≥ 0.90
window = [onset − 1, end + 1] with mass ≥ 0.80
```
If mean density < `min_mean_density = 1e-5`, return "insufficient activity".

### 5.10 Parameter Registry (defaults)

| Parameter | Default | Meaning |
|-----------|---------|---------|
| cell_km | 5.5 | Grid cell size (km) |
| reference_latitude_deg | 23.5 | Latitude the east-west step is scaled for |
| c_min | 50 | Min MODIS confidence |
| viirs_classes | [n, h] | Allowed VIIRS classes |
| fine_K | 200 | Fine grid for static mask |
| min_days | 16 | Persistence threshold |
| bin_days | 8 | Temporal bin width |
| cov_min | 0.75 | Min coverage fraction |
| tile_deg | 1 | Calibration tile size |
| kappa | 50 | Calibration pseudo-count |
| min_overlap_bins_per_year | 30 | Min overlap bins for a year |
| min_overlap_years | 5 | Min overlap years for calibration |
| bootstrap_B | 200 | Bootstrap draws |
| bootstrap_seed | 20260101 | Bootstrap seed |
| sigma_floor | 0.1 | Min sigma for z-score |
| z_elevated / z_extreme | 2.0 / 3.0 | Anomaly thresholds |
| max_aoi_cells | 100000 | Max cells per AOI request |
| request_timeout_s | 30 | API per-request timeout |

All parameters live in `config/params.yaml`; the hash of that file is stored with every derived artifact.

`max_aoi_cells` and `request_timeout_s` are enforced by the API, not just
recorded: `src/api/main.py` reads both from the file at import, refuses an AOI
covering more cells than `max_aoi_cells` with `422 aoi_too_large` before any
query runs, and cuts a request that overruns `request_timeout_s` off with
`503 timeout`.

---

## 6. API Contract

Read-only, versioned under `/api/v1`, UTF-8 JSON. Analysis endpoints use POST (large geometries). Every response includes `params_hash`; every response includes a parameter-hash header for cache matching.

| Verb | Path | Purpose | Response fields |
|------|------|---------|-----------------|
| GET | `/health` | Liveness | status, build_id |
| GET | `/meta` | Extent, years, streams, param hash, last-updated | extent, years, streams, params_hash |
| POST | `/api/v1/series` | Time series for AOI | params_hash, aoi, metric, bins[] |
| POST | `/api/v1/anomalies` | Anomaly scores for AOI | params_hash, anomalies[] |
| POST | `/api/v1/critical-period` | Critical fire period | params_hash, onset_bin, peak_bin, end_bin, window |
| GET | `/api/v1/aoi` | List preset AOIs | id, name, geometry (GeoJSON) |
| GET | `/api/v1/export` | The filtered hotspot records, as CSV | `text/csv`: acq_date, acq_time, latitude, longitude, sensor_family, satellite, confidence_num, frp, cell_id, source_product |

### 6.1 AOI Object

```
Preset:  { "type": "preset",  "id": "BGD" }
Polygon: { "type": "geojson", "geometry": { "type": "Polygon", "coordinates": [[[lon,lat], ...]] } }
```

Validation: ring closed, ≥ 4 positions, within processing extent, no self-intersection, ≤ 100,000 cells. Invalid → HTTP 422 with `{ "code", "message", "field" }`.

### 6.2 Series Bins

```
{ "year": 2018, "bin": 7, "start": "2018-02-26", "end": "2018-03-05",
  "value": 0.0123, "lo": 0.0104, "hi": 0.0141,
  "coverage": 1.0, "source": "MODIS" }
```

`source ∈ {MODIS, BRIDGE, VIIRS_CAL, NONE}`. `lo`/`hi` are 5th/95th bootstrap percentiles when `include_uncertainty` is true.

### 6.3 Error Format

```
HTTP 422 { "code": "invalid_aoi", "message": "Polygon ring is not closed.",
           "field": "aoi.geometry.coordinates[0]" }
```

---

## 7. Frontend & Offline Mechanics

**Stack:** React + TypeScript + Vite; three.js globe on a NASA Earth texture; d3 calendar; all assets bundled locally.

**Screens:** Map panel (Earth basemap, AOI selection, layer toggles); calendar heatmap (rows = years, columns = 46 bins); anomaly panel; critical-period panel; provenance panel; offline manager.

**Visual encoding rules (requirements):**
- Activity and anomaly never share a palette in the same view.
- Low-coverage bins are hatched and labelled, never coloured as zero.
- Modelled bins carry a thin outline; tooltip states "modelled (VIIRS calibrated)" or "modelled (bridge)".
- Every chart shows units and bin length (8 days).

**Offline mechanism (2 layers, both implemented):**
1. Service worker (`web/public/sw.js`): precaches the app shell and the landing
   page; hashed assets cache-first; `/mock/` and `/api/` stale-while-revalidate.
   Caches are versioned, so a new worker drops the old ones.
2. Resource report (`web/src/lib/sw.ts`): on load the page tells the worker
   which resources it used — the hashed assets and the nine mock payloads — so
   they are cached without waiting for a fetch event that may never come.

The basemap is a set of NASA Earth images under `web/public/earth/`. There is
no DuckDB-WASM and no IndexedDB/OPFS layer; the offline screen reports the
service worker's cache state rather than downloading anything. The backend is
local in every deployment, so there is no remote service to fall back from.

**Degradation:** if the FastAPI server is unreachable, the app falls back to
the payloads the service worker holds, and the error is reported per panel.

---

## 8. Determinism & Reproducibility

- Parquet written with sorted keys and fixed compression.
- All randomness seeded (bootstrap seed 20260101).
- Staged outputs keyed by parameter hash of `config/params.yaml`.
- Requirement: identical raw inputs + identical parameter hash → byte-identical derived outputs (NFR-01 / AC-1).
- Build provenance: `params_hash` on every payload, plus the manifest beside each
  acquired file.

---

## 9. Testing Strategy

| Level | Coverage |
|-------|----------|
| Unit | Grid snapping at boundaries and negative coordinates; quality-filter edges (conf 29/30, classes l/n/h); bin formula for days 1, 8, 9, 365, 366; coverage with partial data; calibration with V = 0. |
| Property | Idempotence of S5; invariance to row order; duplicate rows do not change cell-day count. |
| Golden-file | Each stage output matches a pre-computed golden file for synthetic input. |
| End-to-end | Full pipeline on synthetic data; API responses match schema; offline frontend loads cached data. |

A synthetic data generator produces `det.parquet` matching §3.1 with configurable extent, years, streams, intensity distribution, seasonality, detection probability, and false-positive rate, including an injected step change at the VIIRS start year. Versioned fixtures include a ground-truth synthetic dataset and a small real-data excerpt.

---

## 10. Deployment & CI

- Source checkout, no container image: the API runs from `src.api.main` (uvicorn), the frontend is a static build served from `web/dist/`.
- Deployment targets: laptop (field), Raspberry Pi (local server), cloud VM (shared).
- CI on every push: lint + test (`make lint`, `make test`); trunk-based with short-lived branches.
- Environment variables: `FIRMS_MAP_KEY` (S0 only), `OFFLINE`, `FIRMS_PRODUCTS`, `FIRMS_BBOX`, `FIRMS_START`/`FIRMS_END` (S0 only), `EARTHDATA_TOKEN` (S0 only), `VITE_DATA`/`VITE_API_BASE` (frontend build). The API reads no other variable: the cache lives in `cache/`, the fixture in `demo_fixtures/`, and the port is a uvicorn command-line argument. See `docs/DEPLOYMENT.md`.

---

## 11. Security & Data Governance

- The API reads the Parquet cache and never writes to it.
- All inputs validated (AOI geometry, year ranges, cell count ≤ `api.max_aoi_cells` = 100,000).
- Request size limits and a 30 s per-request timeout (`api.request_timeout_s`).
- `FIRMS_MAP_KEY` read from the environment only; never committed or logged.
- Logs contain request path, duration, and status — not user AOI geometries.
- No hardcoded credentials; secrets are environment variables only.
- CORS allows the loopback dev (`:5174`) and preview (`:4173`) origins only — no wildcard.
- HTTPS is a deployment concern: terminate TLS in front of the API, which speaks plain HTTP.

---

## 12. Performance Budgets

| Budget | Target | Verified by |
|--------|--------|-------------|
| Offline cold-start load | Measured on laptop-class hardware | E9, Lighthouse PWA |
| API response time (series/anomalies) | Measured, reported | E9 |
| Service worker cache size | Measured, reported | E9 |

Numeric targets are **TBD — needs decision**; the requirement is that E9 measures and reports each against a stated baseline.

---

## 13. Open Technical Questions

- Whether calibration bootstrap bands are computed at request time or precomputed and cached.
- Minimum device RAM/storage supported by the offline demo.
- Whether bridge factors are computed for both MODIS satellites independently.
