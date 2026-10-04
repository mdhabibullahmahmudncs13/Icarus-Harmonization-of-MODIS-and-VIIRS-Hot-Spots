"""Answer "is this unusual for this place and this time of year".

Given a daily series and one date, report how the value ranks against the
same days in other years, the window used and how many years contributed.
Deterministic, network-free, no LLM.

This is the percentile-rank counterpart to
:func:`src.compute.harmonize.anomaly_score` (which returns a z-score). The
API contract's ``/api/anomaly`` needs a percentile and the baseline window,
which is what :func:`anomaly_report` returns.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from src.compute import harmonize

DEFAULT_WINDOW_DAYS = harmonize.DEFAULT_WINDOW_DAYS


def anomaly_report(
    series: pd.Series,
    date: pd.Timestamp | str,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict[str, Any]:
    """Rank one date against its day-of-year window.

    Returns the contract fields ``value`` and ``percentile`` (0-100, the
    share of same-window days at or below the value), plus ``date``,
    ``baseline_window``, ``doy_range`` and ``years_used``.

    ``value`` is ``NaN`` when the date is absent from the series, and
    ``percentile`` is ``NaN`` when no window sample exists; callers must not
    turn either into a number.
    """
    stamp = pd.Timestamp(date)
    doy = int(stamp.dayofyear)
    window = harmonize.seasonal_window(series, stamp, window_days)
    low, high = harmonize.doy_range(doy, window_days)

    value = float(series.loc[stamp]) if stamp in series.index else float("nan")
    if window.empty:
        percentile = float("nan")
        years = 0
    else:
        percentile = float((window.to_numpy() <= value).mean() * 100.0)
        years = int(pd.Index(window.index.year).nunique())

    return {
        "date": stamp.strftime("%Y-%m-%d"),
        "value": value,
        "percentile": percentile,
        "baseline_window": int(window_days),
        "doy_range": [int(low), int(high)],
        "years_used": years,
    }


def anomaly_payload(series: pd.Series, date: pd.Timestamp | str, window_days: int = DEFAULT_WINDOW_DAYS) -> Mapping[str, Any]:
    """Alias kept for readability at the call site."""
    return anomaly_report(series, date, window_days)


__all__: Iterable[str] = (
    "DEFAULT_WINDOW_DAYS",
    "anomaly_payload",
    "anomaly_report",
)
