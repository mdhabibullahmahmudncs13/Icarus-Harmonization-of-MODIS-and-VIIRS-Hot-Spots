"""Tests for src/compute/export.py.

Every payload is validated against the real contract schema
(``docs/contract.schema.json``, exported from the frontend's zod types), so a
backend payload and a mock file are held to the same shape. The ``$defs``
entries are the contract's single source of truth; the draft-07
``definitions`` alias that briefly shadowed them has been removed, because two
definitions that disagree can both pass and hide a real mismatch.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import jsonschema
import pandas as pd
import pytest

from src.compute import coverage, export, harmonize
from src.compute.availability import availability_table
from src.compute.series_util import bin_of_doy
from src.demo import demo_detections
from tests.synthetic import synthetic_detections

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((REPO_ROOT / "docs" / "contract.schema.json").read_text())

#: Contract payloads this module is responsible for.
PAYLOADS = (
    "metaResponse",
    "series",
    "cells",
    "baseline",
    "anomalies",
    "criticalPeriod",
    "validation",
    "methods",
    "aoi",
)


@pytest.fixture(scope="module")
def detections() -> pd.DataFrame:
    return harmonize.harmonize(synthetic_detections(days=120))


@pytest.fixture(scope="module")
def series(detections: pd.DataFrame) -> pd.Series:
    return harmonize.harmonized_series(detections)


def assert_matches(name: str, payload: dict) -> None:
    """Validate against the contract's ``$defs`` entry, refs and all."""
    defs = CONTRACT["$defs"]
    jsonschema.Draft202012Validator({"$ref": f"#/$defs/{name}", "$defs": defs}).validate(payload)


# --------------------------------------------------------------------------
# The schema itself must be the one the frontend ships
# --------------------------------------------------------------------------


def test_the_contract_defines_every_payload_this_module_builds():
    assert set(PAYLOADS) <= set(CONTRACT["$defs"])


def test_the_contract_has_one_definition_per_payload():
    """A second, disagreeing definition family would make a mismatch invisible."""
    assert "definitions" not in CONTRACT


# --------------------------------------------------------------------------
# meta
# --------------------------------------------------------------------------


def test_meta_payload_matches_the_contract(detections):
    payload = export.build_meta_response(detections)
    assert_matches("metaResponse", payload)
    assert payload["years"]["start"] == 2015
    assert payload["streams"] == ["MOD_T", "MOD_A", "VIIRS_SNPP", "VIIRS_N20", "VIIRS_N21"]


def test_meta_reports_the_params_hash_of_the_parameters_it_used(detections):
    payload = export.build_meta_response(detections, cell_km=11.0)
    assert payload["meta"]["params_hash"] == export.params_hash(
        bbox=export.BANGLADESH_BBOX,
        cell_km=11.0,
        min_confidence=50,
        date_range=payload["meta"]["date_range"],
    )
    # A different parameter set must hash differently, or the id is useless.
    other = export.build_meta_response(detections)
    assert other["meta"]["params_hash"] != payload["meta"]["params_hash"]


# --------------------------------------------------------------------------
# Payloads
# --------------------------------------------------------------------------


def test_series_payload_matches_the_contract(detections):
    payload = export.build_series(detections)
    assert_matches("series", payload)
    assert payload["metric"] == "cell_days"
    assert payload["bin_days"] == 1
    assert payload["series"], "the synthetic data has detections"
    first = payload["series"][0]
    assert first["raw_total"] == first["raw_modis"] + first["raw_viirs"]


def test_series_rows_carry_s7_coverage_and_source(detections):
    """docs/TESTING.md §7: /api/v1/series bins carry coverage and source."""
    payload = export.build_series(detections)
    seen: dict[tuple[int, int], tuple[float, str]] = {}
    for row in payload["series"]:
        assert 0.0 <= row["coverage"] <= 1.0
        assert row["source"] in set(coverage.SOURCES)
        key = (int(row["date"][:4]), bin_of_doy(pd.Timestamp(row["date"]).dayofyear))
        # Coverage and source are properties of the bin, so every day in one
        # eight-day bin reports the same pair.
        assert seen.setdefault(key, (row["coverage"], row["source"])) == (
            row["coverage"],
            row["source"],
        )


def test_series_coverage_equals_the_s7_stage(detections):
    """The payload must not re-derive coverage; it must be the stage's output."""
    payload = export.build_series(detections)
    start, end = (date.fromisoformat(value) for value in payload["meta"]["date_range"])
    index = coverage.coverage_index(availability_table(start, end), start=start, end=end)
    for row in payload["series"]:
        assert (row["coverage"], row["source"]) == coverage.coverage_for_date(index, row["date"])


def test_series_is_continuous_so_an_outage_bin_still_has_rows(detections):
    """A day with no detections is a zero count, not a missing day."""
    payload = export.build_series(detections)
    assert len(payload["series"]) == 120


def test_viirs_anchored_bins_are_calibrated_to_the_modis_scale():
    """During a MODIS outage the bin is VIIRS_CAL and S8 scales its VIIRS count."""
    detections = harmonize.harmonize(demo_detections(days=365, start=date(2019, 1, 1)))
    payload = export.build_series(detections)
    viirs_rows = [row for row in payload["series"] if row["source"] == "VIIRS_CAL"]
    assert viirs_rows, "the June MODIS outage must produce VIIRS_CAL bins"
    for row in viirs_rows:
        assert row["harm_total"] == row["harm_modis"] + row["harm_viirs"]
        assert row["harm_viirs"] >= 0


