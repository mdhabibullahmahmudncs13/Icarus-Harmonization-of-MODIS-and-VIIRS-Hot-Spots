# AGENTS.md

Short mirror of `CLAUDE.md` for AI coding agents.

## Project

Reconcile 1 km MODIS and 375 m VIIRS (NOAA-20, NOAA-21) hotspot detections
from NASA FIRMS so the post-2012 count series is not inflated by the finer
sensor.

## Non-negotiables

1. **Offline-first.** Read from `cache/`, fall back to `demo_fixtures/`.
   Honour `OFFLINE=1`.
2. **Deterministic science lives only in `src/compute/`.** No LLM, no network.
3. **Frontend never calls NASA directly.**
4. **Cite every dataset with an id and a URL.** Use FIRMS sensor product names.
5. **Record every AI tool and key prompt in `docs/AI_USE.md`.**
6. **Apache-2.0, public repository.** No under-18 likenesses anywhere.

## Domain notes

- Default grid cell 5.5 km, configurable. Confidence filter >= 50.
- MODIS confidence is 0–100. VIIRS confidence is low/nominal/high — map to
  numeric before filtering.
- Raw series = count of detections/day. Harmonized series = distinct
  cell-days/day.
- Validate on the MODIS/VIIRS overlap: report raw-vs-raw and
  harmonized-vs-harmonized correlation.
- Suomi-NPP ends 1 Nov 2026; MODIS being retired. Prefer VIIRS NOAA-20/21.

## Commands

```
make cache    # TODO: download NASA FIRMS data
make demo     # OFFLINE=1 uvicorn src.api.main:app
make test     # pytest -q
make lint     # ruff check .
```

See `CLAUDE.md` for full details and the methods/validation requirements.