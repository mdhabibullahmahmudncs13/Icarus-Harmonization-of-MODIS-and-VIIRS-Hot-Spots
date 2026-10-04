# Methods

## Cell size

TODO. Default grid cell 5.5 km, configurable. Describe the equal-area
projection (e.g. a 5.5 km cell at the latitude of Bangladesh) and the
h3/raster choice.

## Confidence filter

TODO. Apply only to detections with confidence >= 50, after mapping VIIRS
low/nominal/high to a numeric scale. Document the mapping.

## Collapse rule

TODO. The harmonized series is the count of distinct cell-days per day.
Document the tie-breaking rule when two sensors detect the same cell on
the same day.

## Validation: overlap correlation

TODO. On the MODIS / VIIRS overlap period report:
- correlation of raw MODIS vs raw VIIRS, and
- correlation of harmonized MODIS vs harmonized VIIRS.

The harmonized correlation should be higher than the raw correlation.

## Sensor retirement note

TODO. Suomi-NPP VIIRS data ends 1 Nov 2026 and MODIS is being retired. The
harmonized series therefore transitions to VIIRS-only (NOAA-20, NOAA-21)
after that point. Document the cutoff date and the expected discontinuity.