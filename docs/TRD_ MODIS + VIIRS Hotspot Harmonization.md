# TRD: MODIS + VIIRS Hotspot Harmonization

**Companion to:** PRD_MODIS_VIIRS_Harmonization **Challenge:** NASA Space Apps 2026, Challenge 9 **License:** Apache-2.0 **Status:** Draft v1. Items marked **\[verify\]** depend on real FIRMS files or the 28 Oct full challenge statement.

---

## 1. Technical goals

1. Deterministic, tested harmonization code that turns MODIS (1 km) and VIIRS (375 m) detections into a series with no sensor-induced step change.
2. A demo that runs fully offline (`OFFLINE=1`) with identical output to the live path.
3. A strict boundary: all numbers come from `src/compute`. No LLM ever computes a statistic.
4. Every number shown in the UI traces to a dataset id, source URL, and a tool/compute result.

## 2. Architecture

```
Acquisition (pre-event)      Compute (deterministic)      API (FastAPI)        Frontend (static, offline)
FIRMS archives  ──► parquet ──► harmonize / validate ──► reads cache only ──► MapLibre + deck.gl
NASA POWER (P2) ──► parquet     baseline / anomaly        never calls NASA     D3 calendar, toggle
                                 precomputed JSON          source badge         service worker + PMTiles
                                        ▲
                         Agent layer (optional, P2): tools only, cite_check guard
```

**Layer rules**

- The frontend never calls NASA directly.
- The API never calls NASA during a demo. It reads `cache/` or `demo_fixtures/`.
- Acquisition runs before the event. Live responses are written to `cache/` with content-hash keys.
- The agent layer sits beside the API and reaches data only through tools. The app works without it.

## 3. Tech stack

| Area | Choice | Notes |
| --- | --- | --- |
| Language | Python 3.11+ |  |
| Data engine | DuckDB + pyarrow, pandas | SQL over parquet, no server |
| API | FastAPI + uvicorn | Read-only |
| Stats | numpy, scipy | Mann-Kendall implemented in-repo or via `pymannkendall` (P2) |
| Frontend | Vite + TypeScript | Built to static files in `web/` |
| Map | MapLibre GL, deck.gl | Basemap via PMTiles |
| Charts | D3 (calendar heatmap, line series) |  |
| Offline | Workbox service worker | Precache app shell; tiles cache-first; data stale-while-revalidate |
| Tests | pytest, hypothesis (optional) |  |
| Packaging | Docker image bundling API + cache | Runs on a laptop with no internet |
| Task runner | Makefile | `make cache`, `make demo`, `make test` |

## 4. Repository layout

```
LICENSE  README.md  CLAUDE.md  AGENTS.md  .env.example  Makefile
cache/            # gitignored, downloaded NASA data
demo_fixtures/    # committed, exact bytes the demo needs
docs/AI_USE.md
src/acquire/      # safe.py, firms.py, power.py
src/compute/      # harmonize.py, confidence.py, validate.py, baseline.py, trend.py
src/api/          # main.py, routes, schemas
src/agents/       # optional: loop.py, tools.json, cite_check.py
web/              # frontend source, built to web/dist
tests/
```

`.env.example` keys: `FIRMS_MAP_KEY`, `EDL_USER`, `NASA_API_KEY`, `ADS_API_TOKEN`. Commit only the example file.

## 5. Data specification

### 5.1 Inputs

| Source | Products | Used for |
| --- | --- | --- |
| FIRMS | MODIS (Terra, Aqua), VIIRS S-NPP, VIIRS NOAA-20, VIIRS NOAA-21 | Core series |
| NASA POWER | T2M, wind, humidity (daily, point) | Anomaly context (P2) |
| GIBS | Imagery tiles, packaged to PMTiles | Basemap |

**Acquisition rules**

- Use bulk archive CSVs for the long record. The area API is for recent data only (5,000 transactions per 10 min; one call is one transaction).
- Convert CSV to parquet on download. Partition by sensor and year: `cache/firms/{sensor}/{year}.parquet`.
- Region bounding box: Bangladesh `88,20,93,27` (west, south, east, north). South Asia is a stretch region. **\[decide before first pull\]**
- **Suomi-NPP archive must be pulled before 1 Nov 2026.** After that NASA stops serving it, and the early VIIRS years and the MODIS overlap likely depend on it.
- Record each platform's actual availability window from the files themselves, not from assumptions **\[verify\]**.

### 5.2 Normalized schema (`detections` view)

Columns differ between MODIS and VIIRS files **\[verify against downloaded files\]**. Normalize on load:

