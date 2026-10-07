"""Harmonize MODIS and VIIRS hot spots onto a common grid.

The finer sensor detects more and smaller fires, so a raw daily count steps
up at the 2012 sensor transition. That step comes from the instrument, not
from the world. Collapsing same-day detections inside one grid cell to a
single *cell-day* removes it.

Deterministic and network-free. No LLM computes any number here.

Grid geometry
-------------
Detections are snapped by latitude and longitude onto uniform steps:

* ``deg_lat = cell_km / 111.0`` (111 km per degree of latitude).
* ``deg_lon = deg_lat / cos(reference_latitude)``, so an east-west cell is
  about ``cell_km`` wide at the region's representative latitude.

This is an approximation, not a geodesic: a single reference latitude keeps
the grid a clean partition and cells near the stated size over one region,
but cells shrink in the east-west direction away from that latitude. Chosen
for Bangladesh (centre ~23.5 N) and documented in ``docs/TRD.md`` §5.3.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd

from src.compute import schema
from src.compute.schema import MIN_CONFIDENCE, MODIS, VIIRS

#: Default grid cell size in kilometres (project doc default, configurable).
DEFAULT_CELL_KM = 5.5

#: Latitude in degrees per kilometre of latitude.
KM_PER_DEGREE = 111.0

#: Representative latitude for the east-west step. Bangladesh centre; the
#: region the project targets. Configurable on every function that grids.
REFERENCE_LATITUDE_DEG = 23.5

#: Half-width, in days, of the day-of-year window used for the baseline.
DEFAULT_WINDOW_DAYS = 7

_COS_FLOOR = 1e-6


# --------------------------------------------------------------------------
# Grid geometry
# --------------------------------------------------------------------------


def degrees_per_lat(cell_km: float = DEFAULT_CELL_KM) -> float:
    """Latitude step in degrees for a cell of ``cell_km`` kilometres."""
    if cell_km <= 0:
        raise ValueError(f"cell_km must be positive, got {cell_km}")
    return cell_km / KM_PER_DEGREE


def degrees_per_lon(
    cell_km: float = DEFAULT_CELL_KM,
    reference_latitude_deg: float = REFERENCE_LATITUDE_DEG,
) -> float:
    """Longitude step in degrees, widened by cos(reference latitude)."""
    cosine = max(math.cos(math.radians(reference_latitude_deg)), _COS_FLOOR)
    return degrees_per_lat(cell_km) / cosine


def grid_index(
    latitude: float,
    longitude: float,
    cell_km: float = DEFAULT_CELL_KM,
    reference_latitude_deg: float = REFERENCE_LATITUDE_DEG,
) -> tuple[int, int]:
    """Return the ``(row, column)`` grid index for one coordinate."""
    row = math.floor(latitude / degrees_per_lat(cell_km))
    col = math.floor(longitude / degrees_per_lon(cell_km, reference_latitude_deg))
    return int(row), int(col)


def cell_id(row: int, col: int) -> str:
    """Stable string id for a grid cell."""
    return f"r{row:03d}c{col:03d}"


def parse_cell_id(value: str) -> tuple[int, int]:
    """Inverse of :func:`cell_id`. Raises ``ValueError`` on a malformed id."""
    text = str(value)
    if not text.startswith("r") or "c" not in text:
        raise ValueError(f"malformed cell id {value!r}")
    row_part, _, col_part = text[1:].partition("c")
    try:
        return int(row_part), int(col_part)
    except ValueError as exc:
        raise ValueError(f"malformed cell id {value!r}") from exc


def cell_bounds(
    value: str,
    cell_km: float = DEFAULT_CELL_KM,
    reference_latitude_deg: float = REFERENCE_LATITUDE_DEG,
) -> tuple[float, float, float, float]:
    """Return ``[west, south, east, north]`` in degrees for a cell id."""
    row, col = parse_cell_id(value)
    dlat = degrees_per_lat(cell_km)
    dlon = degrees_per_lon(cell_km, reference_latitude_deg)
    return (col * dlon, row * dlat, (col + 1) * dlon, (row + 1) * dlat)


def grid_cell_count(
    bbox: tuple[float, float, float, float],
    cell_km: float = DEFAULT_CELL_KM,
    reference_latitude_deg: float = REFERENCE_LATITUDE_DEG,
) -> int:
    """Number of grid cells covering ``bbox`` (west, south, east, north).

    The ``density`` metric divides a count by this figure, so it counts every
    cell the region touches — including cells that never see a detection —
    rather than the cells present in a detection table. A point exactly on a
    cell boundary belongs to the higher index (the same floor semantics as
    :func:`grid_index`), so both edges are included.
    """
    west, south, east, north = bbox
    if not (west < east and south < north):
        raise ValueError(f"bbox must satisfy west<east and south<north, got {bbox}")
    dlat = degrees_per_lat(cell_km)
    dlon = degrees_per_lon(cell_km, reference_latitude_deg)
    rows = math.floor(north / dlat) - math.floor(south / dlat) + 1
    cols = math.floor(east / dlon) - math.floor(west / dlon) + 1
    return int(rows * cols)


def to_grid(
    df: pd.DataFrame,
    cell_km: float = DEFAULT_CELL_KM,
    reference_latitude_deg: float = REFERENCE_LATITUDE_DEG,
) -> pd.DataFrame:
    """Add ``cell_row``, ``cell_col`` and ``cell_id`` to each detection.

    One row per detection; nothing is collapsed here. The input must carry
    ``latitude`` and ``longitude``.
    """
    frame = df.copy()
    if frame.empty:
        frame["cell_row"] = pd.Series(dtype="int64")
        frame["cell_col"] = pd.Series(dtype="int64")
        frame["cell_id"] = pd.Series(dtype="object")
        return frame
    for column in ("latitude", "longitude"):
        if column not in frame.columns:
            raise ValueError(f"detections are missing required column {column!r}")
    dlat = degrees_per_lat(cell_km)
    dlon = degrees_per_lon(cell_km, reference_latitude_deg)
    frame["cell_row"] = np.floor(frame["latitude"].astype(float) / dlat).astype("int64")
    frame["cell_col"] = np.floor(frame["longitude"].astype(float) / dlon).astype("int64")
    frame["cell_id"] = [
        cell_id(row, col)
        for row, col in zip(frame["cell_row"].tolist(), frame["cell_col"].tolist(), strict=True)
    ]
    return frame


# --------------------------------------------------------------------------
# Harmonization
# --------------------------------------------------------------------------


def harmonize(
    df: pd.DataFrame,
    cell_km: float = DEFAULT_CELL_KM,
    min_confidence: float = MIN_CONFIDENCE,
    reference_latitude_deg: float = REFERENCE_LATITUDE_DEG,
) -> pd.DataFrame:
    """Return detections normalized, confidence-filtered and snapped to the grid.

    Applies, in order:

    1. :func:`src.compute.schema.normalize` — one schema, VIIRS confidence
       mapped to numeric, ``sensor_family`` tagged.
    2. the ``min_confidence`` filter on that numeric column;
    3. :func:`to_grid` — ``cell_id`` per detection.
    """
    detections = schema.normalize(df)
    if detections.empty:
        return detections
    detections = detections[detections["confidence_num"] >= min_confidence].copy()
    detections = to_grid(detections, cell_km, reference_latitude_deg)
    return detections.reset_index(drop=True)


def collapse_cell_days(df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per ``(cell, day)`` — the cell-day table.

    ``raw_detections`` counts the detections that collapsed into the
    cell-day; ``sensors_agreeing`` counts distinct sensor families, so a
    same-day MODIS + VIIRS hit in one cell is recorded as two sensors
    agreeing rather than two fires.
    """
    frame = df.copy()
    if frame.empty:
        return frame
    frame["date"] = frame["acq_date"].dt.normalize()
    grouped = (
        frame.groupby(["date", "cell_id"], as_index=False)
        .agg(
            raw_detections=("cell_id", "size"),
            sensors_agreeing=("sensor_family", "nunique"),
        )
        .sort_values(["date", "cell_id"], kind="stable")
    )
    return grouped.reset_index(drop=True)


