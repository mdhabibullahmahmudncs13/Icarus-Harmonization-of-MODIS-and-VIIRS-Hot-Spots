"""Seasonal baseline — day-of-year percentiles across years (docs/TRD.md §5)."""

from __future__ import annotations

import math
from datetime import date as _date
from typing import Iterable, Sequence


def doy(iso: str) -> int:
    """Day of year (1-366) for an ISO date string."""
    y, m, d = (int(p) for p in iso.split("-"))
    return _date(y, m, d).timetuple().tm_yday


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile; 0.0 for an empty sequence."""
    if not values:
        return 0.0
    s = sorted(float(v) for v in values)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = math.floor(pos)
    hi = min(math.ceil(pos), len(s) - 1)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


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
