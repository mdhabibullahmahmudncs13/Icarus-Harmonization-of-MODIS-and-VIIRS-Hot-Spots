# PRD: MODIS + VIIRS Hotspot Harmonization

**Challenge:** NASA Space Apps 2026, Challenge 9 (Thermal sensing & wildfires), Bangladesh node **Working name:** Harmonized Burn Calendar **License:** Apache-2.0, public repository **Status:** Draft v1. Source: the challenge brief and shared build kit. Only challenge summaries are live; full statements land 28 Oct, so scope must be re-checked then.

---

## 1. Problem

MODIS detects fires at 1 km. VIIRS detects at 375 m. The finer sensor sees more and smaller fires, so a raw detection count jumps at the sensor transition. That jump is an instrument artifact, not a change in the world. Anyone comparing fire activity across decades gets a false trend.

It is also urgent. Suomi-NPP data stops being available from NASA on **1 Nov 2026**, and Terra/Aqua MODIS shut down from late 2026. Sensor continuity is now an operational problem.

## 2. Goal and non-goals

**Goal:** Produce a fire-activity series over South Asia / Bangladesh, 2003 to 2026, that is comparable across the MODIS to VIIRS transition, and let a user see and verify that.

**Non-goals**

- Fire spread forecasting or fire-cause attribution.
- Replacing NASA's official products.
- Real-time alerting. Near-real-time is optional only via replayed fixtures.
- The LLM computing any statistic.

## 3. Users

| User | Need |
| --- | --- |
| Responder / forest or agriculture analyst | "Is this burning unusual for this place and time of year?" |
| Researcher | A series without a sensor step change, with method and validation shown |
| Judge | A visible, verifiable before/after in under 240 seconds |

## 4. Core demo (the part that must not break)

One toggle switches every chart between **raw** and **harmonized** counts. In the raw view the counts step up at the transition. In the harmonized view the step disappears and the seasonal signal remains. The brief expects the raw step to look like roughly a tripling. Treat that as a hypothesis to confirm on our region, not a claim to repeat.

## 5. Functional requirements

**P0: must ship**

1. **Harmonization engine** (`src/compute/harmonize.py`)
   - Filter to confidence >= 50.
   - Assign detections to a common grid (default 5.5 km, configurable).
   - Collapse all same-day detections in a cell into one cell-day.
   - Output raw series (all detections per day) and harmonized series (distinct cell-days per day).
2. **Confidence normalization.** MODIS reports 0 to 100. VIIRS reports low / nominal / high. Map VIIRS classes to a numeric scale before the cut-off. The mapping is documented and configurable.
3. **Overlap validation.** On the period where both sensors observed the same fires, report correlation of raw MODIS vs raw VIIRS and harmonized vs harmonized. Both numbers appear in the UI. The improvement is the evidence.
4. **Raw/harmonized toggle** that drives the map and the calendar together.
5. **Burning calendar:** year-by-day heatmap.
6. **Map** of grid cells colored by activity.
7. **Methods panel:** cell size, confidence filter, collapse rule, validation correlations, and a note on Suomi-NPP ending 1 Nov 2026 and MODIS retirement.
8. **Offline operation:** the full demo runs with `OFFLINE=1`. Every fetch goes through the live, cache, fixture wrapper, and the UI shows the source badge.

**P1: should ship** 9. **Seasonal baseline:** day-of-year percentiles from the harmonized record. 10. **Anomaly question:** "Is this unusual for this place and time of year?" Answered with the percentile and the baseline window. 11. **Responder brief:** one-page, plain-language output with every number sourced. 12. **Provenance drawer:** raw tool JSON behind each figure.

**P2: nice to have** 13. NASA POWER wind / temperature / humidity as context for an anomaly. 14. Mann-Kendall / Theil-Sen trend test on the harmonized series (`trend_test` tool). 15. Optional agent layer (retrieve, orchestrate, narrate). The app must work fully without it. 16. Bangladesh partner data (BMD station data) layered on top.

## 6. Technical design

**Layers** (the frontend never calls NASA; the API never calls NASA during a demo)

- **Acquisition** (`src/acquire`): runs before the event. FIRMS archives for MODIS and VIIRS, stored as parquet.
- **Compute** (`src/compute`): deterministic, tested, no LLM.
- **API** (`src/api`): FastAPI reading the local cache.
- **Frontend** (`web/`): static, offline-capable. MapLibre / deck.gl with a service worker. Self-host fonts, glyphs, icons, and libraries. PMTiles for the basemap.
- **Agent** (optional, `src/agents`): plain state machine, max 6 steps, `cite_check` guard before output.

