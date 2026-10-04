# Icarus: Implementation Plan

Harmonization of MODIS and VIIRS hot spots. NASA Space Apps 2026, Challenge 9 (Bangladesh local event).

**Build order:** frontend first against mock data, then compute, then API, then swap mock for real data, then offline hardening and submission.

Last updated: 4 Oct 2026. Verify every external date at spaceappschallenge.org before relying on it.

---

## 1. Principles

1. **The killer demo comes first.** A single toggle switches every chart between raw and harmonized counts, and the false step change at the sensor transition disappears. Everything else supports this moment.
2. **Contract before code.** The frontend and the backend meet at one JSON contract (section 4). The mock data and the real API both validate against it, so swapping mock for real changes one environment variable and nothing else.
3. **Mock data is never evidence.** Mock mode shows a persistent "Mock data" banner. No number from mock mode goes into the video, the project page or the methods panel. A release build refuses to start in mock mode.
4. **Deterministic code does the science.** All statistics live in `src/compute`, tested, with no LLM calls. The frontend displays numbers and never calculates them. The mock generator is the one exception, and it is labeled.
5. **Offline from day one.** No CDN links, no third-party requests, self-hosted fonts. The demo must run with wifi off.
6. **Every number carries its source.** Each figure shows a source badge (`mock`, `live`, `cache` or `fixture`) and opens a provenance drawer with the JSON behind it.

---

## 2. Decisions to confirm

| Decision | Recommended default | Why |
|---|---|---|
| Region | Bangladesh box (88, 20, 93, 27) | Matches the doc's acquisition code, keeps data small, and gives local framing. |
| Cell size | 5.5 km, configurable | Doc default. Backed by a cell-size sweep in validation. |
| Confidence filter | 50 or above | Doc default. VIIRS l/n/h mapped to 25/60/90, configurable. |
| Frontend | Vite + React + TypeScript | Static build, fast iteration, easy to test. |
| Charts | d3 (scale, shape, array) with custom SVG | Full control over the toggle transition. No heavy chart library. |
| Map | MapLibre GL JS, cells as GeoJSON polygons | Reads PMTiles later for offline. |
| Validation of API shape | JSON Schema generated from zod types | One source of truth shared by mock files and pytest. |
| Time range if cut | A window that includes 2012 (for example 2010 to 2015) | A window that skips the transition has no demo. |

---

## 3. Phase overview and timeline

| Phase | What | Target dates | Done when |
|---|---|---|---|
| 0 | Data safety: Suomi-NPP and archive downloads (runs in parallel with everything) | 4 to 8 Oct (Suomi-NPP), rest by 15 Oct | Raw parquet for all sensors exists in `cache/raw/` |
| 1 | Contract and mock data | 4 to 6 Oct | Mock JSON files validate against the schema |
| 2 | Frontend on mock data (F1 to F6) | 6 to 16 Oct | Toggle demo works offline on mock data |
| 3 | Compute: normalize, harmonize, baseline, validate | 12 to 24 Oct (parallel with 2 if you have teammates) | Tests pass, validation numbers produced |
| 4 | FastAPI matching the contract | 20 to 26 Oct | Contract tests pass |
| 5 | Swap mock for real data and scope lock | 28 Oct to 1 Nov | Frontend runs on real cached data |
| 6 | Offline hardening, fixtures, dry run | 2 to 12 Nov | Cold start offline works on a real device |
| 7 | Submission materials | 9 to 14 Nov | Project page submitted, repo tested in a private window |
| Event | Follow the doc's 48-hour plan | Dates to confirm with the Local Lead | Freeze at noon on day 2 |

Key external dates from the project doc:

- **28 Oct:** full challenge statements publish. Lock scope that day.
- **1 Nov:** NASA stops serving Suomi-NPP data.
- **12 Nov:** a full offline dry run must succeed.
- **13 Nov:** submission and judging guides publish. Align the AI-disclosure wording with them.
- **14 Nov, 12:00:** the 30-second global video is due, with English subtitles.

---

## 4. Phase 1: Contract and mock data

### 4.1 Contract (`docs/API_CONTRACT.md` and `web/src/contract/`)

All responses include a `meta` block:

```jsonc
{
  "meta": {
    "source": "mock | live | cache | fixture",
    "generated_at": "ISO timestamp",
    "region": { "bbox": [88, 20, 93, 27] },
    "cell_km": 5.5,
    "min_confidence": 50,
    "date_range": ["2003-01-01", "2026-09-30"]
  }
}
```

