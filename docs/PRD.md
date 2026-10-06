# Project Icarus — Product Requirements Document

**Version:** 1.0 · **Date:** 05 October 2026 · **Status:** Baseline for release · **Challenge:** NASA Space Apps 2026 — Harmonization of MODIS and VIIRS Hot Spots

---

## 1. Product Vision & Problem Statement

Project Icarus is an offline-capable web application that harmonizes satellite active-fire hot spots from MODIS (Terra, Aqua) and VIIRS 375 m (Suomi NPP, NOAA-20, NOAA-21) into a single, consistent **burning activity calendar**.

The problem is an artefact of the observing record, not of the fires themselves. MODIS detects fires at 1 km and is insensitive to small or cool fires. VIIRS detects at 375 m and resolves many more fires, including smaller ones. Because the VIIRS stream only enters the record around 2012, naive counting of raw detections shows a step change in "fire activity" at the year VIIRS begins — a discontinuity created by the instruments, not by the planet. Analysts who rely on these records for trends, climatology, or anomaly detection see a false signal.

Icarus removes that artefact through three deterministic mechanisms:

1. **Presence-based gridding** — detections collapse to cell-day presence on a 0.05° grid, which reduces but does not eliminate sensor bias.
2. **Cross-sensor multiplicative calibration** — VIIRS values are mapped onto the MODIS-equivalent scale using factors estimated on overlap years, so the historical record is left unaltered.
3. **Explicit uncertainty** — bootstrap bands, coverage hatching, and source tagging ensure that modelled values are never presented as raw observations.

Vision: a field-usable, trustworthy calendar of burning activity in which activity, anomaly, and observing coverage are visually distinct, and in which every displayed number is traceable to a deterministic computation and a named NASA dataset.

---

## 2. Target Users & Personas

**P1 — Emergency responder / incident planner (primary).** Needs to know whether the current period is normal or elevated for the region, and when the burning season typically starts and peaks. Works in low-connectivity field conditions. Values speed, clarity, and offline reliability over analytical depth.

**P2 — Air-quality / environmental analyst (primary).** Needs long-run, sensor-consistent time series and anomaly scores for a region or custom polygon. Cares about methodology, uncertainty, and the ability to export or re-query results. Will read the provenance panel.

**P3 — Research reviewer / hackathon judge (secondary).** Needs to verify that NASA data is used correctly, that the harmonization is principled and reproducible, and that model-derived values are labelled as such.

---

## 3. Goals & Success Metrics

| ID | Goal | Measurable outcome |
|----|------|--------------------|
| G1 | Ingest the pilot record reproducibly | Pipeline rebuilds the pilot dataset from raw files with an identical parameter hash → identical output bytes (ties to AC-1). |
| G2 | Remove the artificial VIIRS step change | Cell-day artificial step at the VIIRS join year shrinks after harmonization relative to raw counts (E1). |
| G3 | Quantify cross-sensor offset | Calibrated series reduces median absolute offset versus raw and uncalibrated cell-day series over overlap years (E2). |
| G4 | Separate activity, anomaly, and coverage | Low-coverage bins are visually distinct from zero-activity bins in every view. |
| G5 | Validate against independent truth | Harmonized density correlates with MODIS burned area at 0.25° scale (E8, target r² > 0.5 at coarse scale). |
| G6 | Work offline | Full demo runs with the network off; app shell cold-starts from the service worker (AC-3, AC-6). |

---

## 4. Scope

### 4.1 In Scope

- Active-fire point detections from MODIS (Terra, Aqua) and VIIRS 375 m (S-NPP, N20, N21).
- Presence-based gridding on a 0.05° cell grid (K = 20 cells/degree).
- Static/persistent source masking to suppress industrial and urban false positives.
- Cross-sensor multiplicative calibration on overlap years, with pseudo-count shrinkage and bootstrap uncertainty.
- Climatology, z-score anomaly scoring, and critical fire-period detection.
- Area-of-interest aggregation via preset regions and user-drawn polygons.
- Offline-first frontend: service worker, PMTiles basemap, in-browser query cache.
- Optional MCP-based AI narration layer that reads API JSON and explains results.

### 4.2 Out of Scope

- Burned-area mapping (MCD64CMQ is used only as an independent validation reference).
- Fire-spread modelling and emissions estimation.
- Real-time alerting or notification services.
- Global deployment — pilot extent is 60–93°E, 5–36°N (South Asia).

---

## 5. Key User Stories and Primary Flows

**US-1 — Region overview.** As a responder, I select a preset region and see its calendar heatmap so I can judge whether this season is normal.
**US-2 — Anomaly check.** As an analyst, I view anomaly scores for the current year so I can identify elevated periods at a glance.
**US-3 — Season window.** As a planner, I read the critical fire period (onset, peak, end) so I can schedule readiness.
**US-4 — Custom study area.** As an analyst, I draw a polygon so I can query a non-preset area.
**US-5 — Provenance.** As a reviewer, I open the provenance panel so I can confirm which datasets, versions, and parameters produced the view.
**US-6 — Offline use.** As a field user, I download a region for offline use so the app still works without connectivity.

**Primary flow (region overview):** launch app → select preset AOI → series query returns bins → calendar heatmap renders activity with coverage hatching → user toggles anomaly layer → user opens critical-period panel → provenance panel shows dataset and parameter hash.

---

## 6. Functional Requirements