# --------------------------------------------------------------------------
# Series
# --------------------------------------------------------------------------


def raw_series(df: pd.DataFrame) -> pd.Series:
    """Count every detection per day, indexed by date.

    Pass a :func:`harmonize` table so the confidence filter is already
    applied; the count is then "detections that pass the filter", matching
    the reference implementation.
    """
    if df.empty:
        return pd.Series(dtype="int64", name="raw")
    dates = df["acq_date"].dt.normalize()
    series = dates.groupby(dates).size()
    series.index.name = "date"
    return series.rename("raw").astype("int64")


def harmonized_series(df: pd.DataFrame) -> pd.Series:
    """Count distinct cell-days per day, indexed by date."""
    if df.empty:
        return pd.Series(dtype="int64", name="harmonized")
    dates = df["acq_date"].dt.normalize()
    series = df.assign(date=dates).groupby("date")["cell_id"].nunique()
    series.index.name = "date"
    return series.rename("harmonized").astype("int64")


def daily_series(detections: pd.DataFrame) -> pd.DataFrame:
    """Daily counts in the API contract's shape.

    Returns the columns ``date, raw_modis, raw_viirs, raw_total,
    harm_modis, harm_viirs, harm_total`` — one row per day that has any
    detection.
    """
    columns = [
        "date",
        "raw_modis",
        "raw_viirs",
        "raw_total",
        "harm_modis",
        "harm_viirs",
        "harm_total",
    ]
    if detections.empty:
        return pd.DataFrame(columns=columns)

    frame = detections.copy()
    frame["date"] = frame["acq_date"].dt.normalize()
    days = pd.Index(sorted(frame["date"].unique()), name="date")
    out = pd.DataFrame(index=days)

    for family, key in ((MODIS, "modis"), (VIIRS, "viirs")):
        subset = frame[frame["sensor_family"] == family]
        out[f"raw_{key}"] = subset.groupby("date").size()
        out[f"harm_{key}"] = subset.groupby("date")["cell_id"].nunique()

    out["raw_total"] = frame.groupby("date").size()
    out["harm_total"] = frame.groupby("date")["cell_id"].nunique()
    out = out[columns[1:]].fillna(0).astype("int64").reset_index()
    return out[columns]