**Data**

| Source | Use |
| --- | --- |
| FIRMS: MODIS | Historical detections, validation |
| FIRMS: VIIRS (NOAA-20, NOAA-21) | Continuing sensors |
| NASA POWER | Environmental context (P2) |
| GIBS tiles | Basemap |
| Third-party / partner data | Needed for top "NASA data usage" score |

FIRMS limit: 5,000 transactions per 10 minutes. Use bulk archive CSVs for long records.

**Reference implementation notes**

- The brief's DuckDB query groups by `acq_date, cell_y, cell_x` across all satellites. To validate, we also need the same grouping **per sensor**, so each sensor's harmonized series can be compared.
- It converts the cell size with `/111.0` degrees for both axes. Longitude degrees shrink with latitude, so cells are narrower east-west. Fine at one region, but document it or correct with cos(lat).

**Repo layout:** `LICENSE`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `.env.example`, `cache/` (gitignored), `demo_fixtures/` (committed), `docs/AI_USE.md`, `src/{acquire,compute,agents,api}`, `web/`.

## 7. Success metrics

| Metric | Target |
| --- | --- |
| Harmonized-vs-harmonized overlap correlation | Clearly higher than raw-vs-raw (exact numbers reported, whatever they are) |
| Step change at transition | Visibly removed in harmonized view, and quantified |
| Offline cold start | Full demo passes with wifi off by 12 Nov |
| Compute tests | `make test` passes; every UI number traces to a tool result |
| Submission gates | Category named, public repo (tested in a private window), project page submitted |

## 8. Scoring alignment

| Criterion | How this build earns it |
| --- | --- |
| Impact | Operational continuity as sensors retire; Bangladesh framing (burning season, agriculture) |
| Creativity | The disappearing-step toggle |
| Validity | `src/compute` boundary, overlap correlations, provenance drawer |
| Relevance | FIRMS named on camera and on the project page |
| Presentation | 240-second story: artifact, fix, proof, why now |
| NASA data usage | FIRMS plus a partner/third-party layer |

## 9. Timeline

| When | Milestone |
| --- | --- |
| This week | Earthdata account, FIRMS MAP_KEY, api.nasa.gov key tested; fork template |
| **Before 1 Nov** | Download all Suomi-NPP archive data needed (see risks) |
| 28 Oct | Full challenge statements land; lock scope and dataset list |
| 2 to 12 Nov | Pre-build cache and fixtures; wire one MCP server and skill; offline dry run |
| 13 Nov | Submission and judging guides publish; align AI-disclosure wording |
| 14 Nov, 12:00 | 30-second global video |
| Day 1 | Morning: harmonization core. Afternoon: map + calendar, toggle working by 15:00 round. Evening: baseline + anomaly, record by 18:30 |
| Day 2 | Morning: methods panel, validation, responder brief. Noon: freeze, record, submit |

Confirm exact event dates with the Local Lead.

## 10. Cut order if behind

1. One region instead of a subcontinent
2. Five years instead of twenty
3. Drop the anomaly engine, keep harmonization

The toggle demo stays intact to the end.

## 11. Risks and open questions

| # | Item | Mitigation |
| --- | --- | --- |
| 1 | **Suomi-NPP data ends 1 Nov 2026.** The brief names NOAA-20/21 as continuing sensors, but NOAA-20 and NOAA-21 started after 2012, so the earliest VIIRS years and the MODIS/VIIRS overlap likely depend on Suomi-NPP. (My inference from mission timelines; verify.) | Pull the full S-NPP archive for the chosen region **before 1 Nov** and commit what the demo needs as fixtures |
| 2 | Region inconsistency: the demo text says South Asia, the challenge skill says Bangladesh (bbox 88,20,93,27) | Decide now. Recommend Bangladesh as primary, South Asia as stretch |
| 3 | Overlap window not yet identified | Identify it in the first data pull; it is the validation set |
| 4 | VIIRS confidence mapping is a judgment call | Document the mapping and show sensitivity to alternatives |
| 5 | The "triples" claim may not hold regionally | Report the measured ratio |
| 6 | Dataset advice is the guide's own, not NASA's, until 28 Oct | Recheck on 28 Oct; cache any newly named dataset that day |
| 7 | AI-disclosure wording not final until 13 Nov | Keep `docs/AI_USE.md` current as you build |
| 8 | Rule violations disqualify: open source, every source cited, no under-18 likeness in any video | Checklist before every submission |

**Open questions:** Final grid size (5.5 km default)? Is a partner dataset (BMD, BWDB) feasible in 48 hours? Is the agent layer worth the time versus polishing the toggle?