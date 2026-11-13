# Security Policy

Project Icarus is a read-only analytical web application over public NASA fire
data. It stores no personal data and has no authentication. The security surface
is the read-only HTTP API, the data cache, and the build/deploy pipeline.

---

## 1. Supported versions

| Version | Supported |
|---------|-----------|
| `main` (active development) | Yes |
| Tagged releases (`1.x`) | Current minor only |

Pre-release / `0.x` builds are not supported for security fixes.

---

## 2. Reporting a vulnerability

Please report suspected vulnerabilities privately — do **not** open a public
issue.

- Email the maintainers (address published on the project page) with:
  reproduction steps, affected endpoint or file, and the impact you believe it
  has.
- You will get an acknowledgement within a few business days.
- We will confirm the issue, ship a fix on `main`, and credit you unless you ask
  otherwise.

Do not include real credentials in a report. Redact keys.

---

## 3. Secrets and credentials

- **Environment variables only.** No credential is ever hardcoded or committed.
- `.env` is git-ignored. `.env.example` lists the required names with empty
  values.
- The only secret this project needs is a NASA **FIRMS API key**
  (`FIRMS_MAP_KEY`), used **only at stage S0** (acquisition). It is never needed
  by the API, the frontend, or the demo.
- If a key is exposed, rotate it at
  <https://firms.modaps.eosdis.nasa.gov/api/map_key/> and purge it from history.
- **Never put an account password in `.env`.** The burned-area cross-check uses
  an Earthdata Login *bearer token* (`EARTHDATA_TOKEN`), which expires and can
  be revoked on its own. A password grants account-wide access and is the one
  credential with no safe home.
- `tests/test_secrets.py` fails the build if a credential-shaped literal
  appears in a tracked config file, and if `.env` is ever committed. It scans
  the project's own files only, not vendored third-party directories.

Required environment variables (names only):

| Variable | Scope | Notes |
|----------|-------|-------|
| `FIRMS_MAP_KEY` | acquisition only | NASA FIRMS Area API key |
| `EARTHDATA_TOKEN` | acquisition only | Earthdata Login bearer token, for the burned-area fetch |
| `OFFLINE` | acquisition, API | `1` forces the cache/fixture path and never the network |
| `VITE_DATA`, `VITE_API_BASE` | frontend build | Which data tier the built app uses, and where the API is |

The API reads no other environment variable. There is no `DATA_DIR`, no
`LOG_LEVEL` and no `DUCKDB_MEMORY`: the cache lives in `cache/`, the fixture
in `demo_fixtures/`, and the port is chosen on the uvicorn command line.

---

## 4. Application security controls

| Control | Implementation |
|---------|----------------|
| Read-only data | The API only reads the Parquet cache; nothing in the request path writes to it. |
| Input validation | An AOI is either a known preset id or a bbox of four degrees with `west<east` and `south<north`; an area over `api.max_aoi_cells` grid cells is refused before any query runs. |
| Request bounding | A 30 s per-request timeout, from `api.request_timeout_s`. |
| Structured errors | Invalid input returns HTTP 422 `{code, message, field}`; no stack traces to clients. |
| Origin restriction | CORS allows the loopback dev (`:5174`) and preview (`:4173`) origins only — no wildcard. |
| Transport | HTTPS is a deployment concern: terminate TLS in front of the API. The service itself speaks plain HTTP. |
| No auth by design | The API is read-only over public data; do not expose it as a general compute service. |

---

## 5. Threat model (summary)

| Threat | Mitigation |
|--------|------------|
| Key leakage via repo or image | Env-only secrets; `.env` ignored; acquisition-only usage. |
| Query resource exhaustion (huge AOI) | Cell-count cap + per-request timeout. |
| Malformed / hostile geometry | A bbox is parsed and range-checked before any query. |
| Path traversal via file names | Data paths are fixed by the pipeline; no user-supplied paths. |
| Supply-chain risk in dependencies | Pinned deps; CI installs from a lock; no CDN at runtime. |
| Offline cache tampering | The cache is rebuilt by `make cache`, which never re-requests a chunk already on disk. |

---

## 6. Data governance

- All fire detections come from **NASA FIRMS** and are attributed as such
  (see `docs/DATA_DICTIONARY.md`).
- The project stores no personal data and no user-identifying information.
- User AOI geometries are processed for the request only and are not logged or
  persisted.

---

## 7. Dependency and disclosure hygiene

- Keep dependencies pinned; review upgrades for CVEs before merging.
- Never weaken validation or add suppressions just to make a check pass.
- Security-relevant changes (validation, mounts, secrets handling) require
  review by a maintainer.
