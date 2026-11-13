"""Tests for src/compute/anomaly.py.

One scorer: ``anomaly(...)``. Its percentile is the share of reference days at
or below the value (0-1), the reference excludes the target's own year, and the
flag says whether the day could be scored at all.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.compute import anomaly


def _series(values: list[float], dates: list[str]) -> pd.Series:
    return pd.Series(values, index=pd.to_datetime(dates), dtype="float64")


def test_percentile_is_the_share_of_reference_days_at_or_below():
    # Same day of year in four years: 10, 20, 30, 40. Mid-January so the
    # leap-year offset cannot move one date to a different day of year.
    series = _series(
        [10.0, 20.0, 30.0, 40.0],
        ["2020-01-15", "2021-01-15", "2022-01-15", "2023-01-15"],
    )
    # window 0 so exactly those four days form the sample.
    report = anomaly(series, "2021-01-15", window_days=0)
    assert report["value"] == 20.0
    # The reference is the three *other* years: 10, 30 and 40. One of the three
    # is at or below 20, so the share is 1/3.
    assert report["percentile"] == pytest.approx(1 / 3)
    assert report["years_used"] == [2020, 2022, 2023]
    assert report["baseline_window"] == 0


def test_top_of_the_sample_ranks_at_one():
    series = _series(
        [10.0, 20.0, 30.0, 40.0],
        ["2020-01-15", "2021-01-15", "2022-01-15", "2023-01-15"],
    )
    report = anomaly(series, "2023-01-15", window_days=0)
    assert report["percentile"] == 1.0


def test_a_year_never_judges_itself():
    """The target's own year is excluded from the reference."""
    series = _series(
        [10.0, 20.0, 30.0, 40.0],
        ["2020-01-15", "2021-01-15", "2022-01-15", "2023-01-15"],
    )
    report = anomaly(series, "2021-01-15", window_days=0)
    assert 2021 not in report["years_used"]


def test_doy_range_is_clamped_to_one_and_366():
    index = pd.to_datetime(["2021-01-01", "2021-12-31"])
    series = pd.Series([1.0, 2.0], index=index)
    january = anomaly(series, "2021-01-01", window_days=7)
    december = anomaly(series, "2021-12-31", window_days=7)
    assert january["doy_range"] == [1, 8]
    assert december["doy_range"] == [358, 366]


def test_absent_date_is_not_scored():
    series = _series([10.0], ["2020-04-09"])
    report = anomaly(series, "2024-01-01", window_days=7)
    assert report["flag"] == "not_scored"
    assert report["reason"] == "date_not_in_series"
    assert report["value"] is None
    assert report["z"] is None


def test_too_few_reference_years_is_not_scored():
    series = _series([10.0, 20.0], ["2020-01-15", "2021-01-15"])
    report = anomaly(series, "2021-01-15", window_days=0)
    assert report["flag"] == "not_scored"
    assert report["reason"] == "insufficient_reference_years"
    assert report["z"] is None


def test_a_clear_spike_is_flagged_extreme():
    dates = [f"{year}-01-15" for year in range(2010, 2030)]
    values = [10.0] * len(dates)
    values[dates.index("2015-01-15")] = 200.0
    report = anomaly(_series(values, dates), "2015-01-15", window_days=0)
    assert report["flag"] == "extreme"
    assert report["z"] is not None and report["z"] >= 3
    assert report["percentile"] == 1.0
