"""Tests for src/compute/harmonize.py.

These replaced the original stub tests, which asserted that every function
raised NotImplementedError. They now assert the actual science: hand-checked
grid geometry, the cell-day collapse, the series, the baseline and the
sensor-to-sensor correlation.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from src.compute import harmonize, schema
from src.compute.harmonize import (
    DEFAULT_CELL_KM,
    cell_bounds,
    cell_id,
    collapse_cell_days,
    daily_series,
    degrees_per_lat,
    degrees_per_lon,
    grid_index,
    harmonized_series,
    overlap_correlation,
    parse_cell_id,
    raw_series,
    seasonal_baseline,
    to_grid,
)
from src.compute.harmonize import (
    harmonize as harmonize_detections,
)
from tests.synthetic import identical_cell_days


def modis_detections(rows: list[tuple[float, float, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "latitude": [r[0] for r in rows],
            "longitude": [r[1] for r in rows],
            "acq_date": [r[2] for r in rows],
            "confidence": [r[3] for r in rows],
            "instrument": ["MODIS"] * len(rows),
        }
    )


# --------------------------------------------------------------------------
# Grid geometry
# --------------------------------------------------------------------------


def test_grid_snaps_nearby_detections_into_one_cell():
    # ~1.1 km apart: well inside one 5.5 km cell.
    assert grid_index(23.10, 90.10) == grid_index(23.11, 90.11)


def test_grid_separates_distant_detections():
    assert grid_index(23.10, 90.10) != grid_index(24.00, 91.00)


def test_degrees_per_lon_widens_with_latitude():
    assert degrees_per_lon() > degrees_per_lat()
    assert degrees_per_lon(5.5, 0.0) == pytest.approx(degrees_per_lat(), rel=1e-9)


def test_cell_is_about_the_stated_size_in_both_directions():
    expected_km = DEFAULT_CELL_KM
    lat_km = degrees_per_lat() * harmonize.KM_PER_DEGREE
    lon_km = degrees_per_lon() * harmonize.KM_PER_DEGREE * math.cos(
        math.radians(harmonize.REFERENCE_LATITUDE_DEG)
    )
    assert lat_km == pytest.approx(expected_km, rel=1e-6)
    assert lon_km == pytest.approx(expected_km, rel=1e-6)


def test_cell_bounds_contain_their_own_point():
    row, col = grid_index(23.1, 90.1)
    west, south, east, north = cell_bounds(cell_id(row, col))
    assert west <= 90.1 < east
    assert south <= 23.1 < north


def test_parse_cell_id_round_trips_and_rejects_junk():
    assert parse_cell_id(cell_id(-12, 345)) == (-12, 345)
    with pytest.raises(ValueError):
        parse_cell_id("nonsense")


def test_cell_km_must_be_positive():
    with pytest.raises(ValueError):
        degrees_per_lat(0)


def test_to_grid_adds_one_id_per_detection():
    frame = modis_detections([(23.1, 90.1, "2015-01-01", 80.0)] * 3)
    gridded = to_grid(frame)
    assert len(gridded) == 3
    assert set(gridded["cell_id"]) == {cell_id(*grid_index(23.1, 90.1))}


# --------------------------------------------------------------------------
# Harmonization and collapse
# --------------------------------------------------------------------------


def test_collapse_cell_days_counts_detections_and_sensors():
    frame = pd.DataFrame(
        {
            "latitude": [23.10, 23.11, 24.00, 24.01],
            "longitude": [90.10, 90.11, 91.00, 91.01],
            "acq_date": ["2015-01-01"] * 4,
            "confidence": [80, 80, 80, 80],
            "instrument": ["MODIS", "VIIRS", "MODIS", "MODIS"],
        }
    )
    collapsed = collapse_cell_days(harmonize_detections(frame)).sort_values("cell_id")
    assert len(collapsed) == 2
    assert list(collapsed["raw_detections"]) == [2, 2]
    # The first cell-day was seen by both sensors.
    assert sorted(collapsed["sensors_agreeing"]) == [1, 2]


def test_harmonize_drops_viirs_low_confidence_and_keeps_high():
    low = pd.DataFrame(
        {
            "latitude": [23.1],
            "longitude": [90.1],
            "acq_date": ["2015-01-01"],
            "confidence": ["l"],
            "instrument": ["VIIRS"],
        }
    )
    high = low.assign(confidence="h")
    assert harmonize_detections(low).empty
    assert len(harmonize_detections(high)) == 1
    assert harmonize_detections(high)["confidence_num"].iloc[0] == schema.VIIRS_CONFIDENCE_MAP["h"]


def test_harmonize_empty_input_returns_empty_canonical_frame():
    result = harmonize_detections(pd.DataFrame())
    assert result.empty
    assert list(result.columns) == list(schema.CANONICAL_COLUMNS)


def test_harmonize_rejects_detections_without_required_columns():
    with pytest.raises(ValueError, match="missing required columns"):
        harmonize_detections(pd.DataFrame({"latitude": [23.1]}))


def test_harmonize_is_deterministic():
    frame = modis_detections([(23.1, 90.1, "2015-01-01", 80.0), (23.11, 90.11, "2015-01-01", 70.0)])
    first = harmonize_detections(frame)
    second = harmonize_detections(frame)
    pd.testing.assert_frame_equal(first, second)


# --------------------------------------------------------------------------
# Series
# --------------------------------------------------------------------------


def test_raw_and_harmonized_series_hand_checked():
    frame = modis_detections(
        [
            (23.10, 90.10, "2015-01-01", 80.0),
            (23.11, 90.11, "2015-01-01", 80.0),
            (23.12, 90.12, "2015-01-01", 80.0),
            (24.00, 91.00, "2015-01-01", 80.0),
            (23.10, 90.10, "2015-01-02", 80.0),
        ]
    )
    detections = harmonize_detections(frame)
    raw = raw_series(detections)
    harmonized = harmonized_series(detections)
    assert raw.loc["2015-01-01"] == 4
    assert harmonized.loc["2015-01-01"] == 2  # three detections collapsed to one cell
    assert raw.loc["2015-01-02"] == harmonized.loc["2015-01-02"] == 1


def test_daily_series_has_the_contract_columns():
    detections = harmonize_detections(modis_detections([(23.1, 90.1, "2015-01-01", 80.0)]))
    daily = daily_series(detections)
    assert list(daily.columns) == [
        "date",
        "raw_modis",
        "raw_viirs",
        "raw_total",
        "harm_modis",
        "harm_viirs",
        "harm_total",
    ]
    assert daily.loc[0, "raw_total"] == daily.loc[0, "raw_modis"] + daily.loc[0, "raw_viirs"]


def test_daily_series_of_nothing_is_an_empty_frame_with_columns():
    daily = daily_series(pd.DataFrame())
    assert daily.empty
    assert "harm_total" in daily.columns


def test_collapse_makes_identical_cell_days_match_while_raw_counts_do_not():
    """The mechanism: VIIRS reports 3 detections per fire MODIS reported once."""
    detections = harmonize_detections(identical_cell_days(days=40, multiplier=3))
    daily = daily_series(detections)

    # Harmonized counts agree because both sensors saw the same cell-days.
    assert (daily["harm_modis"] == daily["harm_viirs"]).all()
    # Raw counts do not: VIIRS is inflated by the multiplicity.
    assert daily["raw_viirs"].sum() == 3 * daily["raw_modis"].sum()
    assert (daily["raw_viirs"] > daily["raw_modis"]).all()
    # The raw total counts every detection: 1 MODIS + 3 VIIRS per fire.
    assert daily["raw_total"].sum() == pytest.approx(4.0 * daily["raw_modis"].sum())
    # Harmonization collapses all four into one cell-day, so the total
    # equals the MODIS-only count: the VIIRS inflation is gone.
    assert daily["harm_total"].sum() == pytest.approx(daily["harm_modis"].sum())


# --------------------------------------------------------------------------
# Baseline and anomaly z-score
# --------------------------------------------------------------------------


def test_seasonal_baseline_is_the_median_for_each_day_of_year():
    # Mid-January in each year: the same day of year in leap and non-leap
    # years alike, so the sample really is one calendar day.
    index = pd.to_datetime(["2020-01-15", "2021-01-15", "2022-01-15"])
    series = pd.Series([10.0, 20.0, 30.0], index=index)
    doy = int(index[0].dayofyear)
    baseline = seasonal_baseline(series, window_days=0)
    assert baseline.loc[doy] == 20.0
    assert baseline.loc[doy + 1] != baseline.loc[doy + 1]  # NaN: no data that day


def test_anomaly_score_is_positive_above_the_baseline_and_negative_below():
    index = pd.to_datetime(["2020-01-15", "2021-01-15", "2022-01-15"])
    series = pd.Series([10.0, 20.0, 30.0], index=index)
    baseline = seasonal_baseline(series, window_days=0)
    probe = index[2]
    above = harmonize.anomaly_score(
        pd.Series([10.0, 20.0, 99.0], index=index), baseline, probe
    )
    below = harmonize.anomaly_score(
        pd.Series([10.0, 20.0, 1.0], index=index), baseline, probe
    )
    assert above > 0
    assert below < 0


# --------------------------------------------------------------------------
# Overlap correlation
# --------------------------------------------------------------------------


def test_overlap_correlation_perfect_linear_series():
    index = pd.to_datetime(["2015-01-01", "2015-01-02", "2015-01-03"])
    modis = pd.DataFrame({"raw": [1, 2, 3], "harmonized": [1, 2, 3]}, index=index)
    viirs = pd.DataFrame({"raw": [3, 6, 9], "harmonized": [2, 4, 6]}, index=index)
    raw_corr, harmonized_corr = overlap_correlation(modis, viirs)
    assert raw_corr == pytest.approx(1.0)
    assert harmonized_corr == pytest.approx(1.0)


def test_overlap_correlation_flags_a_missing_column():
    index = pd.to_datetime(["2015-01-01", "2015-01-02"])
    good = pd.DataFrame({"raw": [1, 2], "harmonized": [1, 2]}, index=index)
    bad = pd.DataFrame({"raw": [1, 2]}, index=index)
    with pytest.raises(ValueError, match="missing columns"):
        overlap_correlation(good, bad)
