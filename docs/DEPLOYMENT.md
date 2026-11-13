# Deployment & Runbook

How to install, run, and operate Project Icarus, including the offline field
demo. The system is a single read-only FastAPI service plus a static
frontend, backed by a pre-fetched Parquet cache. See `docs/ARCHITECTURE.md`
for the design.

---

## 1. Deployment model

The API runs from a source checkout. There is no container image, no server
database and no runtime dependency on NASA: the data is a Parquet cache on
disk, read through DuckDB.

Three supported targets, all running the same code:

| Target | Use | Notes |
|--------|-----|-------|
| Laptop | Field demo, judging | The API runs locally; no internet after the cache is built. |
| Raspberry Pi | Local LAN server | Same commands; ARM build. |
| Cloud VM | Shared access | Put behind TLS; still read-only. |

---

## 2. Prerequisites

- Python 3.11+ (`uv` for the venv, or any `venv` you manage).
- Node 20+ for the frontend.
- A populated data cache (see §4) or the committed offline fixture.

---

## 3. Configuration

Environment variables (names only — never commit values):

| Variable | Default | Read by | Purpose |
|----------|---------|---------|---------|
| `FIRMS_MAP_KEY` | — | `make cache` only | NASA FIRMS Area API key |
| `OFFLINE` | unset | acquisition, API | `1` forces the cache/fixture path; never the network |
| `FIRMS_PRODUCTS` | all four | `make cache` only | Which FIRMS products to download |
| `FIRMS_BBOX` | `88,20,93,27` | `make cache` only | Acquisition window, `west,south,east,north` |
| `FIRMS_START` / `FIRMS_END` | `2003-01-01` / `2026-09-30` | `make cache` only | Acquisition window |
| `EARTHDATA_TOKEN` | — | burned-area fetch | Earthdata Login bearer token, not a password |
| `VITE_DATA` | `mock` | frontend build | `mock` (bundled payloads) or `api` (live backend) |
| `VITE_API_BASE` | `/api/v1` | frontend build | Where the API lives, when `VITE_DATA=api` |

Copy `.env.example` to `.env` for local runs; `.env` is git-ignored. The `.env`
lives at the repository root, and Vite reads it from there (`web/vite.config.ts`
sets `envDir: '..'`), so `VITE_DATA=api` in the root `.env` reaches the
frontend build. A shell variable of the same name still wins, which is how the
Playwright suite forces the mock tier.

The API
reads no other environment variable: there is no `DATA_DIR`, `LOG_LEVEL` or
`DUCKDB_MEMORY`, and the cache always lives in `cache/` (the fixture in
`demo_fixtures/`).

---

## 4. Building the data cache (network required)

Run this **before** the event, on a machine with internet access.

```bash
# 1. Create the environment and install the pinned dependencies
make venv

# 2. Acquire raw files and write the per-product parquet under cache/raw/
make cache
```

`make cache` accepts arguments, so one product or one window at a time works:

```bash
make cache ARGS="--products VIIRS_SNPP_SP --start 2012-01-01"
```

The acquisition layer is resumable: a chunk already on disk is never
re-requested. Without a `FIRMS_MAP_KEY` it reads only from `cache/` and
`demo_fixtures/`, so an offline run is harmless.

To write the committed offline demo detections instead:

```bash
make fixture
```

---

## 5. Building the frontend

```bash
cd web
npm ci
npm run build        # typecheck + production build into web/dist/
```

`npm run build:release` is the release build: it refuses to ship on mock data
(`web/vite.config.ts`). Serve `web/dist/` with any static file server, or use
the Vite preview:

```bash
cd web && npm run preview      # :4173
```

---

## 6. Running

```bash
# Field / local run: the API offline against the local cache or fixture
make demo

# The frontend dev server, against the API above:
cd web && npm run dev           # :5174
```

- API: <http://127.0.0.1:8000>
- Health: `GET /health`
- Metadata: `GET /meta`
- Interactive docs: `/docs`

