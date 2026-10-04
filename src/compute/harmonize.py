"""Stub harmonization functions.

These will be implemented in a later commit. The signatures and
docstrings are the contract that ``src/api/`` and the frontend will rely
on, so changing them is a breaking change.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def to_grid(df: pd.DataFrame, cell_km: float = 5.5) -> pd.DataFrame:
    """Snap detections to a regular grid and return the grid-cell table.

    Parameters
    ----------
    df:
        Detection rows. Expected columns (TBD): ``latitude``,
        ``longitude``, ``acq_date``, ``confidence`` (after the VIIRS
        mapping described in ``docs/METHODS.md``), ``instrument``.
    cell_km:
        Grid cell size in kilometres. Default 5.5 km. Must be > 0.

    Returns
    -------
    pandas.DataFrame
        One row per detection with a ``cell_id`` column added. Cell ids
        are stable strings derived from the snapped coordinates.
    """
    raise NotImplementedError("to_grid is a stub — see docs/METHODS.md")


def harmonize(df: pd.DataFrame, cell_km: float = 5.5) -> pd.DataFrame:
    """Return the harmonized detection table.

    Combines MODIS and VIIRS rows into a single comparable set: snaps to
    the grid (``to_grid``), maps VIIRS confidence to numeric, applies the
    confidence filter, and tags the sensor family (MODIS / VIIRS) for
    provenance.
    """
    raise NotImplementedError("harmonize is a stub — see docs/METHODS.md")


def raw_series(df: pd.DataFrame) -> pd.Series:
    """Return the raw daily series: count of all detections per day."""
    raise NotImplementedError("raw_series is a stub — see docs/METHODS.md")


def harmonized_series(df: pd.DataFrame) -> pd.Series:
    """Return the harmonized daily series: count of distinct cell-days per day."""
    raise NotImplementedError("harmonized_series is a stub — see docs/METHODS.md")


def seasonal_baseline(series: pd.Series) -> pd.Series:
    """Return the seasonal baseline indexed by day-of-year.

    The baseline is computed from the same calendar day across all years
    in ``series``. The exact estimator (rolling mean, climatology, etc.)
    is documented in ``docs/METHODS.md``.
    """
    raise NotImplementedError("seasonal_baseline is a stub — see docs/METHODS.md")


def anomaly_score(
    series: pd.Series, baseline: pd.Series, date: pd.Timestamp
) -> float:
    """Return how unusual ``date`` is relative to the seasonal baseline.

    Positive values mean above the baseline. The exact z-score definition
    lives in ``docs/METHODS.md``.
    """
    raise NotImplementedError("anomaly_score is a stub — see docs/METHODS.md")


def overlap_correlation(
    modis: pd.Series, viirs: pd.Series
) -> tuple[float, float]:
    """Return ``(raw_corr, harmonized_corr)`` over the MODIS/VIIRS overlap.

    The caller passes two *paired* series — one per sensor — that share a
    daily index on the overlap window. The function computes the
    correlation of the raw values and the correlation of the
    harmonized (distinct cell-days) values, and returns both so the methods
    panel can show the before/after.
    """
    raise NotImplementedError("overlap_correlation is a stub — see docs/METHODS.md")


__all__: Iterable[str] = (
    "anomaly_score",
    "harmonize",
    "harmonized_series",
    "overlap_correlation",
    "raw_series",
    "seasonal_baseline",
    "to_grid",
)