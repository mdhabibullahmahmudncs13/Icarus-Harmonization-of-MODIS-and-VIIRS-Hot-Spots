"""S8 multiplicative calibration (docs/TRD.md §5.6).

VIIRS is finer and detects more, smaller fires than MODIS, so an uncalibrated
VIIRS cell-day count is not comparable to a MODIS one. Calibration scales VIIRS
onto the MODIS reference:

    r(t, m)  = (M(t, m) + kappa * r_reg(m)) / (V(t, m) + kappa)      kappa = 50
    r_reg(m) = sum_t M(t, m) / sum_t V(t, m)

with ``t`` a 1-degree tile and ``m`` a calendar month, and ``M``/``V`` the
distinct cell-days each family observed there. The pseudo-count ``kappa``
shrinks a sparse tile toward the regional ratio, so a tile with almost no
VIIRS does not produce a wild factor; when a tile has no VIIRS at all the
factor is the regional ratio. Multiplicative keeps sums additive, so an AOI
value aggregates without recalibration.

Deterministic, network-free, no LLM.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import pandas as pd

#: Pseudo-count for the shrinkage (docs/PARAMETERS.md ``kappa``).
KAPPA = 50.0

#: Calibration tile size in degrees (docs/PARAMETERS.md ``tile_deg``).
TILE_DEG = 1.0

#: Factor used when a ratio is undefined (no MODIS or no VIIRS observed).
NEUTRAL_FACTOR = 1.0

_KEYS = ("tile_lat", "tile_lon", "month")


def tile_index(latitude: float, longitude: float, tile_deg: float = TILE_DEG) -> tuple[int, int]:
    """``(floor(lat / tile_deg), floor(lon / tile_deg))`` — the calibration tile."""
    if tile_deg <= 0:
        raise ValueError(f"tile_deg must be positive, got {tile_deg}")
    return (math.floor(latitude / tile_deg), math.floor(longitude / tile_deg))


def _cell_days(detections: pd.DataFrame) -> pd.DataFrame:
    """One row per detection with tile, month and a ``cell_day`` key."""
    if detections.empty:
        return pd.DataFrame(columns=[*_KEYS, "sensor_family", "cell_day"])
    missing = [c for c in ("latitude", "longitude", "sensor_family", "cell_id") if c not in detections.columns]
    if missing:
        raise ValueError(f"detections are missing required columns {missing}")
    frame = detections[["latitude", "longitude", "sensor_family", "cell_id"]].copy()
    if "acq_date" not in detections.columns:
        raise ValueError("detections are missing the required column 'acq_date'")
    dates = pd.to_datetime(detections["acq_date"], errors="coerce").dt.normalize()
    frame["month"] = dates.dt.month
    frame["tile_lat"] = (detections["latitude"] / TILE_DEG).apply(math.floor)
    frame["tile_lon"] = (detections["longitude"] / TILE_DEG).apply(math.floor)
    frame["cell_day"] = dates.astype("string") + "|" + frame["cell_id"].astype("string")
    return frame.dropna(subset=["month"])


def active_cell_days(detections: pd.DataFrame) -> pd.DataFrame:
    """Distinct MODIS and VIIRS cell-days per ``(tile, month)``.

    Returns a frame indexed by ``tile_lat, tile_lon, month`` with ``m_sum`` and
    ``v_sum``.
    """
    frame = _cell_days(detections)
    if frame.empty:
        return pd.DataFrame(columns=[*_KEYS, "m_sum", "v_sum"])
    counts = (
        frame.groupby([*_KEYS, "sensor_family"])["cell_day"].nunique().unstack("sensor_family")
    )
    out = pd.DataFrame(index=counts.index)
    out["m_sum"] = counts["MODIS"].fillna(0).astype("int64") if "MODIS" in counts else 0
    out["v_sum"] = counts["VIIRS"].fillna(0).astype("int64") if "VIIRS" in counts else 0
    return out.reset_index()


def regional_factor(counts: pd.DataFrame) -> dict[int, float]:
    """``r_reg(m)``: summed MODIS over summed VIIRS cell-days, per month."""
    if counts.empty:
        return {}
    grouped = counts.groupby("month")[["m_sum", "v_sum"]].sum()
    factors: dict[int, float] = {}
    for month, row in grouped.iterrows():
        factors[int(month)] = (
            float(row["m_sum"]) / float(row["v_sum"]) if row["v_sum"] else NEUTRAL_FACTOR
        )
    return factors


def tile_factors(
    detections: pd.DataFrame,
    *,
    kappa: float = KAPPA,
) -> dict[tuple[int, int, int], float]:
    """``r(t, m)`` for every tile and month with any activity."""
    counts = active_cell_days(detections)
    if counts.empty:
        return {}
    regional = regional_factor(counts)
    out: dict[tuple[int, int, int], float] = {}
    for row in counts.itertuples():
        month = int(row.month)
        r_reg = regional.get(month, NEUTRAL_FACTOR)
        v = float(row.v_sum)
        out[(int(row.tile_lat), int(row.tile_lon), month)] = (
            (float(row.m_sum) + kappa * r_reg) / (v + kappa) if (v or row.m_sum) else NEUTRAL_FACTOR
        )
    return out


def factor_by_month(detections: pd.DataFrame, *, kappa: float = KAPPA) -> dict[int, float]:
    """``r(m)`` at AOI scale: the factor to scale VIIRS onto MODIS for a month.

    Aggregating first and shrinking once is what keeps an AOI value additive:
    every VIIRS cell-day in the month and area is scaled by the same number.
    """
    counts = active_cell_days(detections)
    if counts.empty:
        return {}
    regional = regional_factor(counts)
    grouped = counts.groupby("month")[["m_sum", "v_sum"]].sum()
    factors: dict[int, float] = {}
    for month, row in grouped.iterrows():
        m_sum = float(row["m_sum"])
        v_sum = float(row["v_sum"])
        r_reg = regional.get(int(month), NEUTRAL_FACTOR)
        factors[int(month)] = (m_sum + kappa * r_reg) / (v_sum + kappa) if (v_sum or m_sum) else NEUTRAL_FACTOR
    return factors


def calibrate_viirs(value: float, factor: float) -> int:
    """Scale a VIIRS cell-day count onto the MODIS scale, as an integer."""
    if not math.isfinite(factor) or factor <= 0:
        factor = NEUTRAL_FACTOR
    return round(value * factor)


__all__: Iterable[str] = (
    "KAPPA",
    "NEUTRAL_FACTOR",
    "TILE_DEG",
    "active_cell_days",
    "calibrate_viirs",
    "factor_by_month",
    "regional_factor",
    "tile_factors",
    "tile_index",
)
