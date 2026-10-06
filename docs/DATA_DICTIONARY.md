# Data Dictionary

Datasets, schemas, and every derived field in Project Icarus. NASA data is the
evidence layer and is attributed throughout. Parameters referenced here are
defined in `docs/PARAMETERS.md`.

---

## 1. Source datasets

| Dataset | Role | Access route | Notes |
|---------|------|--------------|-------|
| MCD14ML (MODIS C6) | Primary long record; reference scale | UMD SFTP archive (monthly `.txt.gz`) | 200K–500K lines/month globally |
| VIIRS 375 m (Suomi-NPP) | Modern record; calibrated to MODIS | FIRMS archive / Area API (recent) | Confidence as classes [n, h, l] |
| VIIRS N20, N21 | Optional extra streams | FIRMS archive | Ingested, not used by default |
| MCD64CMQ | Independent validation reference | NASA LAADS DAAC | 0.25° burned area, hundredths of ha |

Source attribution: **NASA FIRMS / LANCE / EOSDIS** and **NASA LAADS DAAC**.
Every dataset that reaches a displayed number is listed here with its route.

---

## 2. Normalized detection schema (post-S1)

All sources are converted to this unified schema by S1.

| Field | Type | Description | Source mapping |
|-------|------|-------------|----------------|
| `acq_date` | DATE | Acquisition date (UTC) | `YYYYMMDD` (MODIS); date (VIIRS) |
| `acq_time` | TIME | Acquisition time (UTC) HH:MM | `HHMM` (MODIS); time (VIIRS) |
| `lon` | FLOAT | Longitude [−180, 180) | Longitude |
| `lat` | FLOAT | Latitude [−90, 90] | Latitude |
| `frp` | FLOAT | Fire Radiative Power (MW) | FRP; VIIRS may be null |
| `conf_num` | SMALLINT | MODIS confidence 0–100 | Confidence (MODIS) |
| `conf_class` | VARCHAR(1) | VIIRS class: l / n / h | Class (VIIRS) |
| `hs_type` | SMALLINT | MODIS type: 0 fire, 2 persistent, 3 urban | Type (MODIS) |
| `instrument` | ENUM | MODIS or VIIRS | Derived from source |
| `sat` | ENUM | Terra (T), Aqua (A), S-NPP, N20, N21 | Satellite id |
| `stream` | ENUM | MOD_T, MOD_A, VIIRS_SNPP, VIIRS_N20, VIIRS_N21 | Derived |
| `stream_bit` | INT | 1, 2, 4, 8, 16 for bitmask ops | Derived |

---

## 3. Stream definitions

| Stream | Bit | Instrument / satellite | Default config role |
|--------|-----|------------------------|---------------------|
| `MOD_T` | 1 | MODIS / Terra | MODIS reference family |
| `MOD_A` | 2 | MODIS / Aqua | MODIS reference family |
| `VIIRS_SNPP` | 4 | VIIRS / Suomi-NPP | Primary VIIRS stream |
| `VIIRS_N20` | 8 | VIIRS / NOAA-20 | Ingested, not used by default |
| `VIIRS_N21` | 16 | VIIRS / NOAA-21 | Ingested, not used by default |

---

## 4. Derived tables

| Table | Stage | Key columns |
|-------|-------|-------------|
| `det` | S1 | stream, instrument, sat, acq_date, acq_time, lon, lat, frp, conf_num, conf_class, hs_type, stream_bit |
| `det_ok` | S2 | Same as `det`, filtered rows only |
| `det_clean` | S3 | Same as `det_ok`, static cells removed |
| `cell_day` | S4–S5 | cell_x, cell_y, d, stream_mask, n_det, max_frp |
| `cell_bin` | S6 | cell_x, cell_y, yr, bin, tx, ty, mon, ad_modis, ad_mod_t, ad_mod_a, ad_snpp |
| `avail` | S7 | stream, d, available (0/1) |
| `bin_day` | S7 | d, yr, bin, t_ok, a_ok, v_ok |
| `bin_coverage` | S7 | yr, bin, n_days, avail_t, avail_a, both_frac, cov_modis, cov_viirs |
| `calib_factor` | S8 | tx, ty, mon, m_sum, v_sum, r |
| `calib_boot` | S8 | draw, tx, ty, mon, r |
| `cell_bin_h` | S9 | cell_x, cell_y, yr, bin, mon, h, source |

### 4.1 Field glossary

**`cell_day`**

| Column | Type | Description |
|--------|------|-------------|
| `cell_x` | INT | `floor(lon · K)` |
| `cell_y` | INT | `floor(lat · K)` |
| `d` | DATE | Acquisition date (UTC) |
| `stream_mask` | INT | Bitmask of streams present (bit_or of `stream_bit`) |
| `n_det` | INT | Count of raw detections in the cell-day |
| `max_frp` | DOUBLE | Maximum FRP in the cell-day |

