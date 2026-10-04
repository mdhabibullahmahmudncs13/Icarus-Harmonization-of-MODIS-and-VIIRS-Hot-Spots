"""Tests for src/compute/anomaly.py."""

from __future__ import annotations

import pandas as pd

from src.compute import anomaly


def _series(values: list[float], dates: list[str]) -> pd.Series:
    return pd.Series(values, index=pd.to_datetime(dates), dtype="float64")


def test_percentile_is_the_share_of_same_window_days_at_or_below():
    # Same day of year in four years: 10, 20, 30, 40. Mid-January so the
    # leap-year offset cannot move one date to a different day of year.
    series = _series(
        [10.0, 20.0, 30.0, 40.0],
        ["2020-01-15", "2021-01-15", "2022-01-15", "2023-01-15"],
    )
    # window 0 so exactly those four days form the sample.
    report = anomaly.anomaly_report(series, "2021-01-15", window_days=0)
    assert report["value"] == 20.0
    assert report["percentile"] == 50.0  # 10 and 20 are <= 20
    assert report["years_used"] == 4
    assert report["baseline_window"] == 0


def test_top_of_the_sample_ranks_at_one_hundred():
    series = _series(
        [10.0, 20.0, 30.0, 40.0],
        ["2020-01-15", "2021-01-15", "2022-01-15", "2023-01-15"],
    )
    report = anomaly.anomaly_report(series, "2023-01-15", window_days=0)
    assert report["percentile"] == 100.0


def test_doy_range_is_clamped_to_one_and_366():
    index = pd.to_datetime(["2021-01-01", "2021-12-31"])
    series = pd.Series([1.0, 2.0], index=index)
    january = anomaly.anomaly_report(series, "2021-01-01", window_days=7)
    december = anomaly.anomaly_report(series, "2021-12-31", window_days=7)
    assert january["doy_range"] == [1, 8]
    assert december["doy_range"] == [358, 366]


def test_absent_date_reports_nan_rather_than_a_number():
    series = _series([10.0], ["2020-04-09"])
    report = anomaly.anomaly_report(series, "2024-01-01", window_days=7)
    assert report["value"] != report["value"]  # NaN, not a fabricated value
    assert report["date"] == "2024-01-01"