| Column | Type | Notes |
| --- | --- | --- |
| `sensor_family` | enum | `MODIS` or `VIIRS` |
| `platform` | string | Terra, Aqua, S-NPP, NOAA-20, NOAA-21 |
| `lat`, `lon` | float64 |  |
| `obs_ts_utc` | timestamp | From `acq_date` + `acq_time` |
| `obs_date_local` | date | Derived in the configured local timezone (see 6.2) |
| `confidence_raw` | string | As delivered |
| `confidence_num` | float | After mapping (see 6.1) |
| `frp` | float | Fire radiative power |
| `daynight` | char |  |

### 5.3 Derived outputs (precomputed, written to `cache/derived/` and copied to `demo_fixtures/`)

| File | Contents |
| --- | --- |
| `cell_day.parquet` | one row per (platform, cell_x, cell_y, date) with raw count, peak FRP |
| `series_daily.json` | raw and harmonized daily counts, overall and per sensor family |
| `calendar.json` | year x day-of-year matrices, raw and harmonized |
| `cells_geo.pmtiles` | grid cell geometry plus activity attributes |
| `validation.json` | overlap window and correlations |
| `baseline.parquet` | day-of-year percentiles per cell and per region |
| `meta.json` | parameters used, data windows, source URLs, build hash |

## 6. Core algorithms (`src/compute`)

### 6.1 Confidence normalization (`confidence.py`)

MODIS is numeric 0 to 100. VIIRS is low / nominal / high. Mapping is a config table, not hard-coded:

```yaml
viirs_confidence_map: {low: 20, nominal: 60, high: 90}   # proposed default
confidence_threshold: 50
```

With these defaults, `low` is dropped and `nominal` and `high` pass. This is a judgment call. Ship a **sensitivity report**: rerun the pipeline with alternate maps (for example nominal = 45, 55, 75) and show the effect on the validation correlation. Document the chosen map in the methods panel.

### 6.2 Grid and day definition (`harmonize.py`)

**Grid.** Square-ish cells of `cell_km` (default 5.5, configurable).

- `dlat = cell_km / 111.0`
- `dlon = cell_km / (111.0 * cos(lat0))` where `lat0` is a fixed reference latitude (region center). A fixed `lat0` keeps a regular grid.
- `cell_y = floor(lat / dlat)`, `cell_x = floor(lon / dlon)`

The reference code in the challenge brief divides both axes by 111.0. That works at low latitudes but makes cells narrower east-west, so the cos(lat0) correction is included here. Store `cell_km`, `lat0`, and the grid origin in `meta.json` so cells are reproducible.

**Day boundary.** `acq_date` in FIRMS is UTC. For a UTC+6 region, night overpasses can land on the previous UTC date, which splits one night's fire activity across two "days". Default: derive `obs_date_local` in `Asia/Dhaka` and group by that. Make it a config flag (`day_basis: local|utc`) and test both.

**Collapse rule.** One cell-day with any qualifying detection counts once.

### 6.3 Series definitions

- **Raw series:** count of all detections per day (after the confidence filter, so the two series differ only by the collapse).
- **Harmonized series:** count of distinct `(cell_x, cell_y, date)` per day.
- **Per-sensor-family harmonized series:** same grouping with `sensor_family` as an extra key. This is required for the overlap validation. The brief's reference query groups across all satellites, so it cannot produce this on its own.
- **Cross-platform agreement:** `count(DISTINCT platform)` per cell-day, kept as an attribute.

Example (per-family harmonized series):

```sql
SELECT obs_date_local, sensor_family,
       count(DISTINCT (cell_x, cell_y)) AS harmonized,
       count(*)                          AS raw
FROM detections
WHERE confidence_num >= ?
GROUP BY 1, 2;
```

**Known limitation.** The collapse removes spatial-resolution inflation. It does not fully remove effects from more overpasses per day as the constellation grows (Terra, Aqua, S-NPP, NOAA-20, NOAA-21 have different counts and times). Report this in the methods panel. Optional extension: also show a series normalized by the number of active platforms per day.

### 6.4 Overlap validation (`validate.py`)

1. Determine the overlap window as the date range where both MODIS and VIIRS have data for the region (derived from files).
2. Build daily series for each family, raw and harmonized, over that window.
3. Compute Pearson correlation for raw MODIS vs raw VIIRS and for harmonized MODIS vs harmonized VIIRS. Also compute Spearman as a robustness check.
4. Return both numbers, the window, sample size, and the ratio of mean counts (raw and harmonized).

Output goes to `validation.json` and is shown in the UI. Do not assume the improvement. Report what is measured.

### 6.5 Step-change quantification

