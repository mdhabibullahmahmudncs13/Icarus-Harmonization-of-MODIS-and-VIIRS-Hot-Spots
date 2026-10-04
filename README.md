# Icarus: Harmonization of MODIS and VIIRS Hot Spots

NASA Space Apps 2026 — Challenge 9 (Bangladesh local event).

Icarus reconciles 1 km MODIS and 375 m VIIRS (NOAA-20, NOAA-21) hotspot
detections from NASA FIRMS so the post-2012 count series is not inflated by
the finer sensor. The project ships a raw vs harmonized toggle, a
burning-activity calendar, a seasonal baseline and anomaly question, and a
methods panel.

Tagline: **Same fires. One honest record.**

## Status

- **Frontend:** built against mock data — daily series, raw/harmonized toggle,
  a procedural Three.js globe hero over the busiest-cells panel, burning
  calendar, validation card, anomaly box, methods panel, provenance drawer,
  source badge and mock banner. The data layer can run on the API instead
  (`VITE_DATA=api`, same-origin via a dev/preview proxy), and the anomaly box
  re-asks for the day you select. The map draws the payload's own cell
  polygons, shaded by the active mode; it carries no basemap, because a tile
  source would be a third-party request.
- **Acquisition (`src/acquire/`):** implemented for FIRMS (`firms.py`) with
  chunking, rate limiting, resume and parquet output. **No real NASA data has
  been downloaded yet** — run `make cache` with a `FIRMS_MAP_KEY` to do that.
- **Compute (`src/compute/`):** implemented — normalization, confidence
  mapping, grid harmonization, raw/harmonized series, seasonal baseline,
  anomaly rank, overlap validation and the contract export. Deterministic and
  offline; tested against synthetic detections only so far.
- **API (`src/api/`):** implemented — the seven contract endpoints, served
  offline-first from `cache/` then the committed `demo_fixtures/` fixture. It
  never calls NASA. With no cache and no key the demo runs on synthetic
  detections labelled `source: "fixture"`.

Mock and fixture data are never evidence and are labelled as such in the UI.

## What it does (planned)

- Pulls MODIS (Terra/Aqua) and VIIRS (NOAA-20, NOAA-21) hotspot CSVs from
  NASA FIRMS via `src/acquire/`.
- Harmonizes the two sensor series into a single comparable daily series.
- Serves the series, cells, baseline, anomaly, validation and methods payloads
  via a FastAPI backend (`GET /api/meta`, `/api/series`, `/api/cells`,
  `/api/baseline`, `/api/anomaly`, `/api/validation`, `/api/methods`).
- Renders a frontend with a raw/harmonized toggle, calendar, anomaly query,
  and methods panel.

## Datasets used

All from NASA FIRMS. Product names are used verbatim; `_SP` is standard
processing (the archive).

| ID | FIRMS product | Used for |
|----|---------------|----------|
| `FIRMS_VIIRS_SNPP` | `VIIRS_SNPP_SP` | Validation overlap; download first (ends 1 Nov 2026) |
| `FIRMS_MODIS` | `MODIS_SP` | Raw + harmonized MODIS series |
| `FIRMS_VIIRS_NOAA20` | `VIIRS_NOAA20_SP` | Raw + harmonized VIIRS series |
| `FIRMS_VIIRS_NOAA21` | `VIIRS_NOAA21_SP` | Raw + harmonized VIIRS series |

Source: <https://firms.modaps.eosdis.nasa.gov/api/area/>. The authoritative,
cited dataset list lives in `docs/DATA.md`.

## How to run

```bash
make venv    # create .venv and install the dependencies (uv)
make cache   # download NASA FIRMS data into cache/ (needs a FIRMS_MAP_KEY)
make fixture # write the offline demo detections to demo_fixtures/
make demo    # runs the API offline against demo_fixtures/ (uvicorn, :8000)
make test    # runs the test suite
make lint    # runs ruff
```

`make demo` starts the API at <http://127.0.0.1:8000>; the interactive docs
are at `/docs`. The frontend reads mock files by default. To run it on the
API instead:

```bash
make demo                 # terminal 1: the API on :8000
cd web && npm run dev:api # terminal 2: the app on :5174, VITE_DATA=api
```

The app calls `/api/*` on its own origin and the dev server proxies that
prefix to `:8000`, so nothing leaves loopback. Point `VITE_API_PROXY` (proxy)
or `VITE_API_BASE` (browser) elsewhere only when the API is not local.

`make cache` downloads Suomi-NPP first, then MODIS, NOAA-20 and NOAA-21, in
≤5-day chunks, and is resumable — a chunk already written to `cache/raw/` is
never re-requested. Narrow a run with `ARGS`, for example:

```bash
make cache ARGS="--products VIIRS_SNPP_SP --start 2012-01-01 --end 2020-12-31"
```

Set `OFFLINE=1` for a deterministic offline run: acquisition never attempts
network access, and the API serves the committed `demo_fixtures/` fixture
even if a real cache exists. Without it the API prefers `cache/` and falls
back to the fixture.

## Configuration

Copy `.env.example` to `.env` and fill in your keys (`FIRMS_MAP_KEY` is the
one this project needs). `.env` is gitignored. The repo runs fine without any
keys when `OFFLINE=1`.

## License

Apache-2.0. See `LICENSE`.
