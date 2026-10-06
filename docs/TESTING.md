# Testing

Verification asks *did we build the software to spec?* Validation asks *is the
harmonized calendar a better description of burning than the raw record?* This
document covers both. Peak requirements: `DOCS/TRD.md`, `docs/PARAMETERS.md`.

---

## 1. Test pyramid

| Level | What it proves | Where |
|-------|----------------|-------|
| Unit | A single function is correct at its edges | `tests/unit/` |
| Property | Invariants hold for arbitrary input | `tests/property/` |
| Golden-file | A whole stage reproduces a known output | `tests/golden/` |
| Contract | The API matches the JSON schema | `tests/e2e/` |
| End-to-end | The full pipeline + offline frontend work | `tests/e2e/`, `web/e2e/` |

Every pipeline stage ships with at least one test.

---

## 2. Running the tests

```bash
make lint          # ruff check
make test          # pytest -q

cd web && npm test # frontend unit tests
cd web && npx playwright test   # browser / offline tests
```

CI runs lint + tests on every push (`.github/workflows/ci.yml`).

---

## 3. Unit tests

Required coverage of edge cases:

- **Grid snapping:** cell boundaries, negative coordinates, exact-boundary
  detections (floor semantics → higher index), longitude wrap in [−180, 180).
- **Quality filter:** confidence 29 vs 30; MODIS `hs_type` null / 0 / 2 / 3;
  VIIRS classes l / n / h.
- **Binning:** day-of-year 1, 8, 9, 365, 366 → bins 1, 1, 2, 46, 46.
- **Coverage:** full, partial, and zero availability; outage in a bin.
- **Calibration:** `V(t, m) = 0` falls back to the regional ratio; shrinkage
  behaviour as counts grow.
- **Anomaly:** `sigma_floor` used when variance is near zero; target year
  excluded from its own baseline; insufficient reference → `not_scored`.
- **Critical period:** onset/peak/end on a known shape; "insufficient activity"
  below the density floor.

---

## 4. Property tests

Invariants that must hold for arbitrary input:

1. **Idempotence.** Re-running S5 on its own output produces identical output.
2. **Row-order invariance.** Shuffling input rows does not change cell-day
   counts.
3. **Duplicate tolerance.** Adding duplicate detections to the same cell-day
   does not increase the cell-day presence count.
4. **Monotonicity.** With fewer detections, the raw count never increases.
5. **Sum coherence.** Calibrated values sum across cells (multiplicative model
   keeps AOI aggregation additive).

---

## 5. Golden-file tests

- Input: synthetic detections from the generator (§6).
- Expected: a versioned golden file per stage in `tests/golden/`.
- A golden file changes only with a deliberate, reviewed parameter change —
  which also changes the parameter hash.

Regenerate intentionally:

```bash
python -m tests.gen_golden --config config/params.yaml
```

Never regenerate to make a failing test pass without understanding why it
changed.

---

## 6. Synthetic data generator

Runs the pipeline end-to-end with no NASA download.

Inputs: extent, years, streams, fire-intensity distribution, seasonality,
per-sensor detection probability and false-positive rate.

Algorithm (per cell, year):

1. Base fire probability from the climatological mean for the month.
2. For each day: draw `U ~ Uniform(0,1)`; if `U < P_fire`, a fire occurs.
3. Detection count from `Poisson(λ)` where `λ` tracks fire size.
4. Place detections uniformly within the cell footprint.
5. Assign FRP from a log-normal by fire-size class.
6. Apply higher detection probability to VIIRS (smaller fires), lower to MODIS.
7. Inject outages as zero detections.
8. Inject a known step change at the VIIRS start year (2012) for harmonization
   tests.

Output: synthetic `det.parquet` matching the normalized detection schema.

---

## 7. Contract & API tests

- Every endpoint is called and the response validated against the exported JSON
  Schema.
- Mock payloads and live/fixture payloads pass the same schema.
- Required assertions:
  - Every response includes `params_hash`.
  - Invalid AOI → HTTP 422 with `{code, message, field}`.
  - `/api/v1/series` bins carry `coverage` and `source`.
  - `source ∈ {MODIS, BRIDGE, VIIRS_CAL, NONE}`.
- The schema is the single source of truth; fix shape differences in code, never
  by loosening the schema.

---

## 8. End-to-end tests

1. **Full pipeline** on synthetic data from S0-input fixture through S9.
2. **Offline frontend:** block all external hosts; the app must load and work,
   and the offline cold start must succeed from the service worker.
3. **Toggle/verification:** the views respond to the selected mode without a
   refetch.

---

## 9. Validation experiments (E1–E9)

Validation is pre-registered: design, metric, and decision rule are fixed before
running. All experiments execute with a stored parameter hash; each result ships
with a figure, a table, and limitation notes.

| ID | Question | Decision rule |
|----|----------|---------------|
| E1 | Step-change detection | Artificial cell-day step at the VIIRS join shrinks after harmonization. |
| E2 | Calibration residual offset | Calibrated median \|offset\| below the ceiling over leave-one-year-out. |
| E3 | Sensitivity to quality threshold | Vary `c_min` {20,30,40,50}; report change in series and anomalies. |
| E4 | Static-mask sensitivity | Vary `min_days` {8,16,32}; report removal fraction and change. |
| E5 | Non-linear calibration diagnostics | Log-log and quantile mapping vs multiplicative at region level. |
| E6 | Temporal resolution | Daily / weekly / 8-day compared on anomalies and critical period. |
| E7 | VIIRS satellite inclusion | S-NPP only vs S-NPP + N20 + N21. |
| E8 | External validation | Harmonized density vs MCD64CMQ burned area; target r² > 0.5 at 0.25°. |
| E9 | Offline performance | Cold-start time, API latency, cache size, Lighthouse PWA score. |

Targets labelled "informative" are planning expectations, not claims. Report
negative results.

---

## 10. Fixtures policy

- Fixtures are **synthetic or a small versioned real excerpt** — never a full
  cache.
- Synthetic fixtures are byte-stable: the same generator run reproduces the
  same bytes.
- Any fixture used in the interface is labelled with its source; synthetic data
  is never presented as evidence.

---

## 11. CI gates

A change is not done until:

- [ ] `make lint` passes.
- [ ] `make test` passes (unit + property + golden + contract).
- [ ] Frontend `npm test` passes for UI changes.
- [ ] Offline/Playwright checks pass for frontend changes.

If a check cannot run in the environment, report it as a limitation — do not
skip or weaken it to go green.
