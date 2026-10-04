# Icarus: Harmonization of MODIS and VIIRS Hot Spots

NASA Space Apps 2026 — Challenge 9 (Bangladesh local event).

Icarus reconciles 1 km MODIS and 375 m VIIRS (NOAA-20, NOAA-21) hotspot
detections from NASA FIRMS so the post-2012 count series is not inflated by
the finer sensor. The project ships a raw vs harmonized toggle, a
burning-activity calendar, a seasonal baseline and anomaly question, and a
methods panel.

## Status

This repository currently contains the **context files and harness only**.
The harmonization logic, API surface, frontend, and agent code are stubs and
will be implemented in later commits.

## What it does (planned)

- Pulls MODIS (Terra/Aqua) and VIIRS (NOAA-20, NOAA-21) hotspot CSVs from
  NASA FIRMS via `src/acquire/`.
- Harmonizes the two sensor series into a single comparable daily series.
- Serves the series, calendar, and baseline data via a FastAPI backend.
- Renders a frontend with a raw/harmonized toggle, calendar, anomaly query,
  and methods panel.

## Datasets used (placeholders)

| ID | Product | Source |
|----|---------|--------|
| FIRMS_MODIS | MODIS C6.1 hotspots | TODO: add URL |
| FIRMS_VIIRS_NOAA20 | VIIRS 375 m NOAA-20 | TODO: add URL |
| FIRMS_VIIRS_NOAA21 | VIIRS 375 m NOAA-21 | TODO: add URL |

The authoritative dataset list lives in `docs/DATA.md`.

## How to run

```bash
make cache   # TODO: download NASA FIRMS data into cache/
make demo    # runs the API offline against demo_fixtures/
make test    # runs the test suite
make lint    # runs ruff
```

Set `OFFLINE=1` to force the API to use only `demo_fixtures/` and never
attempt network access.

## Configuration

Copy `.env.example` to `.env` and fill in your keys. The repo runs fine
without any keys when `OFFLINE=1`.

## License

Apache-2.0. See `LICENSE`.