**`cell_bin`**

| Column | Type | Description |
|--------|------|-------------|
| `cell_x`, `cell_y` | INT | Grid cell indices |
| `yr` | INT | Year |
| `bin` | INT | 8-day bin (1–46) |
| `tx`, `ty` | INT | Calibration tile indices (`floor(cell / 20)`) |
| `mon` | INT | Month of the bin's first day |
| `ad_modis` | INT | Active cell-days from the MODIS family (bits 1+2) |
| `ad_mod_t` | INT | Active cell-days from MOD_T |
| `ad_mod_a` | INT | Active cell-days from MOD_A |
| `ad_snpp` | INT | Active cell-days from VIIRS_SNPP |

**`bin_coverage`**

| Column | Type | Description |
|--------|------|-------------|
| `yr`, `bin` | INT | Year and bin |
| `n_days` | INT | Days in the bin |
| `avail_t`, `avail_a` | DOUBLE | Fraction of days Terra / Aqua available |
| `both_frac` | DOUBLE | Fraction of days both MODIS satellites available |
| `cov_modis` | DOUBLE | MODIS family coverage |
| `cov_viirs` | DOUBLE | VIIRS coverage |

**`calib_factor` / `calib_boot`**

| Column | Type | Description |
|--------|------|-------------|
| `tx`, `ty`, `mon` | INT | Tile and month stratum |
| `m_sum`, `v_sum` | DOUBLE | Summed MODIS / VIIRS active cell-days |
| `r` | DOUBLE | Multiplicative factor (calibrated / bootstrap draw) |
| `draw` | INT | Bootstrap draw index (calib_boot only) |

**`cell_bin_h`** (harmonized)

| Column | Type | Description |
|--------|------|-------------|
| `cell_x`, `cell_y` | INT | Grid cell indices |
| `yr` | INT | Year |
| `bin` | INT | 8-day bin (1–46) |
| `mon` | INT | Month of bin start |
| `h` | DOUBLE | Harmonized active cell-days (density 0–1) |
| `source` | VARCHAR | `MODIS` \| `BRIDGE` \| `VIIRS_CAL` \| `NONE` |

---

## 5. Source tagging logic

| `source` | Condition |
|----------|-----------|
| `MODIS` | `both_frac ≥ cov_min` — full MODIS constellation observed |
| `BRIDGE` | single MODIS stream observed with adequate coverage |
| `VIIRS_CAL` | VIIRS_SNPP observed with adequate coverage and calibration applied |
| `NONE` | no stream meets the coverage threshold |

---

## 6. Harmonized value formula

For each cell `c`, bin `b`, year `y`:

```
H(c, y, b) = MODIS cell-days             if both_frac ≥ cov_min
H(c, y, b) = q_s · A_s                   if single MODIS stream s with bridge factor
H(c, y, b) = r · A_VIIRS_SNPP            if VIIRS calibrated with factor r
H(c, y, b) = undefined (source = NONE)   otherwise
```

---

## 7. API response fields (glossary)

| Field | Description |
|-------|-------------|
| `params_hash` | Hash of the parameter set that produced the response |
| `aoi.id` / `aoi.n_cells` | Resolved AOI identifier and cell count |
| `metric` | `density` or `cell_days`. Under `density` every count is divided by the grid cells covering `meta.region.bbox`, so `harm_*` ∈ [0,1] is the active-cell fraction and `raw_*` is detections per cell (`$defs/densityPoint`); `cell_days` keeps the integer counts (`$defs/seriesPoint`) |
| `bin_days` | Days per bin (8) |
| `bins[].value` | Metric for the bin |
| `bins[].lo` / `bins[].hi` | 5th / 95th bootstrap percentiles |
| `bins[].coverage` | Bin coverage fraction |
| `bins[].source` | `MODIS` \| `BRIDGE` \| `VIIRS_CAL` \| `NONE` |
| `anomalies[].z` | Anomaly z-score |
| `anomalies[].percentile` | Mid-rank percentile |
| `anomalies[].flag` | `elevated` \| `extreme` \| `not_scored` |
| `onset_bin` / `peak_bin` / `end_bin` | Critical-period bins |
| `window.mass` | Cumulative mass inside the window |

---

## 8. Units and conventions

- Longitude in [−180, 180); latitude in [−90, 90].
- Grid cell = 0.05° (`K = 20`); area weight `w_c = cos(lat_c)`.
- Dates and times are UTC (`acq_date`, `acq_time`).
- FRP in megawatts (MW).
- Coverage fractions are 0–1.
- Bin index is 1–46; bin 46 contains 5 days (6 in a leap year).
