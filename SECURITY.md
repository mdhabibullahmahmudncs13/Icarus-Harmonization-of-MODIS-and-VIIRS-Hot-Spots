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

- **Environment variables only.** No credential is ever hardcoded, committed, or
  baked into a Docker image.
- `.env` is git-ignored. `.env.example` lists the required names with empty
  values.
- The only secret this project needs is a NASA **FIRMS API key**
  (`FIRMS_MAP_KEY`), used **only at stage S0** (acquisition). It is never needed
  by the API, the frontend, or the demo.
- If a key is exposed, rotate it at
  <https://firms.modaps.eosdis.nasa.gov/api/map_key/> and purge it from history.

Required environment variables (names only):

| Variable | Scope | Notes |
|----------|-------|-------|
| `FIRMS_MAP_KEY` | S0 only | NASA FIRMS Area API key |
| `PORT` | API | default 8000 |
| `DATA_DIR` | API | path to data cache |
| `LOG_LEVEL` | API | DEBUG/INFO/WARNING/ERROR |
| `DUCKDB_MEMORY` | API | default 2GB |

---

## 4. Application security controls

| Control | Implementation |
|---------|----------------|
| Read-only data | API mounts `data/` read-only; it cannot mutate source data. |
| Input validation | AOI geometry must be closed, ≥ 4 positions, within extent, non-self-intersecting, ≤ 100,000 cells. |
| Request bounding | Request size limits and a 30 s per-request timeout. |
| Structured errors | Invalid input returns HTTP 422 `{code, message, field}`; no stack traces to clients. |
| Log hygiene | Logs contain request path, duration, status — **not** user AOI geometries. |
| Transport | HTTPS with HSTS for any network communication. |
| Container | Runs as a non-root user; read-only data volume. |
| No auth by design | The API is read-only over public data; do not expose it as a general compute service. |

---

## 5. Threat model (summary)

| Threat | Mitigation |
|--------|------------|
| Key leakage via repo or image | Env-only secrets; `.env` ignored; S0-only usage. |
| Query resource exhaustion (huge AOI) | Cell-count cap + per-request timeout. |
| Malformed / hostile geometry | Full AOI validation before any query. |
| Path traversal via file names | Data paths are fixed by the pipeline; no user-supplied paths. |
| Prompt injection via the AI layer | AI layer reads API JSON only, cannot compute, and is hidden if unavailable. |
| Supply-chain risk in dependencies | Pinned deps; CI installs from a lock; no CDN at runtime. |
| Offline cache tampering | Caches are versioned and rebuilt from checksummed raw files. |

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