| Endpoint | Purpose | Key fields |
|---|---|---|
| `GET /api/meta` | Region, parameters, sensor epochs | `sensors: [{ product, family, start, end }]` |
| `GET /api/series` | Daily counts, one fetch feeds every chart and the calendar | per day: `date, raw_modis, raw_viirs, raw_total, harm_modis, harm_viirs, harm_total` |
| `GET /api/cells?start&end` | Grid cells for the map over a window | per cell: `cell_id, bounds [w,s,e,n], raw, harmonized, peak_frp` |
| `GET /api/baseline` | Seasonal baseline | per day of year: `doy, p05, p25, p50, p75, p95`, plus `window_days`, `years_used` |
| `GET /api/anomaly?date&bbox` | "Is this unusual?" | `value, percentile, baseline_window, doy_range, years_used` |
| `GET /api/validation` | Overlap-period validation | `overlap`, `raw {pearson, spearman, ratio}`, `harmonized {...}`, `cell_sweep[]` |
| `GET /api/methods` | Content for the methods panel | `cell_km, min_confidence, confidence_mapping, collapse_rule, notices[], datasets[]` |

Design choices that keep the frontend simple:

- The calendar heatmap is derived client-side from `/api/series`, so the toggle never triggers a refetch.
- Cell bounds are returned by the API, so the frontend never works out grid geometry.
- Percentiles, correlations and baselines are computed server-side only.

### 4.2 Mock generator (`web/scripts/gen-mock.ts`)

Generate **cell-day records first**, then aggregate. That way series, cells and calendar always agree with each other.

- Seeded PRNG (for example mulberry32) so output is reproducible.
- A latent set of fire cell-days with a seasonal curve (dry-season peak) and year-to-year variation. This shape is an assumption for the mock only.
- MODIS-like sensor: detects a fraction of latent cell-days, one detection each, 2003 to 2026.
- VIIRS-like sensor from 2012: detects a higher fraction and produces several detections per cell-day, tuned so raw counts roughly triple at the transition while harmonized counts stay comparable.
- Spatial intensity from a few arbitrary blobs. Make no real-geography claims in mock mode.
- Output to `web/public/mock/*.json`, one file per endpoint, and validate each against the schema in the generator itself.
- Print a one-line summary on generation (raw ratio, harmonized ratio) so you can see the demo effect immediately.

Replace the sensor epochs with the real ones once confirmed from the FIRMS documentation (Suomi-NPP archive start, NOAA-20 and NOAA-21 start dates). Do not rely on memory for these.

**Exit criteria:** all mock files validate, and the raw series shows a clear step at 2012 that the harmonized series does not.

---

## 5. Phase 2: Frontend on mock data

### 5.1 Design direction

Subject: a scientific instrument that exposes a measurement artifact. The audience is judges who see it for 30 to 240 seconds, plus responders reading the brief.

- **One memorable element:** the series chart. When the toggle flips, the raw line eases down and the false step collapses. Everything else stays quiet.
- **Color encodes meaning, consistently, in every view:**
  - Raw: signal red `#C8372D`
  - Harmonized: teal `#0E7C86`
  - Ink `#14202A`, muted text `#5B6B76`, gridlines `#CBD3D8`, canvas `#EEF1F3`
  - Calendar and map intensity: a perceptual ramp (magma or inferno) so dark-to-bright reads as low-to-high activity
- **Type:** self-hosted. Atkinson Hyperlegible for the interface and numerals, Newsreader for the title and methods prose. Sentence case, no all-caps labels, line length under 80 characters.
- **Layout:** the series chart is the hero and sits at the top. The calendar and map sit below it, and a right rail holds the anomaly question and validation numbers.
- **Quality floor:** keyboard-reachable toggle with a visible focus ring, `prefers-reduced-motion` respected (swap instantly instead of tweening), responsive down to a phone, contrast checked.
- **Copy:** plain verbs and specific labels. "Raw detections" and "Harmonized cell-days", not internal names.

```
+--------------------------------------------------------------+
| Icarus                [ Raw | Harmonized ]      source: mock    |
+--------------------------------------------------------------+
| Daily counts, 2003 to 2026 (hero chart, sensor epochs marked) |
|                                                              |
+--------------------------------+-----------------------------+
| Burning calendar (year x day)  | Is this unusual?            |
|                                | [date] [area]  -> percentile |
+--------------------------------+ Validation: raw r, harm. r  |
| Map of grid cells              | Methods panel (drawer)      |
+--------------------------------+-----------------------------+
```

### 5.2 Structure

```
web/
  src/
    contract/        zod types, exported JSON Schema
    data/            DataSource interface, MockDataSource, ApiDataSource
    state/           mode (raw|harmonized), date, area; synced to the URL
    components/      Toggle, SeriesChart, CalendarHeatmap, CellMap,
                     AnomalyBox, ValidationCard, MethodsPanel,
                     SourceBadge, ProvenanceDrawer, MockBanner
    styles/          design tokens, self-hosted fonts
  public/
    mock/            generated JSON
    fonts/           woff2 files
    geo/             boundary GeoJSON (cite the source)
  scripts/gen-mock.ts
```

