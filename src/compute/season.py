"""Critical fire period (docs/TRD.md §5.9).

The seasonal profile m(b) is the mean over years of activity in bin b. Onset is
the first bin whose cumulative share reaches 10%; end the first reaching 90%;
peak the argmax. The window is [onset-1, end+1] and its mass is reported.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .baseline import doy
from .series_util import bin_of_doy

BIN_DAYS = 8
ONSET = 0.10
END = 0.90
MIN_MEAN_DENSITY = 1e-5


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def critical_period(
    series: Iterable[dict],
    value_key: str = "harm_total",
    bin_days: int = BIN_DAYS,
    onset: float = ONSET,
    end: float = END,
    min_mean_density: float = MIN_MEAN_DENSITY,
) -> dict:
    """Onset, peak, end and window mass for the seasonal profile."""
    per_year: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for row in series:
        year = int(row["date"][:4])
        per_year[year][bin_of_doy(doy(row["date"]), bin_days)] += float(row[value_key])

    years = sorted(per_year)
    profile = [
        _mean([per_year[y].get(b, 0.0) for y in years]) if years else 0.0
        for b in range(1, 47)
    ]
    total = sum(profile)

    insufficient = total <= 0 or (total / (46 * bin_days)) < min_mean_density
    if insufficient:
        return {
            "insufficient_activity": True,
            "onset_bin": None,
            "peak_bin": None,
            "end_bin": None,
            "window": None,
        }

    cum = 0.0
    onset_bin: int | None = None
    end_bin: int | None = None
    for i, value in enumerate(profile):
        cum += value
        if onset_bin is None and cum / total >= onset:
            onset_bin = i + 1
        if end_bin is None and cum / total >= end:
            end_bin = i + 1
    peak_bin = max(range(46), key=lambda i: profile[i]) + 1

    start = max((onset_bin or 1) - 1, 1)
    end_clamped = min((end_bin or 46) + 1, 46)
    mass = sum(profile[start - 1 : end_clamped]) / total

    return {
        "insufficient_activity": False,
        "onset_bin": onset_bin,
        "peak_bin": peak_bin,
        "end_bin": end_bin,
        "window": {"start_bin": start, "end_bin": end_clamped, "mass": round(mass, 4)},
    }