def test_cells_payload_matches_the_contract(detections):
    payload = export.build_cells(detections)
    assert_matches("cells", payload)
    assert payload["cells"]
    west, south, east, north = payload["cells"][0]["bounds"]
    assert west < east and south < north
    assert payload["window"]["start"] <= payload["window"]["end"]


def test_cells_window_defaults_to_the_whole_dataset(detections):
    payload = export.build_cells(detections)
    assert payload["window"] == {
        "start": export.detections_date_range(detections)[0],
        "end": export.detections_date_range(detections)[1],
    }


def test_baseline_payload_matches_the_contract(series):
    payload = export.build_baseline(series, window_days=7)
    assert_matches("baseline", payload)
    assert payload["window_days"] == 7
    assert payload["baseline"]
    assert payload["years_used"] == [2015]


def test_anomaly_payload_matches_the_contract(series):
    date_ = series.index[len(series) // 2]
    payload = export.build_anomaly(series, date_=date_)
    assert_matches("anomalies", payload)
    assert payload["query"] == {"date": pd.Timestamp(date_).strftime("%Y-%m-%d"), "aoi": "BGD"}
    assert payload["flag"] in {"normal", "elevated", "extreme", "not_scored"}


def test_anomaly_payload_never_carries_nan(series):
    """The schema allows null for an un-scored day and never allows NaN."""
    payload = export.build_anomaly(series, date_=series.index[0], window_days=7)
    assert_matches("anomalies", payload)
    assert payload["value"] is None or math.isfinite(payload["value"])
    assert payload["percentile"] is None or math.isfinite(payload["percentile"])
    json.dumps(payload, allow_nan=False)


def test_validation_payload_matches_the_contract(detections):
    payload = export.build_validation(detections)
    assert_matches("validation", payload)
    assert payload["cell_sweep"]
    assert set(payload["overlap"]) == {"years", "n_days"}


def test_critical_period_payload_matches_the_contract(series):
    payload = export.build_critical_period(series)
    assert_matches("criticalPeriod", payload)
    assert payload["aoi"] == "BGD"
    assert set(payload["window"]) == {"start_bin", "end_bin", "mass"}
    assert {row["year"] for row in payload["year_timing_deviation"]} == {2015}


def test_critical_period_reports_a_null_window_when_nothing_burns():
    empty_ish = pd.Series(
        [0.0] * 40,
        index=pd.date_range("2015-01-01", periods=40, freq="D"),
    )
    payload = export.build_critical_period(empty_ish)
    assert_matches("criticalPeriod", payload)
    assert payload["insufficient_activity"] is True
    assert payload["window"] is None
    assert payload["onset_bin"] is None and payload["peak_bin"] is None


def test_year_timing_deviation_is_zero_for_a_single_year(series):
    assert export.year_timing_deviation(series) == [{"year": 2015, "days": 0}]


def test_aoi_payload_matches_the_contract_and_the_presets_file():
    payload = export.build_aoi()
    assert_matches("aoi", payload)
    on_disk = json.loads((REPO_ROOT / "src" / "aoi_presets.json").read_text())["presets"]
    assert payload["presets"] == [
        {"id": p["id"], "name": p["name"], "bbox": p["bbox"]} for p in on_disk
    ]


def test_methods_payload_matches_the_contract():
    payload = export.build_methods()
    assert_matches("methods", payload)
    assert payload["confidence_mapping"] == {"low": 25, "nominal": 60, "high": 90}
    assert payload["min_confidence"] == 50
    assert {d["id"] for d in payload["datasets"]} == {
        "FIRMS_MODIS_SP",
        "FIRMS_VIIRS_SNPP_SP",
        "FIRMS_VIIRS_NOAA20_SP",
        "FIRMS_VIIRS_NOAA21_SP",
    }
    assert all(d["sensor"] and d["used_for"] for d in payload["datasets"])


def test_sensor_epochs_carry_the_firms_product_names_and_the_npp_deadline():
    products = {s["product"]: s for s in export.sensor_table()}
    assert "VIIRS_SNPP_SP" in products
    assert products["VIIRS_SNPP_SP"]["family"] == "VIIRS"
    assert products["VIIRS_SNPP_SP"]["end"] == "2026-11-01"


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def test_write_all_writes_every_file_and_is_serializable(tmp_path, detections):
    written = export.write_all(
        detections,
        tmp_path,
        anomaly_date=str(detections["acq_date"].iloc[0].date()),
        generated_at=pd.Timestamp("2026-10-04T00:00:00Z").to_pydatetime(),
    )
    names = {path.name for path in written}
    assert names == {
        "meta.json",
        "series.json",
        "cells.json",
        "baseline.json",
        "anomaly.json",
        "critical-period.json",
        "validation.json",
        "methods.json",
        "aoi.json",
    }
    definition_for = {
        "meta": "metaResponse",
        "series": "series",
        "cells": "cells",
        "baseline": "baseline",
        "anomaly": "anomalies",
        "critical-period": "criticalPeriod",
        "validation": "validation",
        "methods": "methods",
        "aoi": "aoi",
    }
    for path in written:
        payload = json.loads(path.read_text())
        assert_matches(definition_for[path.stem], payload)


def test_written_json_is_byte_stable_for_a_fixed_timestamp(tmp_path, detections):
    stamp = pd.Timestamp("2026-10-04T00:00:00Z").to_pydatetime()
    first = export.write_json(
        export.build_series(detections, generated_at=stamp), tmp_path / "a.json"
    )
    second = export.write_json(
        export.build_series(detections, generated_at=stamp), tmp_path / "b.json"
    )
    assert first.read_bytes() == second.read_bytes()
