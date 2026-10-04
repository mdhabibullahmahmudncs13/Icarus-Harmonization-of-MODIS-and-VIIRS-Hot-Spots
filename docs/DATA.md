# Data

Authoritative dataset list. Every dataset that reaches a number in the
interface is listed here with an id, the FIRMS sensor **product name**
(used verbatim) and a URL.

## Source

All fire detections come from **NASA FIRMS** (Fire Information for Resource
Management System), part of NASA LANCE / EOSDIS.

- Home: <https://firms.modaps.eosdis.nasa.gov/>
- Area API (what `src/acquire/firms.py` uses):
  <https://firms.modaps.eosdis.nasa.gov/api/area/>
- Bulk archive CSVs (for very long records; not used yet):
  <https://firms.modaps.eosdis.nasa.gov/download/>
- Data availability (confirm product start/end dates here before the demo):
  <https://firms.modaps.eosdis.nasa.gov/api/data_availability/>
- Free MAP_KEY: <https://firms.modaps.eosdis.nasa.gov/api/map_key/>

### Area API contract

```
GET /api/area/csv/[MAP_KEY]/[SOURCE]/[AREA_COORDINATES]/[DAY_RANGE]/[DATE]
```

- `AREA_COORDINATES` is `west,south,east,north` (or `world`).
- `DAY_RANGE` is **1..5**. Larger ranges are split into multiple calls, and
  larger transactions count as multiple requests.
- `DATE` (`YYYY-MM-DD`) is optional; without it the most recent data is
  returned.
- Limit: **5,000 transactions per 10-minute interval**.
- `src/acquire/firms.py` chunks a requested window into ≤5-day requests,
  throttles to the limit, and writes parquet. It is resumable: a chunk whose
  parquet already exists is never re-requested.

## Products used

`_SP` = standard processing (the archive, used for the historical record).
`_NRT` = near-real-time (recent days only).

| id | FIRMS product name | Sensor | Used for | License |
|----|--------------------|--------|----------|---------|
| `FIRMS_VIIRS_SNPP` | `VIIRS_SNPP_SP` | VIIRS 375 m, Suomi-NPP | Validation overlap only; the 2012–2018 stretch. **Download first — NASA stops serving it 1 Nov 2026** | NASA open data; free to use, attribute NASA FIRMS |
| `FIRMS_MODIS` | `MODIS_SP` | MODIS C6.1 (Terra + Aqua), 1 km | Raw + harmonized MODIS series | NASA open data; free to use, attribute NASA FIRMS |
| `FIRMS_VIIRS_NOAA20` | `VIIRS_NOAA20_SP` | VIIRS 375 m, NOAA-20 | Raw + harmonized VIIRS series (forward-looking) | NASA open data; free to use, attribute NASA FIRMS |
| `FIRMS_VIIRS_NOAA21` | `VIIRS_NOAA21_SP` | VIIRS 375 m, NOAA-21 | Raw + harmonized VIIRS series (forward-looking) | NASA open data; free to use, attribute NASA FIRMS |

Area of interest: Bangladesh bounding box `88,20,93,27` (west, south, east,
north). Configurable via `--bbox` / `FIRMS_BBOX`.

## Cache layout

`cache/` is gitignored. `make cache` populates it.

```
cache/raw/
  csv/<SOURCE>/<YYYYMMDD>.csv        raw Area API responses (re-run free)
  <SOURCE>/<YYYYMMDD>.parquet        one parquet per ≤5-day chunk
  <SOURCE>.parquet                   merged, sorted, de-duplicated product
  <SOURCE>.manifest.json             what was requested and what arrived
```

## Demo fixture (synthetic — not data)

`demo_fixtures/detections.parquet` is the offline fallback the API serves
when there is no cache and no `FIRMS_MAP_KEY` (`OFFLINE=1` forces it). It is
**synthetic**, generated deterministically by `python -m src.demo`
(`make fixture`) from `src/demo.py`: two calendar years, 2019-01-01 to
2020-12-31, with a MODIS-like and a VIIRS-like sensor over the same grid.
It is committed on purpose so a demo runs with no network and no key.

It is never evidence: the API reports `meta.source: "fixture"` on every
payload built from it, and the frontend shows the source badge. No number in
the interface may cite it as an observation. Regenerating it is byte-stable:
`python -m src.demo` reproduces the same file.

## To confirm before the demo

- Product **start/end dates** in `src/acquire/firms.py` (`PRODUCTS`) are the
  project's contract values, not yet verified against FIRMS. Check
  <https://firms.modaps.eosdis.nasa.gov/api/data_availability/> and update
  both this file and the table in that module.
- The exact **license/citation wording** for FIRMS before submission.
- Whether the ≤5-day chunked Area API is enough for the full 2003–2026
  record, or whether the bulk archive CSVs should be used for the earliest
  MODIS years. Current estimate: ~3,700 requests for the full four-product
  window (see `make cache` output), well inside the 5,000/10-minute limit.