Quantify the artifact so the demo claim is a measured number:

- Compare mean daily counts in matched windows before and after the transition (same seasons, for example a fixed set of years each side).
- Report the raw ratio and the harmonized ratio.
- Do not state "triples" unless the measured ratio supports it for the chosen region.

### 6.6 Seasonal baseline and anomaly (`baseline.py`, P1)

- **Baseline:** for each day-of-year, pool harmonized values over a window of +/- `w` days (default 7) across all years; store percentiles (p5, p25, p50, p75, p95) per region and per cell.
- **Anomaly score:** for a chosen date and area, compute the percentile rank of its harmonized value against the baseline pool for that day-of-year window.
- Return `{percentile, baseline_window, n_years, n_samples, method}`. The UI sentence is generated from this object by a template, not by a model.
- Leap day: map Feb 29 to Feb 28 or document the rule.
- Fall back to region-level when a cell has too few samples (configurable minimum).

### 6.7 Trend test (`trend.py`, P2)

`mann_kendall(series)` returns `S, Z, p, direction`; Theil-Sen slope separately. Apply to the harmonized annual or seasonal series only, never to raw. Unit tests against a known reference series.

## 7. API specification (`src/api`)

All responses are JSON and include:

```json
{ "data": {...}, "source": "live|cache|fixture", "dataset_ids": ["..."], "source_urls": ["..."], "generated_at": "..." }
```

| Method | Path | Params | Returns |
| --- | --- | --- | --- |
| GET | `/api/meta` |  | parameters, data windows per platform, build hash |
| GET | `/api/series` | `mode=raw\|harmonized`, `family?`, `from`, `to` | daily series |
| GET | `/api/calendar` | `mode`, `year_from`, `year_to` | year x day-of-year matrix |
| GET | `/api/cells` | `mode`, `date_from`, `date_to` | cell activity (GeoJSON or tile reference) |
| GET | `/api/validation` |  | overlap window, correlations, ratios |
| GET | `/api/anomaly` | `date`, `bbox` or `cell`, `window?` | percentile and baseline info |
| GET | `/api/methods` |  | cell size, confidence filter and map, collapse rule, limitations, sensor retirement note |
| GET | `/api/provenance/{figure_id}` |  | raw compute result behind a figure |

**Rules:** read-only; no endpoint triggers a NASA call; startup fails loudly if neither cache nor fixtures contain required derived files; CORS limited to the local frontend origin.

## 8. Frontend specification (`web/`)

- **Single global state:** `mode: raw | harmonized`. One toggle drives the map, calendar, and line chart. Switching must not refetch; both modes are loaded or lazily cached.
- **Views:** map of grid cells by activity; year-by-day calendar heatmap; daily series line chart marking the transition; validation card showing both correlations; anomaly question box; methods panel; provenance drawer.
- **Source badge:** every number displays `live`, `cache`, or `fixture` from the API wrapper field.
- **Offline requirements**
  - No external dependencies at runtime: self-host fonts, glyphs, sprites, icons, libraries.
  - Precache the app shell; tiles cache-first; data stale-while-revalidate; version caches.
  - PMTiles for basemap and cells; MapLibre reads them directly.
  - Request persistent storage (`navigator.storage.persist()`).
  - Optional: "Download for offline" screen with size estimate and "data last updated" per layer.
- **Graceful agent degradation:** if no agent or LLM is available, hide the agent UI. No error banners.
- **Accessibility and UX:** usable without training; color scales readable in both modes; consistent color scale across raw and harmonized so the difference is visually honest.

## 9. Offline and fallback design

- `src/acquire/safe.py` wraps every fetch: live first, then cache, then committed fixture, never raising during a demo. `OFFLINE=1` skips live.
- The challenge brief's reference wrapper handles JSON. Extend it for parquet and CSV (the FIRMS data), keyed by content hash.
- `demo_fixtures/` holds the minimum derived set for the demo region and years, committed to the repo. Keep it small enough for GitHub.
- A full cold start with wifi off must succeed by 12 Nov. Record the 240-second fallback video from that offline run.

## 10. Optional agent layer (P2)

Only if core P0 and P1 are done.

- Plain state machine, max 6 steps, one MCP server (custom FastMCP). No heavy framework.
- Tools: `firms_area_query` (retrieval, cache-backed), `trend_test` (deterministic), `cite_check` (returns true only if every numeric claim maps to a dataset id and source URL).
- Model may choose datasets, chain tools, and narrate. It may not compute any statistic or state a number no tool returned.
- Provenance guard blocks any output with an unsourced claim.
- Evaluation set: a small list of questions mapped to the expected tool call; grade tool-selection accuracy in `make test`.

