"""Tests for tools/export_payloads.py — the static-export CLI.

The payloads it writes are the same ones the API serves, so writing them is
also the broadest contract check in the project: every payload is validated
against ``docs/contract.schema.json`` here, and the file list is the contract's
own set of payloads.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pandas as pd
import pytest

from src.compute import export, harmonize
from tests.synthetic import synthetic_detections
from tools import export_payloads

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((REPO_ROOT / "docs" / "contract.schema.json").read_text())

#: The contract entry each written file must match.
DEFINITION_FOR = {
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


@pytest.fixture(scope="module")
def detections() -> pd.DataFrame:
    return harmonize.harmonize(synthetic_detections(days=120))


def test_write_all_writes_every_file_and_is_serializable(tmp_path, detections):
    written = export_payloads.write_all(
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
    for path in written:
        payload = json.loads(path.read_text())
        jsonschema.Draft202012Validator(
            {"$ref": f"#/$defs/{DEFINITION_FOR[path.stem]}", "$defs": CONTRACT["$defs"]}
        ).validate(payload)


def test_written_json_is_byte_stable_for_a_fixed_timestamp(tmp_path, detections):
    stamp = pd.Timestamp("2026-10-04T00:00:00Z").to_pydatetime()
    first = export_payloads.write_json(
        export.build_series(detections, generated_at=stamp), tmp_path / "a.json"
    )
    second = export_payloads.write_json(
        export.build_series(detections, generated_at=stamp), tmp_path / "b.json"
    )
    assert first.read_bytes() == second.read_bytes()


def test_load_detections_says_so_when_the_cache_is_empty(tmp_path):
    with pytest.raises(FileNotFoundError, match="make cache"):
        export_payloads.load_detections(str(tmp_path / "*.parquet"))
