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

#: Minimum reference years before a date is scored (config/params.yaml).
MIN_REFERENCE = 8
#: Minimum σ for the anomaly z-score (``sigma_floor`` in params.yaml), so a
#: near-constant baseline cannot divide the z-score by zero.
SIGMA_FLOOR = 0.1
#: z at or above which the day is flagged elevated / extreme.
Z_ELEVATED = 2.0
Z_EXTREME = 3.0


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


def _daily_series(series: pd.Series | Iterable[Mapping[str, Any]]) -> pd.Series:
    """Normalize the accepted series shapes onto a sorted DatetimeIndex."""
    if isinstance(series, pd.Series):
        daily = series.copy()
        if not isinstance(daily.index, pd.DatetimeIndex):
            daily.index = pd.to_datetime(daily.index)
        return daily.astype("float64").sort_index()
    # list of {"date": ..., "harm_total": ...} rows; the last row wins per day
    values: dict[pd.Timestamp, float] = {}
    for row in series:
        values[pd.Timestamp(row["date"])] = float(row.get("harm_total", 0.0))
    return pd.Series(values, dtype="float64").sort_index()


def anomaly(
    series: pd.Series | Iterable[Mapping[str, Any]],
    date: str | pd.Timestamp,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_reference: int = MIN_REFERENCE,
    sigma_floor: float = SIGMA_FLOOR,
    z_elevated: float = Z_ELEVATED,
    z_extreme: float = Z_EXTREME,
) -> dict[str, Any]:
    """Score one date against its seasonal window: z, percentile, flag.

    The reference sample is the same day-of-year window in *other* years —
    a year never judges itself. With fewer than ``min_reference`` reference
    years the day is ``not_scored`` with reason
    ``insufficient_reference_years``. Sigma below ``sigma_floor`` is floored,
    so a near-constant baseline keeps z finite instead of dividing by zero.

    ``series`` is either a daily ``pd.Series`` on a DatetimeIndex or the
    list-of-dicts shape :func:`src.compute.grid.to_series` returns.
    """
    daily = _daily_series(series)
    stamp = pd.Timestamp(date)
    low, high = harmonize.doy_range(int(stamp.dayofyear), window_days)
    window = harmonize.seasonal_window(daily, stamp, window_days)
    reference = window[window.index.year != stamp.year]
    value = float(daily.loc[stamp]) if stamp in daily.index else None

    percentile = None
    if value is not None and not reference.empty:
        percentile = float((reference.to_numpy(dtype="float64") <= value).mean())

    years = sorted({int(year) for year in reference.index.year})
    if value is None:
        flag, reason, z = "not_scored", "date_not_in_series", None
    elif len(years) < min_reference:
        flag, reason, z = "not_scored", "insufficient_reference_years", None
    else:
        centre = float(reference.mean())
        sigma = float(reference.std(ddof=1)) if len(reference) > 1 else 0.0
        z = (value - centre) / max(sigma, sigma_floor)
        reason = None
        if z >= z_extreme:
            flag = "extreme"
        elif z >= z_elevated:
            flag = "elevated"
        else:
            flag = "normal"

    return {
        "flag": flag,
        "reason": reason,
        "z": z,
        "percentile": percentile,
        "value": value,
        "years_used": years,
        "doy_range": [int(low), int(high)],
        "baseline_window": int(window_days),
    }


# One callable facade: ``anomaly(...)`` is the z-score scorer above, while
# ``anomaly.anomaly_report(...)`` is the percentile-rank report the API
# contract needs. Both survive ``from src.compute import anomaly``.
anomaly.anomaly_report = anomaly_report
anomaly.anomaly_payload = anomaly_payload
anomaly.DEFAULT_WINDOW_DAYS = DEFAULT_WINDOW_DAYS

__all__: Iterable[str] = (
    "DEFAULT_WINDOW_DAYS",
    "MIN_REFERENCE",
    "SIGMA_FLOOR",
    "Z_ELEVATED",
    "Z_EXTREME",
    "anomaly",
    "anomaly_payload",
    "anomaly_report",
)