Priority: **M** = must, **S** = should, **C** = could.

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | System ingests MODIS (Terra, Aqua) and VIIRS (S-NPP, N20, N21) detections and normalizes them to a single schema with stream and stream-bit fields. | M |
| FR-02 | System records every acquired raw file in a manifest with file name, bytes, sha256, row count, retrieval date, and source URL. | M |
| FR-03 | System applies the quality filter: MODIS retained when confidence ≥ c_min and hot-spot type is fire or null; VIIRS retained when confidence class is nominal or high. | M |
| FR-04 | System masks static/persistent sources per year using a fine grid and a persistence-day threshold. | M |
| FR-05 | System snaps detections to 0.05° grid cells using floor semantics and records a per-cell area weight. | M |
| FR-06 | System collapses same-stream detections in the same cell and day into one presence record with a stream bitmask, detection count, and maximum FRP. | M |
| FR-07 | System bins cell-days into 46 eight-day bins per year, restarting each 1 January. | M |
| FR-08 | System computes stream availability, per-bin coverage, family coverage, and joint MODIS coverage, including known outages. | M |
| FR-09 | System estimates multiplicative calibration factors per tile and month with shrinkage toward the regional ratio, and stores bootstrap draws. | M |
| FR-10 | System produces harmonized cell-bin values tagged by source (MODIS, BRIDGE, VIIRS_CAL, NONE). | M |
| FR-11 | System computes climatological baselines, anomaly z-scores, percentile ranks, and elevated/extreme flags for an AOI. | M |
| FR-12 | System computes the critical fire period (onset, peak, end, window mass) for an AOI. | M |
| FR-13 | API exposes health, meta, series, anomalies, critical-period, and preset-AOI endpoints, all returning the parameter hash. | M |
| FR-14 | System validates AOI input (closed ring, minimum positions, within extent, non-self-intersecting, cell-count limit) and returns structured errors. | M |
| FR-15 | Frontend renders a MapLibre map with PMTiles basemap and a d3 calendar heatmap. | M |
| FR-16 | Frontend supports preset selection and polygon drawing. | M |
| FR-17 | Frontend renders distinct anomaly and critical-period panels. | M |
| FR-18 | Frontend renders a provenance panel with dataset names, versions, retrieval dates, and parameter hash. | M |
| FR-19 | Frontend provides a "Download for offline" screen with size estimate, progress, and per-layer last-updated timestamps. | M |
| FR-20 | Low-coverage and modelled bins are visually distinct (hatching, outline) and never coloured as zero activity. | M |
| FR-21 | Optional AI narration layer reads API JSON only and is hidden when unavailable. | S |
| FR-22 | System supports display of UTC and local acquisition time for seasonal alignment. | C |

---

## 7. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | **Determinism.** Identical raw inputs and an identical parameter hash MUST produce byte-identical derived outputs. |
| NFR-02 | **Offline operation.** After data is cached, the app MUST run with the network off; app shell cold start MUST succeed from the service worker. |
| NFR-03 | **Performance.** Cold-start load, API response time, and cache size MUST be measured on laptop-class hardware without GPUs (E9). |
| NFR-04 | **Accessibility.** Interactive controls MUST be keyboard reachable; charts MUST not rely on colour alone to convey coverage or anomaly state. |
| NFR-05 | **Reproducibility.** Every derived artifact MUST carry the parameter hash so any view can be traced to its configuration. |
| NFR-06 | **Security.** The API MUST run read-only; secrets MUST come from environment variables; logs MUST not contain user AOI geometries. |

---

## 8. Constraints & Assumptions

- NASA data is the named evidence layer and is acknowledged in the interface and project page.
- Deterministic code performs the science; any LLM only retrieves, orchestrates, or explains.
- The demo runs with the network off; a fallback video is recorded.
- Laptop-class hardware, no GPUs; DuckDB runs embedded.
- Small team with Python, SQL, and web-development skills; ten-week build window.
- Assumption: enough overlap years exist within the pilot extent to fit calibration; otherwise the documented fall-back applies.

---

## 9. Risks and Mitigations

| ID | Risk | Prob. | Impact | Mitigation |
|----|------|-------|--------|------------|
| R1 | Slow or blocked data download | M | H | Start S0 in week 1; use archive downloads; scope to pilot sub-region. |
| R2 | Calibration unstable in sparse tiles | M | M | Shrinkage toward regional ratio; larger tiles; regional-only fall-back. |
| R3 | Insufficient overlap years | L | H | Documented calibration fall-back; N20/N21 as fallback streams. |
| R4 | Offline storage exceeds device capacity | M | M | Size estimate before download; incremental caching; last-updated timestamps. |
| R5 | Service worker cache eviction | M | M | Request persistent storage; versioned Cache API; OPFS fallback. |
| R6 | UTC date splitting misaligns local season | L | L | Quantified in E6; offer UTC and local time display. |
| R7 | AI narration states an incorrect figure | L | M | Hide layer when unavailable; every number must appear in API JSON; label as AI-generated. |

---

## 10. Release Acceptance Criteria

- **AC-1** Pipeline rebuilds the pilot dataset from raw files with an identical parameter hash → identical output bytes.
- **AC-2** Experiments E1–E8 completed and reported, including negative results.
- **AC-3** Offline demo runs with Wi-Fi off; fallback video recorded.
- **AC-4** All M-priority functional requirements pass acceptance tests.
- **AC-5** API returns HTTP 422 for an invalid AOI with a structured `{code, message, field}` error.
- **AC-6** Service worker precaches the app shell; offline cold start succeeds.
- **AC-7** Provenance panel shows dataset names, versions, retrieval dates, and parameter hash.

---

## 11. Open Questions

- Which preset AOIs are included at launch, and who owns their geometries?
- What is the exact target device profile (minimum RAM and storage) for the field demo?
- Is the AI narration layer part of the launch demo or a stretch feature?
- Should results be exportable (CSV/GeoJSON), and if so under which licence?
- What is the retention and refresh policy for cached offline layers?
