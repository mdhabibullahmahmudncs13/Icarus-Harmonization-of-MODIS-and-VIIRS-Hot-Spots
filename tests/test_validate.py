"""Tests for src/compute/validate.py.

The headline test is the synthetic one the implementation plan asks for: a
dataset where VIIRS produces about three times as many detections inside the
same cells. Harmonized counts match, raw counts do not, and the harmonized
correlation beats the raw one.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.compute import schema
from src.compute.validate import (
    correlation_stats,
    family_date_range,
    overlap_window,
    validate_overlap,
)
from tests.synthetic import identical_cell_days, synthetic_detections

# --------------------------------------------------------------------------
# Overlap window
# --------------------------------------------------------------------------


def test_overlap_window_is_the_later_start_and_earlier_end():
    detections = pd.DataFrame(
        {
            "acq_date": pd.to_datetime(["2010-01-01", "2020-01-01", "2012-06-01", "2018-06-01"]),
            "sensor_family": ["MODIS", "MODIS", "VIIRS", "VIIRS"],
        }
    )
    assert overlap_window(detections) == (date(2012, 6, 1), date(2018, 6, 1))


def test_overlap_window_requires_both_sensors():
    detections = pd.DataFrame(
        {"acq_date": pd.to_datetime(["2015-01-01"]), "sensor_family": ["MODIS"]}
    )
    with pytest.raises(ValueError, match="both MODIS and VIIRS"):
        overlap_window(detections)


def test_family_date_range_is_none_when_the_sensor_is_absent():
    detections = pd.DataFrame(
        {"acq_date": pd.to_datetime(["2015-01-01"]), "sensor_family": ["MODIS"]}
    )
    assert family_date_range(detections, schema.VIIRS) is None


# --------------------------------------------------------------------------
# Correlation statistics
# --------------------------------------------------------------------------


def test_correlation_stats_on_a_known_linear_pair():
    index = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    stats = correlation_stats(pd.Series([1, 2, 3], index=index), pd.Series([2, 4, 6], index=index))
    assert stats.pearson == pytest.approx(1.0)
    assert stats.spearman == pytest.approx(1.0)
    assert stats.ratio == pytest.approx(2.0)


def test_correlation_stats_on_an_inverted_pair():
    index = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    stats = correlation_stats(pd.Series([1, 2, 3], index=index), pd.Series([3, 2, 1], index=index))
    assert stats.pearson == pytest.approx(-1.0)
    assert stats.spearman == pytest.approx(-1.0)


def test_correlation_stats_is_nan_with_too_little_data():
    index = pd.to_datetime(["2020-01-01"])
    stats = correlation_stats(pd.Series([1], index=index), pd.Series([2], index=index))
    assert stats.pearson != stats.pearson  # NaN


# --------------------------------------------------------------------------
# The synthetic 3x VIIRS case
# --------------------------------------------------------------------------


def test_raw_counts_triple_but_harmonized_counts_match():
    detections = identical_cell_days(days=40, multiplier=3)
    report = validate_overlap(detections, cell_km=5.5)

    assert report.raw.ratio == pytest.approx(3.0, rel=0.05)
    assert report.harmonized.ratio == pytest.approx(1.0, rel=0.05)
    assert report.raw.ratio > report.harmonized.ratio


def test_harmonized_correlation_exceeds_raw_correlation_on_noisy_data():
    """VIIRS adds several variable detections per cell-day; the collapse removes that noise."""
    detections = synthetic_detections()
    report = validate_overlap(detections, cell_km=5.5)

    assert report.raw.ratio > 2.0, "VIIRS should look strongly inflated before harmonization"
    assert report.harmonized.ratio < report.raw.ratio, "harmonization should shrink the inflation"
    assert report.harmonized.pearson > report.raw.pearson, (
        "harmonized MODIS/VIIRS should track more closely than raw"
    )
    assert report.raw.pearson > 0.5, "the sensors should still agree in direction"


def test_cell_sweep_leaves_raw_pearson_constant_and_varies_only_harmonized():
    detections = synthetic_detections()
    report = validate_overlap(detections, cell_km=5.5, cell_sizes=(5.5, 11.0, 22.0))
    assert [row["cell_km"] for row in report.cell_sweep] == [5.5, 11.0, 22.0]
    raw_values = {row["raw_pearson"] for row in report.cell_sweep}
    assert len(raw_values) == 1, "raw counts do not depend on the grid"
    assert all(row["harmonized_pearson"] > 0.9 for row in report.cell_sweep)


def test_validate_overlap_rejects_an_empty_detection_set():
    with pytest.raises(ValueError, match="no detections"):
        validate_overlap(pd.DataFrame())


def test_validate_report_serializes_to_the_contract_shape():
    report = validate_overlap(synthetic_detections(days=60), cell_km=5.5)
    payload = report.as_dict()
    assert set(payload) == {"overlap", "raw", "harmonized", "cell_sweep"}
    assert set(payload["raw"]) == {"pearson", "spearman", "ratio"}
    assert set(payload["overlap"]) == {"start", "end"}
    assert payload["overlap"]["start"] <= payload["overlap"]["end"]
