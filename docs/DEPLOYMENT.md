# Deployment & Runbook

How to build, run, and operate Project Icarus, including the offline field demo.
The system is a single read-only FastAPI service plus a static frontend, backed
by a pre-fetched Parquet cache. See `docs/ARCHITECTURE.md` for the design.

---

## 1. Deployment model

One Docker image contains the API, the static frontend, and the data cache.
There is no server database and no runtime dependency on NASA.

Three supported targets:

| Target | Use | Notes |
|--------|-----|-------|
| Laptop | Field demo, judging | The API runs locally; no internet after cache. |
| Raspberry Pi | Local LAN server | Same image, ARM build. |
| Cloud VM | Shared access | Put behind TLS; still read-only. |

---

## 2. Prerequisites

- Docker 24+ (or Python 3.11+, Node 20+ for a source run).
- A pre-built data cache in `data/` (produced by stage S0; see §4).
- TLS termination if anyone other than localhost will reach the API.

---

## 3. Configuration

Environment variables (names only — never commit values):

| Variable | Default | Purpose |
|----------|---------|---------|
| `FIRMS_MAP_KEY` | — | NASA FIRMS key; **S0 only**, not needed at runtime |
| `PORT` | `8000` | API port |
| `DATA_DIR` | `data/` | Path to the data cache |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |
| `DUCKDB_MEMORY` | `2GB` | DuckDB memory limit |

Copy `.env.example` to `.env` for local runs; `.env` is git-ignored.

---

## 4. Building the data cache (S0, network required)

Run this **before** the event, on a machine with internet access.

```bash
# 1. Acquire raw files and write the checksum manifest
python -m icarus.pipeline.cli s0 --config config/params.yaml

# 2. Run the full pipeline S1–S9
python -m icarus.pipeline.cli run-all --config config/params.yaml
```

S0 writes `data/raw/**` plus `data/manifest.csv` (file, bytes, sha256, rows,
retrieved, url). It is resumable: a file already registered with a matching
checksum is never re-requested. Verify integrity with:

```bash
python -m icarus.pipeline.cli verify-manifest --config config/params.yaml
```

Derived outputs are written under `data/derived/`; `data/meta/params.hash`
records the parameter set that produced them.

> **Data is never modified after acquisition.** `data/raw/` is append-only.

---

## 5. Building the image

```bash
docker build -f docker/Dockerfile -t icarus:latest .
```

The build runs from a clean checkout, installs pinned dependencies, and packages
the frontend. The container runs as a non-root user and mounts `data/`
read-only.

---

## 6. Running

```bash
# Field / local run
docker run --rm -p 8000:8000 \
  -v "$PWD/data:/app/data:ro" \
  --env-file .env \
  icarus:latest
```

- API: <http://127.0.0.1:8000>
- Health: `GET /health`
- Metadata: `GET /meta`
- Interactive docs: `/docs`

For a source run without Docker:

```bash
make demo     # starts the API offline against the local cache
cd web && npm run dev
```

---

## 7. Offline demo runbook (field / judging)

Goal: the demo works with the network off, from a cold start.

1. **Before the event:** complete §4 and §5, then confirm `data/derived/` and
   `data/tiles/basemap_<region>.pmtiles` exist and the image is built.
2. **Prime the browser cache:** open the app once online and use the
   "Download for offline" screen to cache the region and layers. Confirm the
   per-layer "data last updated" timestamp is current.
3. **Turn the network off:** disable Wi-Fi, or enable airplane mode.
4. **Cold start:** close the browser fully, reopen the app. The service worker
   serves the app shell and cached data.
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
  -d '{"aoi":{"type":"preset","id":"BGD"},"metric":"density","view":"harmonized"}'
```

Expected: 200 with a `params_hash` present in every body; the invalid-AOI path
returns 422 with `{code, message, field}`.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `/meta` reports no years/streams | Cache not built or wrong `DATA_DIR` | Re-run §4; check the volume mount. |
| API returns 422 for a valid-looking AOI | Ring not closed, outside extent, or > 100,000 cells | Check the `field` in the error. |
| Cold start fails offline | App shell not precached | Open once online; re-run the offline download; check the service worker. |
| Map tiles missing offline | PMTiles not included in the image | Add `data/tiles/*.pmtiles` and rebuild. |
| Results changed unexpectedly | `params.yaml` changed → new hash | Expected; regenerate derived outputs. |
| API slow / OOM | AOI too large or `DUCKDB_MEMORY` too low | Lower the AOI cell count; raise `DUCKDB_MEMORY`. |
| 503 / AI panel missing | Optional AI layer not running | Expected; the layer hides itself and the core app is unaffected. |

---

## 10. Upgrade & rollback

- Build the new image, run the smoke test in §8, then swap.
- Keep the previous image tag until the new one passes the smoke test.
- A parameter change requires a full re-run of `run-all`; derived outputs are
  keyed by the parameter hash and regenerate deterministically.

---

## 11. Operational limits

- Read-only API; no writes, no schema migrations.
- One process is sufficient for field use; scale horizontally only for shared
  cloud access.
- Data refresh is a batch operation (S0 → S9), not a live sync.