def family_daily_frames(detections: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Per-family daily frames with ``raw`` and ``harmonized`` columns.

    Used by the overlap validation: MODIS and VIIRS are compared
    sensor-to-sensor, so each needs its own raw and harmonized series.
    """
    out: dict[str, pd.DataFrame] = {}
    for family, key in ((MODIS, "modis"), (VIIRS, "viirs")):
        subset = detections[detections["sensor_family"] == family] if not detections.empty else detections
        frame = pd.DataFrame(
            {
                "raw": raw_series(subset),
                "harmonized": harmonized_series(subset),
            }
        )
        frame.index.name = "date"
        out[key] = frame
    return out


# --------------------------------------------------------------------------
# Seasonal baseline and anomaly
# --------------------------------------------------------------------------


def _by_doy(series: pd.Series) -> dict[int, list[float]]:
    cleaned = series.dropna()
    buckets: dict[int, list[float]] = {}
    for date, value in cleaned.items():
        buckets.setdefault(int(date.dayofyear), []).append(float(value))
    return buckets


def _window_doys(doy: int, window_days: int) -> list[int]:
    """Circular day-of-year window, so late December sees early January."""
    if window_days <= 0:
        return [doy]
    return sorted({((doy - 1 + offset) % 366) + 1 for offset in range(-window_days, window_days + 1)})


def doy_range(doy: int, window_days: int) -> tuple[int, int]:
    """Non-circular ``[start, end]`` day-of-year window, clamped to 1..366."""
    start = max(1, doy - window_days)
    end = min(366, doy + window_days)
    return start, end


def _window_values(buckets: dict[int, list[float]], doy: int, window_days: int) -> list[float]:
    values: list[float] = []
    for candidate in _window_doys(doy, window_days):
        values.extend(buckets.get(candidate, []))
    return values


def seasonal_baseline(series: pd.Series, window_days: int = DEFAULT_WINDOW_DAYS) -> pd.Series:
    """Median of the daily series for each day of year.

    Each day-of-year is estimated from every year in ``series`` inside a
    circular +/- ``window_days`` window, so neighbouring days reinforce the
    estimate. Indexed 1..366.
    """
    buckets = _by_doy(series)
    values = {
        doy: (float(np.median(window)) if (window := _window_values(buckets, doy, window_days)) else float("nan"))
        for doy in range(1, 367)
    }
    return pd.Series(values, name="p50")


def baseline_percentiles(
    series: pd.Series,
    window_days: int = DEFAULT_WINDOW_DAYS,
    quantiles: Sequence[float] = (0.05, 0.25, 0.5, 0.75, 0.95),
) -> pd.DataFrame:
    """Day-of-year percentiles in the API contract's shape.

    Returns a frame indexed by ``doy`` with one column per quantile
    (``p05``..``p95``). Missing quantiles for a day with no data are ``NaN``
    and the caller decides how to present that.
    """
    buckets = _by_doy(series)
    labels = [f"p{round(q * 100):02d}" for q in quantiles]
    rows: dict[int, dict[str, float]] = {}
    for doy in range(1, 367):
        window = _window_values(buckets, doy, window_days)
        if window:
            values = np.percentile(np.asarray(window, dtype="float64"), [q * 100 for q in quantiles])
            rows[doy] = dict(zip(labels, (float(v) for v in values), strict=True))
        else:
            rows[doy] = dict.fromkeys(labels, float("nan"))
    frame = pd.DataFrame.from_dict(rows, orient="index")
    frame.index.name = "doy"
    return frame[labels]


def years_used(series: pd.Series) -> int:
    """Distinct calendar years contributing to a series."""
    if series.empty:
        return 0
    return int(pd.Index(series.index.year).nunique())


def seasonal_window(
    series: pd.Series, date: pd.Timestamp, window_days: int = DEFAULT_WINDOW_DAYS
) -> pd.Series:
    """Every value from every year inside the circular +/-window around ``date``.

    The sample keeps its DatetimeIndex, so callers can also count the years
    contributing to the estimate (used by the anomaly percentiles).
    """
    doy = int(pd.Timestamp(date).dayofyear)
    keep = _window_doys(doy, window_days)
    if series.empty:
        return series.iloc[0:0]
    mask = series.index.dayofyear.isin(keep)
    return series[mask].dropna()


def anomaly_score(series: pd.Series, baseline: pd.Series, date: pd.Timestamp) -> float:
    """Standardized departure of ``date`` from its seasonal baseline.

    ``(value - baseline[doy]) / sd`` where ``sd`` is the sample standard
    deviation of the same day-of-year window across years. Positive is above
    the baseline. Returns ``NaN`` when the value or the spread is undefined.
    """
    stamp = pd.Timestamp(date)
    doy = int(stamp.dayofyear)
    try:
        value = float(series.loc[stamp])
    except KeyError:
        return float("nan")
    if doy not in baseline.index:
        return float("nan")
    central = float(baseline.loc[doy])
    window = seasonal_window(series, stamp, DEFAULT_WINDOW_DAYS).to_numpy(dtype="float64")
    if len(window) < 2:
        return float("nan")
    spread = float(np.std(window, ddof=1))
    if spread == 0:
        return 0.0
    return (value - central) / spread


# --------------------------------------------------------------------------
# Overlap correlation (low level)
# --------------------------------------------------------------------------


def _pearson(a: pd.Series, b: pd.Series) -> float:
    joined = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(joined) < 2:
        return float("nan")
    left = joined.iloc[:, 0].to_numpy(dtype="float64")
    right = joined.iloc[:, 1].to_numpy(dtype="float64")
    if left.std() == 0 or right.std() == 0:
        return float("nan")
    return float(np.corrcoef(left, right)[0, 1])


def overlap_correlation(
    modis: pd.DataFrame,
    viirs: pd.DataFrame,
) -> tuple[float, float]:
    """Return ``(raw_corr, harmonized_corr)`` for MODIS against VIIRS.

    Each argument is one sensor's daily frame with columns ``raw`` and
    ``harmonized`` indexed by date (see :func:`family_daily_frames`). One
    ``pd.Series`` cannot carry both the raw and the harmonized values, so the
    stub's Series signature was unworkable; nothing else consumed it.
    """
    for name, frame in (("modis", modis), ("viirs", viirs)):
        missing = [c for c in ("raw", "harmonized") if c not in frame.columns]
        if missing:
            raise ValueError(f"{name} frame is missing columns {missing}")
    return (
        _pearson(modis["raw"], viirs["raw"]),
        _pearson(modis["harmonized"], viirs["harmonized"]),
    )


__all__: Iterable[str] = (
    "DEFAULT_CELL_KM",
    "DEFAULT_WINDOW_DAYS",
    "REFERENCE_LATITUDE_DEG",
    "anomaly_score",
    "baseline_percentiles",
    "cell_bounds",
    "cell_id",
    "collapse_cell_days",
    "daily_series",
    "degrees_per_lat",
    "degrees_per_lon",
    "doy_range",
    "family_daily_frames",
    "grid_cell_count",
    "grid_index",
    "harmonize",
    "harmonized_series",
    "overlap_correlation",
    "parse_cell_id",
    "raw_series",
    "seasonal_baseline",
    "seasonal_window",
    "to_grid",
    "years_used",
)