The data layer is selected by `VITE_DATA=mock|api`. Components only ever see the `DataSource` interface.

### 5.3 Milestones

| Milestone | Scope | Acceptance |
|---|---|---|
| **F1** Scaffold | Vite + React + TS, tokens, fonts, `DataSource` with mock, mock banner, source badge, release guard | App loads from mock files with no network |
| **F2** Series chart and toggle | Hero chart, sensor epoch markers, animated raw to harmonized transition, URL-synced mode | Toggle visibly removes the step. This is the demo, so finish it first |
| **F3** Calendar heatmap | Year-by-day grid driven by the same mode, tooltip with the day's value | Toggle updates the calendar without refetching |
| **F4** Map | MapLibre with cell polygons colored by the selected mode, date window control | Cells recolor on toggle, legend shows units |
| **F5** Questions and evidence | Anomaly box (percentile plus baseline window), validation card with both correlations, methods panel, provenance drawer | Every figure opens its source JSON |
| **F6** Quality | Responsive layout, keyboard and screen reader pass, reduced motion, error and empty states, self-hosted everything | Passes the checks in 5.4 |

### 5.4 Frontend checks

- **No third-party requests.** A Playwright test blocks all external hosts and the app must still load and work.
- **Toggle correctness.** A test loads mock data and asserts that every view changes when the mode changes, and that no network request fires on toggle.
- **Accessibility.** Run axe on the main views. Test keyboard-only use of the toggle and the date control.
- **Release guard.** `npm run build:release` fails if `VITE_DATA=mock`.
- **Performance.** Toggle response under 100 ms on a mid-range laptop with the full mock series.
- **Time-box.** If F4 (map) is slipping, ship it with static cell polygons and no date control. Do not let it delay F5.

---

## 6. Phase 0: Data safety (runs in parallel)

Start this today. It is independent of the frontend and has the only hard external deadline.

1. Create a FIRMS MAP_KEY and test it with one call. Put it in `.env` (never commit it).
2. **Download the Suomi-NPP VIIRS archive for the Bangladesh box first.** NASA stops serving it on 1 Nov 2026, and without it the 2012 to 2018 stretch of the record is missing. Use the archive (standard processing) products for the historical record.
3. Then MODIS (Terra and Aqua), NOAA-20 and NOAA-21.
4. Confirm exact product names, valid date ranges and the per-call day limit from the FIRMS API documentation. Chunk requests and respect 5,000 transactions per 10 minutes.
5. Write raw parquet per product to `cache/raw/`. Make the download resumable.
6. Record the dataset ids, product names and source URLs in `docs/DATA.md`.

---

## 7. Phase 3: Compute (`src/compute`)

Build in this order, each with tests and no network access.

1. **`schema.py`:** normalize MODIS and VIIRS to one schema. Map VIIRS confidence l/n/h to numbers via a single configurable constant, document it, and log any unknown columns.
2. **`harmonize.py`:** grid assignment and cell-day collapse, based on the reference function in the project doc with these fixes:
   - Use the numeric confidence column.
   - Scale longitude steps by cos(latitude) so cells are close to the stated size, and document the approximation.
   - Add the second aggregation that turns the cell-day table into the daily harmonized series.
3. **Series and baseline:** raw series, harmonized series per sensor family, seasonal baseline as day-of-year percentiles.
4. **`anomaly.py`:** percentile rank of a chosen date and area against the baseline, returning the baseline window used.
5. **`validate.py`:** correlation of raw MODIS vs raw VIIRS and of harmonized vs harmonized on the overlap period, plus the cell-size sweep.
6. **Tests:** a synthetic dataset where VIIRS produces about three times as many detections inside the same cells. Assert that harmonized counts match, raw counts do not, and harmonized correlation exceeds raw correlation. Add hand-checkable tests for the confidence mapping, cell assignment, baseline and anomaly.
7. **Export step:** a script that writes the exact JSON files the contract defines, so real data can be used as static files before the API exists.

A ready-made prompt for a coding agent covering this phase was written earlier in this conversation. Use it for phases 0 and 3.

---

## 8. Phase 4: API (`src/api`)

- FastAPI endpoints exactly matching section 4. The API reads from `cache/` and `demo_fixtures/` and never calls NASA during a demo.
- Every fetch goes through `src/acquire/safe.py` (live, then cache, then fixture), and `OFFLINE=1` forces fixtures.
- **Contract tests (pytest):** call every endpoint and validate the response against the JSON Schema exported from the frontend. Mock files and API responses pass the same schema.
- Include `meta.source` truthfully on every response.

---

## 9. Phase 5: Swap mock for real data

