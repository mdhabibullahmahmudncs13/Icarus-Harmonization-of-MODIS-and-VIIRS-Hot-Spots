# Datasets, AI use, and references

The provenance of every dataset the project reads, the project's policy on
machine learning, and the literature the method rests on. Field-level detail
lives in `docs/DATA_DICTIONARY.md`; the parameter registry is
`docs/PARAMETERS.md`.

---

## 1. Datasets

All inputs are NASA open data, fetched through the FIRMS API
(`https://firms.modaps.eosdis.nasa.gov/api/area/`) and cached locally by
`src/acquire`. No dataset is redistributed in this repository.

| Product | Sensor / resolution | Role here | Source |
|---------|--------------------|-----------|--------|
| `MODIS_SP` | MODIS C6.1 (Terra + Aqua), 1 km | Reference family for calibration; the pre-VIIRS record | FIRMS archive / Area API |
| `VIIRS_SNPP_SP` | VIIRS 375 m, Suomi-NPP | Primary VIIRS stream | FIRMS archive / Area API |
| `VIIRS_NOAA20_SP` | VIIRS 375 m, NOAA-20 | Extra VIIRS stream (ingested, not default) | FIRMS Area API |
| `VIIRS_NOAA21_NRT` | VIIRS 375 m, NOAA-21 | Extra VIIRS stream; NRT only — the Area API serves no `VIIRS_NOAA21_SP` | FIRMS Area API |
| `MCD64A1` v061 | MODIS 500 m monthly burned area | External validation (E8), regridded to 0.25°; not bundled, needs an Earthdata Login token | LP DAAC, via `earthaccess` |

**Attribution.** NASA FIRMS / LANCE / EOSDIS and NASA LAADS DAAC. FIRMS data
are free and open; cite them and the algorithm papers in §3.

**Known limitations carried from the data itself.**

- VIIRS detects more, smaller fires at 375 m than MODIS does at 1 km, so raw
  counts step up at the sensor join. That step is the phenomenon the project
  harmonizes; it is documented honestly in `docs/IMPLEMENTATION_PLAN.md` §6.1
  and measured in `docs/VALIDATION.md` (E1, E7).
- NOAA-21 is available only as a near-real-time (NRT) source, which may be
  revised upstream; it is labelled `VIIRS 375 m, NOAA-21 (NRT)` throughout.
- The 0.25° climate-modelling-grid burned-area product (MCD64CMQ) is not
  published to CMR, so it cannot be discovered by `earthaccess`. E8 therefore
  uses MCD64A1 v061 at 500 m and aggregates it to 0.25° itself.

---

## 2. AI use

- **Deterministic code performs all of the science.** Harmonization,
  calibration, the anomaly engine and the validation experiments are ordinary
  Python in `src/`, with no model in the path (`docs/ARCHITECTURE.md` ADR-7,
  `docs/PRD.md`).
- **No LLM touches a number.** If a language model is ever added, it only
  retrieves, orchestrates or explains; it never issues its own query and
  cannot alter a payload (`docs/SYSTEM_ARCHITECTURE.md`).
- **The validation report is computed, not narrated.** Every value in
  `docs/VALIDATION.md` comes from `src/validate/experiments.py`, run by
  `python -m tools.experiments`, and is guarded by `tests/test_experiments.py`.
- **Synthetic data is labelled.** The mock and demo fixtures are explicitly
  marked as such and are never presented as evidence
  (`docs/TESTING.md` §10; the release build refuses to ship on mock data).
- **Disclosure.** This repository's source and documentation were drafted with
  an AI coding assistant; correctness rests on the tests and gates, not on the
  assistant's word.

---

## 3. References

**Active fire — MODIS**

- Giglio, L., Schroeder, W., Justice, C. O. (2016). *The Collection 6 MODIS
  active fire detection algorithm and fire products.* Remote Sensing of
  Environment, 178, 31–41. https://doi.org/10.1016/j.rse.2016.02.054
- Giglio, L., Schroeder, W., Hall, J. V., Justice, C. O. (2021). *MODIS
  Collection 6 and Collection 6.1 Active Fire Product User's Guide*, Version
  1.4. NASA.

**Active fire — VIIRS 375 m**

- Schroeder, W., Oliva, P., Giglio, L., Csiszar, I. A. (2014). *The New VIIRS
  375 m active fire detection data product: algorithm description and initial
  assessment.* Remote Sensing of Environment, 143, 85–96.
  https://doi.org/10.1016/j.rse.2013.12.008
- Schroeder, W., Oliva, P., Giglio, L., Csiszar, I. A. (2017). *Visible
  Infrared Imaging Radiometer Suite (VIIRS) 375 m Active Fire Algorithm User's
  Guide*, Version 1.3. NASA / NOAA.

**Burned area — MODIS**

- Giglio, L., Boschetti, L., Roy, D. P., Humber, M. L., Justice, C. O. (2018).
  *The Collection 6 MODIS burned area mapping algorithm and product.* Remote
  Sensing of Environment, 217, 72–85.
  https://doi.org/10.1016/j.rse.2018.08.005

**Data distribution**

- Davies, D. K., Ilavajhala, S., Wong, M. M., Justice, C. O. (2009). *Fire
  Information for Resource Management System: Archiving and Distributing MODIS
  Active Fire Data.* IEEE Transactions on Geoscience and Remote Sensing, 47(1),
  72–79.
- NASA FIRMS — Fire Information for Resource Management System.
  https://firms.modaps.eosdis.nasa.gov/
