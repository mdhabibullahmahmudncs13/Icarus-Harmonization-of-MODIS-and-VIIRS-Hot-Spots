"""Unit tests for the S7 coverage stage (``src/compute/coverage.py``).

Coverage exists so an unobserved bin is never shown as a zero-activity bin
(docs/PRD.md G4, docs/TESTING.md §3). These tests pin its edges: a fully
covered bin, a partially covered one that falls below ``cov_min``, a bin where
neither family meets the threshold, and a bin with no observing day at all.

Synthetic data is never evidence; these are seeded, offline fixtures.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from src.compute import coverage


def _frame(rows: list[tuple[str, str]]) -> pd.DataFrame:
    """A minimal normalized frame: date plus the harmonized family column."""
    return pd.DataFrame(
        [{"acq_date": date, "sensor_family": family} for date, family in rows]
    )


# --------------------------------------------------------------------------
# Bin geometry
# --------------------------------------------------------------------------


def test_days_in_bin_is_eight_except_the_last():
    assert coverage.days_in_bin(2015, 1) == 8
    assert coverage.days_in_bin(2015, 45) == 8
    # 2015 is not a leap year: bin 46 is days 361-365, five days.
    assert coverage.days_in_bin(2015, 46) == 5
    # 2016 is: bin 46 is days 361-366, six days.
    assert coverage.days_in_bin(2016, 46) == 6


def test_days_in_bin_rejects_a_non_positive_bin():
    with pytest.raises(ValueError):
        coverage.days_in_bin(2015, 0)


# --------------------------------------------------------------------------
# Source tagging: the documented truth table (docs/DATA_DICTIONARY.md §5)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cov_modis,cov_viirs,expected",
    [
        (1.0, 1.0, "MODIS"),
        (0.75, 0.0, "MODIS"),  # exactly at the threshold still anchors
        (0.5, 1.0, "VIIRS_CAL"),
        (0.0, 0.75, "VIIRS_CAL"),
        (0.5, 0.5, "NONE"),
        (0.0, 0.0, "NONE"),
    ],
)
def test_source_for_matches_the_documented_rule(cov_modis, cov_viirs, expected):
    assert coverage.source_for(cov_modis, cov_viirs) == expected


def test_bridge_is_in_the_vocabulary_but_never_emitted():
    """A bridge factor needs one MODIS satellite separated from the pair, which
    the acquisition table cannot express; the enum still reserves the word."""
    assert "BRIDGE" in coverage.SOURCES
    grid = [coverage.source_for(m / 10, v / 10) for m in range(11) for v in range(11)]
    assert "BRIDGE" not in grid


def test_coverage_reports_the_anchoring_stream():
    assert coverage.coverage_for(1.0, 0.4) == 1.0
    assert coverage.coverage_for(0.5, 1.0) == 1.0
    # NONE falls back to the best coverage either family reached.
    assert coverage.coverage_for(0.5, 0.25) == 0.5


# --------------------------------------------------------------------------
# Binned coverage
# --------------------------------------------------------------------------


def test_availability_is_one_row_per_day_with_both_family_flags():
    frame = _frame(
        [
            ("2015-01-01", "MODIS"),
            ("2015-01-01", "VIIRS"),
            ("2015-01-03", "VIIRS"),
        ]
    )
    availability = coverage.family_availability(frame)
    assert list(availability.index.strftime("%Y-%m-%d")) == ["2015-01-01", "2015-01-03"]
    assert bool(availability.loc["2015-01-01", "modis"]) is True
    assert bool(availability.loc["2015-01-01", "viirs"]) is True
    assert bool(availability.loc["2015-01-03", "modis"]) is False
    assert bool(availability.loc["2015-01-03", "viirs"]) is True


def test_full_coverage_is_tagged_modis():
    rows = [(f"2015-01-{day:02d}", family) for day in range(1, 9) for family in ("MODIS", "VIIRS")]
    table = coverage.bin_coverage(_frame(rows))
    assert len(table) == 1
    row = table.iloc[0]
    assert row["year"] == 2015 and row["bin"] == 1
    assert row["n_days"] == 8 and row["observed_days"] == 8
    assert row["cov_modis"] == 1.0 and row["cov_viirs"] == 1.0
    assert row["coverage"] == 1.0 and row["source"] == "MODIS"


def test_partial_modis_falls_back_to_viirs_and_is_still_low_when_it_cannot():
    """Six observing days: MODIS on four -> 2/3, below cov_min; VIIRS fills in."""
    rows: list[tuple[str, str]] = []
    for day in range(1, 5):
        rows += [(f"2015-01-{day:02d}", "MODIS"), (f"2015-01-{day:02d}", "VIIRS")]
    for day in range(5, 7):
        rows.append((f"2015-01-{day:02d}", "VIIRS"))
    table = coverage.bin_coverage(_frame(rows))
    row = table.iloc[0]
    assert row["observed_days"] == 6
    assert row["modis_days"] == 4 and row["viirs_days"] == 6
    assert row["cov_modis"] == pytest.approx(4 / 6, abs=1e-4)
    assert row["cov_viirs"] == 1.0
    assert row["source"] == "VIIRS_CAL"
    assert row["coverage"] == 1.0


def test_neither_family_meeting_the_threshold_is_none():
    """Two observing days, one MODIS day and one VIIRS day: 0.5 each."""
    frame = _frame([("2015-01-01", "MODIS"), ("2015-01-02", "VIIRS")])
    row = coverage.bin_coverage(frame).iloc[0]
    assert row["observed_days"] == 2
    assert row["cov_modis"] == 0.5 and row["cov_viirs"] == 0.5
    assert row["source"] == "NONE"
    assert row["coverage"] == 0.5


def test_no_availability_is_an_empty_table_with_the_right_columns():
    table = coverage.bin_coverage(_frame([]))
    assert table.empty
    assert list(table.columns) == list(coverage.COVERAGE_COLUMNS)


def test_coverage_never_carries_nan():
    frame = _frame([("2015-01-01", "MODIS"), ("2015-01-02", "VIIRS")])
    for value in coverage.bin_coverage(frame).iloc[0].to_dict().values():
        assert not (isinstance(value, float) and math.isnan(value))


# --------------------------------------------------------------------------
# Date lookup used by the series payload
# --------------------------------------------------------------------------


def test_coverage_for_date_maps_a_day_to_its_bin():
    rows = [(f"2015-01-{day:02d}", family) for day in range(1, 9) for family in ("MODIS", "VIIRS")]
    index = coverage.coverage_index(_frame(rows))
    assert coverage.coverage_for_date(index, "2015-01-05") == (1.0, "MODIS")
    # Day 9 opens bin 2, which has no detections in this frame.
    assert coverage.coverage_for_date(index, "2015-01-09") == (0.0, "NONE")