1. Run the export step or the API on the real cached data and switch the frontend with `VITE_DATA=api`.
2. Fix any shape differences by changing the code, not by loosening the schema.
3. Check that the real raw series shows the step at the sensor transition and the harmonized series reduces it. If it does not, investigate before polishing anything, because that is the finding the whole project rests on.
4. Review the validation numbers honestly. Report whatever the correlations are.
5. **28 Oct:** compare NASA's named datasets against the data plan, lock scope, and apply the cut list below if you are behind.

### Cut order (from the project doc)

1. Reduce the region (already Bangladesh only).
2. Shorten the time range, keeping a window that includes the 2012 transition.
3. Drop the anomaly engine and keep harmonization.
4. Replace live queries with static parquet and fixtures.

Keep the toggle demo intact to the very end.

---

## 10. Phase 6: Offline hardening (2 to 12 Nov)

- Copy the minimum demo set into `demo_fixtures/` (the exact bytes the demo needs) and precompute the demo series as static JSON.
- Package the basemap as a PMTiles file and serve it locally.
- Add a service worker (Workbox): precache the app shell, cache-first for tiles, stale-while-revalidate for data, versioned caches.
- Self-host every font, glyph, sprite and library. One CDN link breaks a cold offline start.
- Show the source badge (`live`, `cache`, `fixture`) in the interface.
- Make the backend portable: FastAPI plus cache runs from one command or one Docker image.
- Test cold start, not just reload: Chrome DevTools offline mode, then airplane mode on a real device, then a Lighthouse PWA audit.
- **Gate:** a full dry run offline succeeds by 12 Nov. Record a fallback video of it.

---

## 11. Phase 7: Submission

Secure the three single-point items first (they take about fifteen minutes):

- [ ] Challenge category named on the project page
- [ ] Repository public and open to a stranger. Test it in a private window
- [ ] Project page fully filled and submitted

Then the rest:

- [ ] `LICENSE` is Apache-2.0 and visible
- [ ] `docs/AI_USE.md` lists every AI tool, the prompts, what the AI did and what it did not do (the harmonization method, parameters and statistics are the team's own)
- [ ] README states the datasets used with FIRMS product names, and cites every source (including the boundary file and fonts)
- [ ] NASA data sources section lists each dataset, what it was used for and how. Judges check it against your claims
- [ ] Methods panel shows cell size, confidence filter, collapse rule, both validation correlations, and the note that Suomi-NPP ends on 1 Nov 2026 and MODIS is being retired
- [ ] 240-second video: names NASA datasets on camera, built from real (not mock) data
- [ ] 30-second global video: team, problem, the thing working, NASA data usage, impact, English subtitles
- [ ] No recognizable name, voice or likeness of anyone under 18 appears in any video or submission
- [ ] Align AI-disclosure text with the official wording after the guides publish on 13 Nov
- [ ] Check whether the 1 Oct prescreening video was submitted. If not, ask the Local Lead whether a late entry is possible

### 240-second demo storyboard

1. The problem: fire counts appear to triple after 2012 (raw view).
2. The cause: the finer sensor detects more and smaller fires. The step comes from the instrument, not the world.
3. The flip: toggle to harmonized and the step disappears. Name FIRMS, MODIS and VIIRS on camera.
4. The evidence: show both correlations from the overlap period.
5. The use: ask the anomaly question for a place and date, show the percentile and baseline window.
6. Why now: Suomi-NPP ends 1 Nov 2026 and MODIS is being retired, so continuity is an operational problem.

---

## 12. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Suomi-NPP archive not downloaded before 1 Nov | The 2012 to 2018 record is missing | Phase 0 starts today and finishes first |
| FIRMS column or product-name differences | Normalization fails | Check the FIRMS docs, normalize at ingest, log unknown columns |
| VIIRS confidence mapping drops too much | Counts shift | Configurable mapping, sensitivity check in the validation sweep |
| Real data does not show a clean step | The demo story weakens | Check early in Phase 5, adjust cell size or the story, report honestly |
| Mock numbers leak into the video | Misleading submission | Mock banner and the release build guard |
| Frontend and API shapes drift | Integration pain | Shared JSON Schema and contract tests |
| Map or offline tile work overruns | Lost days | Static polygons first, PMTiles in Phase 6 only |
| Third-party request breaks offline start | Demo fails | Playwright external-host block test in CI |

---

## 13. Definition of done

- The toggle switches every view between raw and harmonized without a network request, and the step change visibly disappears.
- All statistics come from tested functions in `src/compute`, and every figure opens its source JSON.
- `make cache`, `make demo` (offline) and `make test` all pass, and the demo runs with wifi off from a cold start.
- The validation card shows raw and harmonized correlations from the overlap period.
- The repository is public, Apache-2.0 licensed, and documents its datasets, AI use and references.
- The project page, 240-second video and 30-second global video are submitted.