# Application Flow

How the app behaves at runtime: how it picks a data source, how a request moves
through the system, how the pipeline feeds it, and how it degrades. Structure
lives in `docs/ARCHITECTURE.md`; screens in `docs/ScreenFlow.md`.

---

## 1. Runtime layers

```
[Pipeline S0-S9]  ->  [Data Cache]  ->  [FastAPI /api/v1]  ->  [Web App]
   offline batch        parquet         read-only, DuckDB      MapLibre + d3
```

The web app never calls NASA. The API never mutates data or computes statistics.
The pipeline is the only writer.

---

## 2. Data-source selection

At startup the app chooses one source and labels it everywhere:

| Source | When | Badge |
|--------|------|-------|
| `api` | A reachable API is configured | `live` / `cache` |
| `mock` | Development / design work | `mock` |
| `fixture` | API has no cache and no key, or `OFFLINE=1` | `fixture` |

Selection order: explicit override → reachable API → mock. The chosen source is
reported by the API's `meta.source` and shown in the source badge and provenance
drawer. Mock/fixture data is never presented as evidence.

---

## 3. Startup sequence

```
1. Load app shell (rail, mode control, empty panels)
2. GET /meta                     -> extent, years, streams, params_hash
3. Apply defaults (region, metric=density, view=harmonized)
4. POST /api/v1/series           -> hero chart + calendar
5. Idle requests: /api/v1/aoi    -> preset list
6. Register service worker       -> precache shell (offline-ready)
```

Steps 4–5 degrade independently: a failed series request shows an error state
without blocking the shell.

---

## 4. Request lifecycle (series)

```
Browser ──POST /api/v1/series {aoi, metric, view}──► API
  API ──validate AOI─────────────────────────────────► 422 {code,message,field}
  API ──read DuckDB (read-only)──► cell_bin_h
  API ──attach params_hash + bootstrap bands──────────► JSON
Browser ◄──200 JSON─────────────────────────────────  API
  Service Worker: stale-while-revalidate
  Calendar derived client-side from the same bins
```

- Analysis endpoints are **POST** because AOI geometries can be large.
- Every response carries `params_hash`; the API also sets it as a header.
- The calendar, map, and any AI narration read the same payload — one source of
  truth per view.

---

## 5. Harmonization pipeline flow (feeding the app)

```
S0 Acquire    raw + manifest (sha256)
S1 Normalize  det
S2 Filter     det_ok
S3 Mask       det_clean
S4 Snap       cell indices
S5 Collapse   cell_day
S6 Bin        cell_bin (46 bins/year)
S7 Coverage   avail, bin_coverage
S8 Calibrate  calib_factor, calib_boot
S9 Harmonize  cell_bin_h (h, source)
```

The API reads `cell_bin_h` and coverage tables; it never re-runs a stage. A
change to `config/params.yaml` changes the hash and marks derived data stale.

---

## 6. State model

| State | Values | Persistence |
|-------|--------|-------------|
| `view` | overview, calendar, map, anomalies, critical, validation, methods, offline | URL hash |
| `mode` | raw, harmonized | URL hash |
| `aoi` | preset id or GeoJSON polygon | URL |
| `date` | selected date/bin | URL |
| `theme` | dark (default), light | local storage |

State changes update the hash; the app can be reopened from a deep link.

---

## 7. Error and degradation flow

| Condition | Behaviour |
|-----------|-----------|
| API unreachable | Serve from cache; queue actions via Background Sync; show offline badge |
| Invalid AOI | 422 with `{code, message, field}`; highlight the offending field |
| No data for extent | Empty state naming the missing stream/period |
| Low coverage bin | Hatched, excluded from baselines, never "no fire" |
| Insufficient overlap years | Calibration not applied; notice shown |
| AI layer unavailable | Hidden; core app unaffected |
| Service worker evicted | Re-fetch online; versioned caches; OPFS fallback |

---

## 8. Offline flow

```
Online (prime)
  Download-for-offline -> size estimate -> cache shell + tiles + data
    -> Service Worker (Workbox) + IndexedDB/OPFS
Offline (use)
  cold start -> shell from SW -> data from cache -> same UI, offline badge
  any mutation/query queued (Background Sync) until reconnect
```

PMTiles hold the basemap in one file per region; DuckDB-WASM can query
GeoParquet in-browser where bundling allows.

---

## 9. Determinism contract

- Same raw inputs + same `params_hash` ⇒ identical API output.
- Percentiles, correlations, and baselines are computed server-side only.
- The frontend displays numbers and never computes statistics.

---

## 10. AI layer (optional)

The MCP AI layer reads the same JSON the frontend receives and narrates it. It
cannot compute, cannot query independently, and is hidden if unavailable. Every
number it states must already appear in the API payload.