The frontend reads the bundled mock payloads by default. To point it at the
live API, build or serve it with `VITE_DATA=api` (and `VITE_API_BASE` if the
API is not on the same origin). The API allows the dev server (`:5174`) and
the preview server (`:4173`); both are loopback-only, with no wildcard.

---

## 7. Offline demo runbook (field / judging)

Goal: the demo works with the network off, from a cold start.

1. **Before the event:** complete §4 and §5, then confirm `cache/` (or
   `demo_fixtures/`) is populated and the frontend is built.
2. **Prime the browser cache:** open the app once online. The service worker
   registers on load and reports the resources the page used — the app shell,
   the hashed assets, and the nine mock payloads — so they are cached.
3. **Turn the network off:** disable Wi-Fi, or enable airplane mode.
4. **Cold start:** close the browser fully, reopen the app. The service worker
   serves the app shell and the cached payloads.
5. **Verify:** run the primary flow — select a preset AOI → series loads →
   calendar renders → anomaly panel → critical-period panel → provenance panel.
6. **Fallback:** if anything fails, play the recorded fallback video. Keep it on
   the same machine.

Record the cold-start time and any failure for the E9 experiment.

---

## 8. Health checks & smoke test

```bash
curl -s localhost:8000/health
curl -s localhost:8000/meta

curl -s -X POST localhost:8000/api/v1/series \
  -H 'content-type: application/json' \
  -d '{"aoi":"BGD","metric":"density"}'

curl -s 'localhost:8000/api/v1/export?aoi=BGD&start=2019-01-01&end=2019-12-31' \
  | head -3
```

Expected: 200 with a `params_hash` present in every body; an unknown AOI
returns 422 with `{code, message, field}`; an AOI over the cell limit returns
422 `aoi_too_large`; a request that overruns the timeout returns 503
`timeout`. The export answers `text/csv`, one row per detection.

A drawn area is sent as the `polygon` query parameter — a JSON list of
`[lon, lat]` pairs:

```bash
curl -s 'localhost:8000/api/v1/series?polygon=%5B%5B88.2,23.0%5D,%5B88.6,23.0%5D,%5B88.6,23.3%5D%5D'
```

The same ring may be posted as the AOI object `docs/TRD.md` §6.1 defines:
`{"aoi": {"type": "geojson", "geometry": {"type": "Polygon", "coordinates": [[[88.2,23.0],[88.6,23.0],[88.6,23.3]]]}}}`. The body wins over the query parameter.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `/meta` reports no years/streams | Cache not built, or only the fixture is present | Re-run §4; check that `cache/raw/` has parquet. |
| API returns 422 for a valid-looking AOI | Unknown AOI id, or the area covers more cells than the limit | Check the `field` in the error; the limit is `api.max_aoi_cells` in `config/params.yaml`. |
| Cold start fails offline | App shell not precached | Open once online and reload; check the service worker registered. |
| Frontend shows mock data, not the API | `VITE_DATA` is `mock` | Rebuild with `VITE_DATA=api`. |
| Browser blocks the API request | Origin not allowed | The API allows `:5174` and `:4173` only. |
| Results changed unexpectedly | `config/params.yaml` changed → new `params_hash` | Expected; the hash covers the file. |
| API slow / OOM | AOI too large | Lower the AOI cell count; the API caps it at `api.max_aoi_cells`. |
| 503 timeout | The request overran `api.request_timeout_s` | Expected above the bound; narrow the area or raise the timeout. |

---

## 10. Upgrade & rollback

- Change the code, rebuild the frontend, restart the API, then run the smoke
  test in §8.
- The API holds the dataset in memory for its lifetime, so a restart reloads
  it from disk. There is no database and no migration to run.
- A parameter change in `config/params.yaml` changes `params_hash`, so a
  cached response from before the change is distinguishable from one after.

---

## 11. Operational limits

- Read-only API; no writes, no schema migrations.
- One process is sufficient for field use; scale horizontally only for shared
  cloud access.
- Data refresh is a batch operation (`make cache`), not a live sync.
- The API never calls NASA: the acquisition step is separate and offline
  afterwards.
