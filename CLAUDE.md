# CLAUDE.md

Icarus — instructions for Claude (and any other AI coding agent) working on this repository.

## Project

Reconcile 1 km MODIS and 375 m VIIRS (NOAA-20, NOAA-21) hotspot detections
from NASA FIRMS so the post-2012 count series is not inflated by the finer
sensor.

Deliverables:

- Raw vs harmonized toggle on the chart.
- Burning-activity calendar (heatmap of day-of-year by year).
- Seasonal baseline and anomaly question ("how unusual is this date?").
- Methods panel: cell size, confidence filter, collapse rule, validation
  correlations, sensor retirement note.

## Non-negotiables

1. **Offline-first.** Read from `cache/`, fall back to `demo_fixtures/`.
   Honour `OFFLINE=1` (no network calls). The demo must never raise because
   the network is unavailable.
2. **Deterministic science lives only in `src/compute/`.** No LLM calls, no
   network calls in that folder. All inputs and outputs are plain pandas
   objects.
3. **Frontend never calls NASA directly.** The frontend talks to the API;
   the API reads the local cache or fixtures.
4. **Cite every dataset with an id and a URL.** Use FIRMS sensor product
   names verbatim in code and comments.
5. **Record every AI tool and key prompt in `docs/AI_USE.md`.**
6. **Apache-2.0, public repository.** No under-18 likenesses anywhere —
   do not add photos, names, or other identifying details of minors.

## Domain notes (use verbatim)

- Default grid cell **5.5 km**, configurable.
- Confidence filter **50 or above** (after the VIIRS-to-numeric mapping
  described below).
- **MODIS confidence** is 0–100. **VIIRS confidence** is low/nominal/high
  and must be mapped to a numeric scale before filtering.
- **Raw series** = count of all detections per day.
  **Harmonized series** = count of distinct cell-days per day.
- **Validate on the MODIS/VIIRS overlap period**: correlation of raw vs raw
  and harmonized vs harmonized.
- **Suomi-NPP** data ends **1 Nov 2026** and **MODIS is being retired**.
  Prefer VIIRS on NOAA-20 and NOAA-21.

## Commands

```bash
make cache   # populate cache/ from NASA FIRMS (TODO)
make demo    # OFFLINE=1 uvicorn src.api.main:app
make test    # pytest -q
make lint    # ruff check .
```

## Style

- Python 3.11+, type hints on every public function.
- Small pure functions in `src/compute/`.
- pytest for all science. Stub functions should be `xfail` rather than
  silently passing.
- Cite the dataset id in code comments where the modulation is known
  (e.g. `# FIRMS_VIIRS_NOAA20 confidence mapping`).

## Folder layout

```
cache/             downloaded NASA data (gitignored)
demo_fixtures/     committed fixtures for the offline demo
docs/              AI_USE.md, METHODS.md, DATA.md
src/acquire/       data download modules
src/compute/       deterministic science (no LLM, no network)
src/api/           FastAPI app
web/               frontend
tests/             pytest
```