## 11. Testing plan

| Test | Purpose |
| --- | --- |
| Synthetic collapse | A fine sensor producing N detections in one cell-day yields harmonized count 1 |
| Monotonicity | harmonized \<= raw for every day |
| Idempotence | Running the pipeline twice yields identical output |
| Grid boundary | Points at cell edges and across the region edge land in the expected cell; cell size matches `cell_km` within tolerance at `lat0` |
| Day basis | Night-pass detections group correctly under `local` and `utc` |
| Confidence map | MODIS passthrough; each VIIRS class maps per config; threshold boundary behavior |
| Validation | Known synthetic series with known correlation |
| Baseline | Percentiles on a hand-built dataset; leap-day handling; small-sample fallback |
| Trend | Mann-Kendall against a reference series |
| Offline | Full pipeline and API start with `OFFLINE=1` and no network |
| API contract | Every endpoint returns the source field and dataset ids |
| cite_check | Fails when a figure lacks id or URL |
| Manual | Cold-start offline in Chrome DevTools offline mode and on a real device in airplane mode; Lighthouse PWA audit |

`make test` runs all automated tests including the tool-selection evaluation.

## 12. Performance targets

- Charts never wait on a query: all demo series, calendars, and validation are precomputed to static JSON or parquet.
- Toggle response under 200 ms (client-side switch between preloaded datasets).
- Full demo region and years load from fixtures in a few seconds on a laptop.
- Pipeline rebuild from parquet for one region: target minutes, not hours. Measure actual size and timing in the first data pull **\[verify\]**.

## 13. Security and compliance

- Secrets only in `.env`; only `.env.example` committed; test each key with one call.
- API is read-only and local. No user data is collected.
- Apache-2.0 `LICENSE`; public repository testable in a private window with no login.
- Cite FIRMS with the product and sensor names, plus every library and asset, in README and project page.
- `docs/AI_USE.md` lists each AI tool, prompts, and what the team did itself (statistics, dataset selection, harmonization method, interface design).
- No recognizable name, voice, or likeness of anyone under 18 in any video or submission.

## 14. Build plan and milestones

| Phase | Deliverable | Done when |
| --- | --- | --- |
| **Now** | Keys, repo from template, region decision, **Suomi-NPP archive pulled before 1 Nov** | Parquet present for all sensors; availability windows recorded |
| **28 Oct** | Scope lock against full challenge statement | Dataset list updated; any newly named dataset cached the same day |
| **2 to 12 Nov** | `harmonize.py` + tests, validation, derived artifacts, fixtures, offline dry run | `make test` green; offline cold start passes |
| **Day 1 AM** | Core engine integrated: raw and harmonized series | Series match test expectations |
| **Day 1 PM** | Calendar, map, toggle | Toggle works for the 15:00 round |
| **Day 1 PM/Eve** | Baseline + anomaly (P1) | Record by 18:30 |
| **Day 2 AM** | Methods panel, validation display, responder brief | All numbers carry source badge |
| **Day 2 noon** | Freeze | Only videos, project page, public repo after this |

**Cut order:** one region instead of a subcontinent, then five years instead of twenty, then drop the anomaly engine and keep harmonization.

## 15. Technical risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Suomi-NPP archive not downloaded before 1 Nov | Loses early VIIRS years and overlap | Pull it first; commit needed fixtures |
| FIRMS column or confidence differences from assumptions | Normalization bugs | Inspect real files first; unit-test the loader |
| Overlap window too short or too noisy for a convincing correlation | Weak validation story | Report honestly; use Spearman and a longer window if available |
| Platform count changes over time still bias the series | Residual artifact | State it; show per-platform-normalized series as an extension |
| Raw step is smaller than "tripling" | Demo narrative mismatch | Use the measured ratio |
| Fixtures too large for the repo | Push or clone issues | Limit region and years; use Git LFS or a release asset if needed |
| Offline path diverges from live path | Demo surprises | One code path through `safe.py`; test with `OFFLINE=1` in CI |
| Time pressure | Core unfinished | Core engine first; everything else follows the cut order |

## 16. Open technical questions

1. Primary region: Bangladesh only, or South Asia?
2. Grid size: keep 5.5 km, or test 3 km and 11 km for sensitivity?
3. Day basis default: local (Asia/Dhaka) or UTC?
4. Is a partner dataset (Bangladesh Meteorological Department or Water Development Board) feasible in 48 hours?
5. Is the agent layer worth the time versus polishing the toggle and validation?
6. Hosting for the final public demo: static build plus fixtures only, or API container as well?