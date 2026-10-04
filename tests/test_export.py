"""Tests for src/compute/export.py.

Every payload is validated against the real contract schema
(``docs/contract.schema.json``, exported from the frontend's zod types), so
a backend payload and a mock file are held to the same shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pandas as pd
import pytest

from src.compute import export, harmonize
from tests.synthetic import synthetic_detections

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((REPO_ROOT / "docs" / "contract.schema.json").read_text())


@pytest.fixture(scope="module")
def detections() -> pd.DataFrame:
    return harmonize.harmonize(synthetic_detections(days=120))


@pytest.fixture(scope="module")
def series(detections: pd.DataFrame) -> pd.Series:
    return harmonize.harmonized_series(detections)


def assert_matches(endpoint: str, payload: dict) -> None:
    jsonschema.validate(payload, CONTRACT["definitions"][endpoint])


# --------------------------------------------------------------------------
# The schema itself must be the one the frontend ships
# --------------------------------------------------------------------------


def test_every_endpoint_has_a_definition():
    assert set(CONTRACT["definitions"]) == {
        "meta",
        "series",
        "cells",
        "baseline",
        "anomaly",
        "validation",
        "methods",
    }


# --------------------------------------------------------------------------
# Payloads
# --------------------------------------------------------------------------


def test_meta_payload_matches_the_contract(detections):
    assert_matches("meta", export.build_meta_response(detections))


def test_series_payload_matches_the_contract(detections):
    payload = export.build_series(detections)
    assert_matches("series", payload)
    assert payload["rows"], "the synthetic data has detections"
    first = payload["rows"][0]
    assert first["raw_total"] == first["raw_modis"] + first["raw_viirs"]


def test_cells_payload_matches_the_contract(detections):
    payload = export.build_cells(detections)
    assert_matches("cells", payload)
    assert payload["rows"]
    west, south, east, north = payload["rows"][0]["bounds"]
    assert west < east and south < north


def test_baseline_payload_matches_the_contract(series):
    payload = export.build_baseline(series, window_days=7)
    assert_matches("baseline", payload)
    assert payload["window_days"] == 7
    assert payload["rows"] and payload["years_used"] >= 1


def test_anomaly_payload_matches_the_contract(series):
    date_ = series.index[len(series) // 2]
    payload = export.build_anomaly(series, date_=date_)
    assert_matches("anomaly", payload)
    assert payload["date"] == pd.Timestamp(date_).strftime("%Y-%m-%d")


def test_validation_payload_matches_the_contract(detections):
    payload = export.build_validation(detections)
    assert_matches("validation", payload)
    assert payload["cell_sweep"]


def test_methods_payload_matches_the_contract(detections):
    payload = export.build_methods()
    assert_matches("methods", payload)
    assert payload["confidence_mapping"] == {"l": 25.0, "n": 60.0, "h": 90.0}
    assert {d["id"] for d in payload["datasets"]} == {
        "FIRMS_MODIS_SP",
        "FIRMS_VIIRS_SNPP_SP",
        "FIRMS_VIIRS_NOAA20_SP",
        "FIRMS_VIIRS_NOAA21_SP",
    }


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
        "validation.json",
        "methods.json",
    }
    for path in written:
        payload = json.loads(path.read_text())
        assert_matches(path.stem, payload)


def test_written_json_is_byte_stable_for_a_fixed_timestamp(tmp_path, detections):
    stamp = pd.Timestamp("2026-10-04T00:00:00Z").to_pydatetime()
    first = export.write_json(
        export.build_series(detections, generated_at=stamp), tmp_path / "a.json"
    )
    second = export.write_json(
        export.build_series(detections, generated_at=stamp), tmp_path / "b.json"
    )
    assert first.read_bytes() == second.read_bytes()
