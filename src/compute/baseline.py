"""Seasonal baseline — day-of-year percentiles across years (docs/TRD.md §5)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

import numpy as np


def doy(iso: str) -> int:
    """Day of year (1-366) for an ISO date string."""
    return date.fromisoformat(iso).timetuple().tm_yday


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile; 0.0 for an empty sequence.

    ``np.percentile``'s default interpolation is the same linear rule the
    project documented, and agrees with the hand-rolled version to ~1e-14.
    """
    if not values:
        return 0.0
    return float(np.percentile(np.asarray(values, dtype="float64"), q * 100))


def seasonal_baseline(
    series: Iterable[dict],
    value_key: str = "harm_total",
) -> list[dict]:
    """Percentile envelope per day of year, pooled across all years."""
    by_doy: dict[int, list[float]] = {}
    for row in series:
        by_doy.setdefault(doy(row["date"]), []).append(float(row[value_key]))

    out: list[dict] = []
    for d in range(1, 367):
        vals = by_doy.get(d, [])
        out.append(
            {
                "doy": d,
                "p05": round(percentile(vals, 0.05), 3),
                "p25": round(percentile(vals, 0.25), 3),
                "p50": round(percentile(vals, 0.50), 3),
                "p75": round(percentile(vals, 0.75), 3),
                "p95": round(percentile(vals, 0.95), 3),
            }
        )
    return out
