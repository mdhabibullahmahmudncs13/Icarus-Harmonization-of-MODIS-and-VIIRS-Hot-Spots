# Parameters

Every tunable value in Project Icarus lives in `config/params.yaml`. The hash of
that file is stored with every derived artifact, so changing any value
invalidates downstream outputs by design and makes any result reproducible.

Adding or changing a parameter means updating three places: `config/params.yaml`,
this document, and the sensitivity experiment it affects (see §4).

---

## 1. Full registry (defaults)

| Parameter | Default | Meaning | Section |
|-----------|---------|---------|---------|
| `K` | `20` | Cells per degree; `Δ = 1/K = 0.05°` | §5.4 |
| `c_min` | `30` | Minimum MODIS confidence (0–100) | §5.2 |
| `modis_allowed_types` | `[0]` | Allowed MODIS hot-spot types (null also allowed) | §5.2 |
| `viirs_classes` | `[n, h]` | Allowed VIIRS confidence classes | §5.2 |
| `fine_K` | `200` | Fine grid cells per degree for the static mask (~550 m) | §5.3 |
| `min_days` | `16` | Distinct-date threshold for the static mask | §5.3 |
| `bin_days` | `8` | Temporal bin width; yields 46 bins/year | §5.5 |
| `reference_family` | `[MOD_T, MOD_A]` | MODIS family used as the calibration target | §6 |
| `viirs_primary` | `VIIRS_SNPP` | Primary VIIRS stream | §6 |
| `viirs_extra` | `[VIIRS_N20, VIIRS_N21]` | Extra VIIRS streams (ingested, not default) | §6 |
| `cov_min` | `0.75` | Minimum coverage fraction (6 of 8 days) | §5.6 |
| `zero_detection_rule` | `true` | Zero detections ⇒ stream unavailable that day | §5.6 |
| `tile_deg` | `1` | Calibration tile size in degrees (20 × 20 cells) | §6 |
| `kappa` | `50` | Pseudo-count for calibration shrinkage | §6 |
| `min_overlap_bins_per_year` | `30` | Minimum overlap bins for a year to count | §6 |
| `min_overlap_years` | `5` | Minimum overlap years for calibration to apply | §6 |
| `bootstrap_B` | `200` | Bootstrap resample draws | §6 |
| `bootstrap_seed` | `20260101` | Bootstrap random seed (determinism) | §6 |
| `scale` | `1000` | Anomaly scale constant in `ln(1 + 1000·D)` | §7 |
| `min_reference` | `8` | Minimum reference years per bin | §7 |
| `sigma_floor` | `0.1` | Minimum σ for the anomaly z-score | §7 |
| `smoothing` | `[0.25, 0.5, 0.25]` | Circular smoothing weights | §7 |
| `z_elevated` | `2.0` | Elevated anomaly threshold | §7 |
| `z_extreme` | `3.0` | Extreme anomaly threshold | §7 |
| `window_mass` | `0.80` | Critical-period mass threshold | §7 |
| `onset` | `0.10` | Onset cumulative fraction | §7 |
| `end` | `0.90` | End cumulative fraction | §7 |
| `min_mean_density` | `1e-5` | Minimum mean density to detect a season | §7 |
| `max_aoi_cells` | `100000` | Max cells per AOI request | §8 |
| `request_timeout_s` | `30` | API request timeout (seconds) | §8 |

---

## 2. Shape of `config/params.yaml`

```yaml
grid:
  K: 20                 # cells per degree -> 0.05 deg
quality:
  c_min: 30             # min MODIS confidence
  modis_allowed_types: [0]
  viirs_classes: [n, h]
mask:
  fine_K: 200
  min_days: 16
bins:
  bin_days: 8
calibration:
  reference_family: [MOD_T, MOD_A]
  viirs_primary: VIIRS_SNPP
  viirs_extra: [VIIRS_N20, VIIRS_N21]
  tile_deg: 1
  kappa: 50
  min_overlap_bins_per_year: 30
  min_overlap_years: 5
  bootstrap_B: 200
  bootstrap_seed: 20260101
coverage:
  cov_min: 0.75
  zero_detection_rule: true
anomaly:
  scale: 1000
  min_reference: 8
  sigma_floor: 0.1
  smoothing: [0.25, 0.5, 0.25]
  z_elevated: 2.0
  z_extreme: 3.0
season:
  window_mass: 0.80
  onset: 0.10
  end: 0.90
  min_mean_density: 1.0e-5
api:
  max_aoi_cells: 100000
  request_timeout_s: 30
```

The exact key layout is fixed by the pipeline; values shown are the defaults.

---

## 3. Hashing & versioning

- `config/params.yaml` is hashed to `data/meta/params.hash`.
- Every derived file and every API response carries the hash.
- Two runs with the same raw inputs and the same hash MUST produce byte-identical
  outputs (NFR-01).
- A hash change marks all downstream artifacts stale; regenerate with
  `run-all`.

---

## 4. Sensitivity mapping

Changing a default should be justified by the experiment that tests it.

| Parameter | Affects | Experiment |
|-----------|---------|------------|
| `c_min` | Detections retained; series and anomalies | E3 |
| `min_days` | Static-mask removal fraction | E4 |
| `K` | Cell size; cell-day counts | E6 (resolution), cell-size sweep |
| `kappa`, `tile_deg` | Calibration stability in sparse tiles | E2, E5 |
| `viirs_extra` | VIIRS inclusion | E7 |
| `bin_days` | Temporal resolution | E6 |
| `bootstrap_B`, `bootstrap_seed` | Uncertainty band | E2 |
| `z_elevated`, `z_extreme`, `sigma_floor` | Anomaly flags | E1 |
| `cov_min` | Which bins are scored | E2, E8 |

---

## 5. Rules

1. **No magic numbers in code.** Read every tunable from `params.yaml`.
2. **Document before you change.** A parameter change ships with an update to
   this file.
3. **Keep defaults honest.** Defaults are the published method's values; changing
   one changes the method.
4. **Seeds are fixed.** Never remove `bootstrap_seed`; determinism depends on it.
