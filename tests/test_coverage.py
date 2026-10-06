"""Unit tests for the S7 coverage stage (``src/compute/coverage.py``).

Coverage exists so an unobserved bin is never shown as a zero-activity bin
(docs/PRD.md G4, docs/TESTING.md §3). Availability is the stream calendar from
:mod:`src.compute.availability`, so these tests drive the four source classes
directly: full MODIS, a single MODIS satellite (BRIDGE), VIIRS only
(VIIRS_CAL), and nothing (NONE, the hatched state).

Deterministic, offline fixtures.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from src.compute import coverage


def _window(start: date, days: int) -> set[date]:
    return {start + timedelta(days=offset) for offset in range(days)}


# --------------------------------------------------------------------------
# Bin geometry
# --------------------------------------------------------------------------


def test_days_in_bin_is_eight_except_the_last():
    assert coverage.days_in_bin(2015, 1) == 8
    assert coverage.days_in_bin(2015, 45) == 8
    assert coverage.days_in_bin(2015, 46) == 5  # 2015 is not a leap year
    assert coverage.days_in_bin(2016, 46) == 6  # 2016 is


def test_days_in_bin_rejects_a_non_positive_bin():
    with pytest.raises(ValueError):
        coverage.days_in_bin(2015, 0)


# --------------------------------------------------------------------------
# Source tagging: the documented rule (docs/DATA_DICTIONARY.md §5)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "both_frac,cov_mod_t,cov_mod_a,cov_viirs,expected",
    [
        (1.0, 1.0, 1.0, 1.0, "MODIS"),
        (0.75, 1.0, 0.75, 1.0, "MODIS"),  # at the threshold still anchors
        (0.0, 1.0, 0.0, 1.0, "BRIDGE"),  # Terra alone
        (0.0, 0.0, 1.0, 0.0, "BRIDGE"),  # Aqua alone
        (0.0, 0.0, 0.0, 1.0, "VIIRS_CAL"),
        (0.5, 0.5, 0.5, 0.5, "NONE"),
        (0.0, 0.0, 0.0, 0.0, "NONE"),
    ],
)
def test_source_for_matches_the_documented_rule(both_frac, cov_mod_t, cov_mod_a, cov_viirs, expected):
    assert (
        coverage.source_for(
            both_frac=both_frac, cov_mod_t=cov_mod_t, cov_mod_a=cov_mod_a, cov_viirs=cov_viirs
        )
        == expected
    )


def test_the_full_vocabulary_is_reachable():
    assert set(coverage.SOURCES) == {"MODIS", "BRIDGE", "VIIRS_CAL", "NONE"}


def test_coverage_reports_the_anchoring_stream():
    assert (
        coverage.coverage_for("MODIS", both_frac=1.0, cov_mod_t=1.0, cov_mod_a=1.0, cov_viirs=0.0)
        == 1.0
    )
    assert (
        coverage.coverage_for("BRIDGE", both_frac=0.0, cov_mod_t=1.0, cov_mod_a=0.0, cov_viirs=1.0)
        == 1.0
    )
    assert (
        coverage.coverage_for("VIIRS_CAL", both_frac=0.0, cov_mod_t=0.0, cov_mod_a=0.0, cov_viirs=1.0)
        == 1.0
    )
    # NONE falls back to the best coverage any MODIS stream reached.
    assert (
        coverage.coverage_for("NONE", both_frac=0.0, cov_mod_t=0.5, cov_mod_a=0.0, cov_viirs=0.25)
        == 0.5
    )


# --------------------------------------------------------------------------
# Binned coverage
# --------------------------------------------------------------------------


_START = date(2019, 1, 1)
_END = date(2019, 1, 8)  # exactly bin 1


def _row(availability: dict[str, set[date]]):
    table = coverage.bin_coverage(availability, start=_START, end=_END)
    assert len(table) == 1
    return table.iloc[0]


def test_full_modis_is_tagged_modis():
    row = _row(
        {
            "MOD_T": _window(_START, 8),
            "MOD_A": _window(_START, 8),
            "VIIRS_SNPP": _window(_START, 8),
        }
    )
    assert row["year"] == 2019 and row["bin"] == 1
    assert row["n_days"] == 8 and row["window_days"] == 8
    assert row["both_frac"] == 1.0 and row["coverage"] == 1.0 and row["source"] == "MODIS"


def test_single_modis_satellite_is_bridge():
    row = _row(
        {
            "MOD_T": _window(_START, 8),
            "MOD_A": set(),
            "VIIRS_SNPP": _window(_START, 8),
        }
    )
    assert row["both_frac"] == 0.0 and row["cov_mod_t"] == 1.0
    assert row["source"] == "BRIDGE" and row["coverage"] == 1.0


def test_modis_absent_with_viirs_is_viirs_cal():
    row = _row({"MOD_T": set(), "MOD_A": set(), "VIIRS_SNPP": _window(_START, 8)})
    assert row["source"] == "VIIRS_CAL" and row["coverage"] == 1.0


def test_everything_out_is_none_and_uncovered():
    row = _row({"MOD_T": set(), "MOD_A": set(), "VIIRS_SNPP": set()})
    assert row["source"] == "NONE"
    assert row["coverage"] == 0.0
    assert row["mod_t_days"] == 0 and row["mod_a_days"] == 0


def test_partial_coverage_below_threshold_is_none():
    row = _row(
        {
            "MOD_T": _window(_START, 4),
            "MOD_A": set(),
            "VIIRS_SNPP": _window(_START, 2),
        }
    )
    assert row["cov_mod_t"] == 0.5 and row["cov_viirs"] == 0.25
    assert row["source"] == "NONE" and row["coverage"] == 0.5


def test_a_bin_clipped_by_the_window_is_measured_over_its_window():
    """A range that covers four days of bin 1 must not punish the other four."""
    availability = {
        "MOD_T": _window(_START, 8),
        "MOD_A": _window(_START, 8),
        "VIIRS_SNPP": _window(_START, 8),
    }
    row = coverage.bin_coverage(availability, start=_START, end=_START + timedelta(days=3)).iloc[0]
    assert row["n_days"] == 8 and row["window_days"] == 4
    assert row["both_frac"] == 1.0 and row["source"] == "MODIS"


def test_reversed_window_is_empty_with_the_right_columns():
    table = coverage.bin_coverage({}, start=date(2019, 2, 1), end=date(2019, 1, 1))
    assert table.empty
    assert list(table.columns) == list(coverage.COVERAGE_COLUMNS)


def test_coverage_never_carries_nan():
    row = _row({"MOD_T": set(), "MOD_A": set(), "VIIRS_SNPP": set()})
    for value in row.to_dict().values():
        assert not (isinstance(value, float) and math.isnan(value))


# --------------------------------------------------------------------------
# Date lookup used by the series payload
# --------------------------------------------------------------------------


def test_coverage_for_date_maps_a_day_to_its_bin():
    availability = {
        "MOD_T": _window(_START, 8),
        "MOD_A": _window(_START, 8),
        "VIIRS_SNPP": _window(_START, 8),
    }
    index = coverage.coverage_index(availability, start=_START, end=_END)
    assert coverage.coverage_for_date(index, "2019-01-05") == (1.0, "MODIS")
    # Day 9 opens bin 2, which is not in the indexed window.
    assert coverage.coverage_for_date(index, "2019-01-09") == (0.0, "NONE")
