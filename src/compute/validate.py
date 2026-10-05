"""Validate harmonization on the MODIS / VIIRS overlap.

The evidence that harmonization worked: on the period where both sensors
observed, harmonized MODIS and harmonized VIIRS track each other more
closely than the raw counts do. Raw counts inflate because VIIRS sees more
and smaller fires; collapsing to cell-days removes that.

Deterministic, network-free, no LLM. ``docs/METHODS.md`` describes the
estimators; this module computes them.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from src.compute import harmonize, schema
from src.compute.grid import MODIS_MASK, VIIRS_MASK

#: Cell sizes, in km, swept to show the result is not an artefact of one grid.
DEFAULT_CELL_SIZES: tuple[float, ...] = (5.5, 11.0, 16.5, 22.0)


@dataclass(frozen=True)
class Correlation:
    """How two daily series relate over the overlap."""

    pearson: float
    spearman: float
    ratio: float

    def as_dict(self) -> dict[str, float]:
        return {"pearson": self.pearson, "spearman": self.spearman, "ratio": self.ratio}


@dataclass
class ValidationReport:
    """Everything the validation card shows."""

    overlap: tuple[date, date]
    raw: Correlation
    harmonized: Correlation
    cell_sweep: list[dict[str, float]] = field(default_factory=list)

    def as_dict(self) -> Mapping[str, object]:
        """Contract payload (``GET /api/validation``) without the meta block."""
        start, end = self.overlap
        return {
            "overlap": {"start": start.isoformat(), "end": end.isoformat()},
            "raw": self.raw.as_dict(),
            "harmonized": self.harmonized.as_dict(),
            "cell_sweep": list(self.cell_sweep),
        }


def correlation_stats(first: pd.Series, second: pd.Series) -> Correlation:
    """Pearson, Spearman and mean-ratio for two paired daily series.

    ``ratio`` is ``mean(second) / mean(first)``, so passing MODIS first and
    VIIRS second yields the VIIRS-to-MODIS inflation factor. Undefined
    quantities are ``NaN`` and the caller must not present them as numbers.
    """
    joined = pd.concat([first, second], axis=1, join="inner").dropna()
    if len(joined) < 2:
        return Correlation(float("nan"), float("nan"), float("nan"))
    left = joined.iloc[:, 0].to_numpy(dtype="float64")
    right = joined.iloc[:, 1].to_numpy(dtype="float64")

    pearson = float(np.corrcoef(left, right)[0, 1]) if left.std() and right.std() else float("nan")
    ranked = joined.rank(method="average").to_numpy(dtype="float64")
    spearman = (
        float(np.corrcoef(ranked[:, 0], ranked[:, 1])[0, 1])
        if ranked[:, 0].std() and ranked[:, 1].std()
        else float("nan")
    )
    first_mean = float(left.mean())
    ratio = float(right.mean() / first_mean) if first_mean else float("nan")
    return Correlation(pearson, spearman, ratio)


def family_date_range(
    detections: pd.DataFrame, family: str
) -> tuple[date, date] | None:
    """First and last day a sensor family has a detection, or ``None``."""
    if detections.empty:
        return None
    dates = detections.loc[detections["sensor_family"] == family, "acq_date"]
    if dates.empty:
        return None
    return (dates.min().date(), dates.max().date())


def overlap_window(detections: pd.DataFrame) -> tuple[date, date]:
    """The MODIS / VIIRS overlap: both sensors observing.

    The interval where both sensors have data, i.e. the later start and the
    earlier end. Raises ``ValueError`` when either sensor is absent or they
    do not overlap, because then there is nothing to validate.
    """
    modis = family_date_range(detections, schema.MODIS)
    viirs = family_date_range(detections, schema.VIIRS)
    if modis is None or viirs is None:
        raise ValueError("both MODIS and VIIRS detections are required for the overlap")
    start = max(modis[0], viirs[0])
    end = min(modis[1], viirs[1])
    if end < start:
        raise ValueError(f"sensors do not overlap: MODIS={modis}, VIIRS={viirs}")
    return start, end


def validate_overlap(
    detections: pd.DataFrame,
    *,
    cell_km: float = harmonize.DEFAULT_CELL_KM,
    cell_sizes: Sequence[float] = DEFAULT_CELL_SIZES,
    min_confidence: float = schema.MIN_CONFIDENCE,
    reference_latitude_deg: float = harmonize.REFERENCE_LATITUDE_DEG,
) -> ValidationReport:
    """Compare raw and harmonized MODIS/VIIRS agreement on the overlap.

    Raw agreement is grid-independent, so the sweep varies only the
    harmonized correlation — which is the point: the improvement should hold
    across cell sizes rather than depending on one tuned grid.
    """
    normalized = schema.normalize(detections)
    if normalized.empty:
        raise ValueError("no detections to validate")
    start, end = overlap_window(normalized)
    lo, hi = pd.Timestamp(start), pd.Timestamp(end)
    subset = normalized[(normalized["acq_date"] >= lo) & (normalized["acq_date"] <= hi)].copy()

    raw_modis = harmonize.raw_series(subset[subset["sensor_family"] == schema.MODIS])
    raw_viirs = harmonize.raw_series(subset[subset["sensor_family"] == schema.VIIRS])
    raw_correlation = correlation_stats(raw_modis, raw_viirs)

    def harmonized_stats(size: float) -> Correlation:
        gridded = harmonize.harmonize(
            subset,
            cell_km=size,
            min_confidence=min_confidence,
            reference_latitude_deg=reference_latitude_deg,
        )
        frames = harmonize.family_daily_frames(gridded)
        return correlation_stats(frames["modis"]["harmonized"], frames["viirs"]["harmonized"])

    sweep: list[dict[str, float]] = []
    for size in cell_sizes:
        stats = harmonized_stats(float(size))
        # A grid so coarse that a sensor's series collapses to a constant has
        # no defined correlation. Drop it rather than publish an undefined
        # number (the contract only accepts real values).
        if not (
            math.isfinite(stats.pearson) and math.isfinite(raw_correlation.pearson)
        ):
            continue
        sweep.append(
            {
                "cell_km": float(size),
                "raw_pearson": raw_correlation.pearson,
                "harmonized_pearson": stats.pearson,
            }
        )

    harmonized_correlation = harmonized_stats(float(cell_km))
    if not math.isfinite(raw_correlation.pearson):
        raise ValueError(
            "raw MODIS/VIIRS correlation is undefined on the overlap: "
            "at least one sensor has fewer than two varied days"
        )
    if not math.isfinite(harmonized_correlation.pearson):
        raise ValueError(
            f"harmonized correlation is undefined at {cell_km} km: "
            "at least one sensor has a constant series on the overlap"
        )

    return ValidationReport(
        overlap=(start, end),
        raw=raw_correlation,
        harmonized=harmonized_correlation,
        cell_sweep=sweep,
    )


# --------------------------------------------------------------------------
# List-based statistics: the cell-day / mock surface
# --------------------------------------------------------------------------


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Pearson's r for two paired lists; ``None`` when it is undefined.

    Undefined means fewer than two points, mismatched lengths, or a constant
    series in either argument — callers must not present ``None`` as a
    number (the contract only carries real values).
    """
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    syy = sum((y - mean_y) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    return sxy / math.sqrt(sxx * syy)


def ranks(values: Sequence[float]) -> list[float]:
    """Average ranks (ties share the mean position), as Spearman needs."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2.0
        for k in range(i, j + 1):
            out[order[k]] = average
        i = j + 1
    return out


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman's rho: Pearson correlation of the average ranks."""
    if len(xs) != len(ys):
        return None
    return pearson(ranks(xs), ranks(ys))


def overlap_validation(
    rows: Sequence[Mapping[str, Any]],
    transition: str | date | None = None,
) -> dict[str, Any]:
    """Raw vs harmonized agreement over the overlap, from daily series rows.

    ``rows`` carries the :func:`src.compute.grid.to_series` shape (``date``,
    ``raw_modis``, ``raw_viirs``, ``harm_modis``, ``harm_viirs``).
    ``transition`` is the VIIRS start date: rows before it are excluded,
    because there is no second sensor to compare against.

    Returns the contract's validation payload shape without ``meta``
    (``overlap`` / ``raw`` / ``harmonized`` / ``cell_sweep``). The sweep
    needs the cell geometry the daily rows do not carry, so it is left empty
    here — :func:`validate_overlap` computes it from the detections.
    """
    selected = list(rows)
    if transition is not None:
        cutoff = str(transition)
        selected = [row for row in selected if str(row["date"]) >= cutoff]

    def column(key: str) -> list[float]:
        return [float(row[key]) for row in selected]

    def block(prefix: str) -> dict[str, float | None]:
        modis = column(f"{prefix}_modis")
        viirs = column(f"{prefix}_viirs")
        total_modis = sum(modis)
        total_viirs = sum(viirs)
        ratio = total_modis / total_viirs if total_viirs else None
        r = pearson(modis, viirs)
        rho = spearman(modis, viirs)
        return {
            "pearson": round(r, 4) if r is not None else None,
            "spearman": round(rho, 4) if rho is not None else None,
            "ratio": round(ratio, 4) if ratio is not None else None,
        }

    years = sorted({int(str(row["date"])[:4]) for row in selected})
    return {
        "overlap": {"years": years, "n_days": len(selected)},
        "raw": block("raw"),
        "harmonized": block("harm"),
        "cell_sweep": [],
    }


def cell_sweep(
    cell_days: Iterable,
    *,
    factors: Sequence[int] = (1, 2, 4),
    cell_km: float = harmonize.DEFAULT_CELL_KM,
) -> list[dict[str, float]]:
    """Harmonized agreement as the grid coarsens; raw is grid-independent.

    Each cell-day is re-snapped to a grid ``factor`` times coarser and the
    per-day distinct-cell counts of the two sensors are correlated, which
    shows the improvement is not an artefact of one cell size. Raw counts are
    point data and do not aggregate, so ``raw_correlation`` is constant
    across the sweep. Undefined correlations (a constant series) count as
    0.0 rather than ``NaN``: the contract only carries real numbers.
    """
    items = list(cell_days)
    dates = sorted({cd.date for cd in items})

    raw_modis = dict.fromkeys(dates, 0.0)
    raw_viirs = dict.fromkeys(dates, 0.0)
    for cd in items:
        if cd.stream_mask & MODIS_MASK:
            raw_modis[cd.date] += cd.n_modis
        if cd.stream_mask & VIIRS_MASK:
            raw_viirs[cd.date] += cd.n_viirs
    raw_corr = pearson(
        [raw_modis[d] for d in dates], [raw_viirs[d] for d in dates]
    ) or 0.0

    sweep: list[dict[str, float]] = []
    for factor in factors:
        hit_modis = {d: set() for d in dates}
        hit_viirs = {d: set() for d in dates}
        for cd in items:
            cell = (cd.cell_x // factor, cd.cell_y // factor)
            if cd.stream_mask & MODIS_MASK:
                hit_modis[cd.date].add(cell)
            if cd.stream_mask & VIIRS_MASK:
                hit_viirs[cd.date].add(cell)
        corr = pearson(
            [len(hit_modis[d]) for d in dates],
            [len(hit_viirs[d]) for d in dates],
        ) or 0.0
        sweep.append(
            {
                "cell_km": round(cell_km * factor, 2),
                "raw_correlation": round(float(raw_corr), 4),
                "harmonized_correlation": round(float(corr), 4),
            }
        )
    return sweep


__all__: Iterable[str] = (
    "DEFAULT_CELL_SIZES",
    "Correlation",
    "ValidationReport",
    "cell_sweep",
    "correlation_stats",
    "family_date_range",
    "overlap_validation",
    "overlap_window",
    "pearson",
    "ranks",
    "spearman",
    "validate_overlap",
)
