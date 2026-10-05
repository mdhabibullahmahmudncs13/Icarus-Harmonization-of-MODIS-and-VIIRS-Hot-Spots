"""Phase 0 contract tests.

Every committed mock payload must validate against docs/contract.schema.json,
and every payload must be labelled as mock (never evidence).

Run:
    python3 -m pytest tests/test_contract.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "contract.schema.json"
MOCK_DIR = ROOT / "web" / "public" / "mock"

DEF_FOR = {
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
def schema() -> dict:
    assert SCHEMA_PATH.exists(), f"missing schema: {SCHEMA_PATH}"
    return json.loads(SCHEMA_PATH.read_text())


def mock_payloads() -> list[tuple[str, dict]]:
    assert MOCK_DIR.exists(), f"missing mock dir: {MOCK_DIR}"
    out = []
    for path in sorted(MOCK_DIR.glob("*.json")):
        out.append((path.stem, json.loads(path.read_text())))
    return out


def test_schema_defs_cover_every_payload(schema: dict) -> None:
    defs = schema["$defs"]
    for name in DEF_FOR:
        assert DEF_FOR[name] in defs, f"no $defs entry for {name!r}"


@pytest.mark.parametrize("name,payload", mock_payloads(), ids=lambda v: v if isinstance(v, str) else "")
def test_payload_matches_schema(schema: dict, name: str, payload: dict) -> None:
    defs = schema["$defs"]
    validator = Draft202012Validator(
        {"$ref": f"#/$defs/{DEF_FOR[name]}", "$defs": defs},
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors)


@pytest.mark.parametrize("name,payload", mock_payloads(), ids=lambda v: v if isinstance(v, str) else "")
def test_payload_is_labelled_mock(name: str, payload: dict) -> None:
    assert payload["meta"]["source"] == "mock", f"{name} is not labelled as mock"
    assert payload["meta"]["params_hash"], f"{name} has no params_hash"


def test_series_includes_the_sensor_transition() -> None:
    """The demo depends on a window that crosses the VIIRS start."""
    series = json.loads((MOCK_DIR / "series.json").read_text())["series"]
    dates = [row["date"] for row in series]
    assert any(d < "2012-01-20" for d in dates), "no pre-VIIRS days"
    assert any(d >= "2012-01-20" for d in dates), "no post-VIIRS days"
