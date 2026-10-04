"""Contract tests for src/api.

Every response is validated against the real contract schema
(``docs/contract.schema.json``, exported from the frontend's zod types), so a
backend payload and a mock file are held to the same shape. The endpoints are
called through FastAPI's ASGI test client, so routing, query parsing and
status codes are exercised, not the builder functions in isolation.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import jsonschema
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.acquire import safe
from src.api import dataset as dataset_module
from src.api.main import app
from src.demo import demo_detections

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((REPO_ROOT / "docs" / "contract.schema.json").read_text())
MOCK_DIR = REPO_ROOT / "web" / "public" / "mock"

#: The seven endpoints and the contract definition each one must satisfy.
ENDPOINTS = {
    "meta": {},
    "series": {},
    "cells": {},
    "baseline": {},
    "anomaly": {"date": "2019-06-01"},
    "validation": {},
    "methods": {},
}


def assert_matches(endpoint: str, payload: dict) -> None:
    jsonschema.validate(payload, CONTRACT["definitions"][endpoint])


@pytest.fixture(autouse=True)
def _fresh_dataset(monkeypatch: pytest.MonkeyPatch):
    """Reload the dataset for every test and default to the fixture tier."""
    monkeypatch.setenv("OFFLINE", "1")
    monkeypatch.setattr(safe, "FIXTURE_DIR", REPO_ROOT / "demo_fixtures")
    dataset_module.reset_dataset_cache()
    yield
    dataset_module.reset_dataset_cache()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def fixture_frame() -> pd.DataFrame:
    """A small real-shaped detection set for the temp-cache tests."""
    return demo_detections(days=120)


# --------------------------------------------------------------------------
# Every endpoint answers and every answer satisfies the contract
# --------------------------------------------------------------------------


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("endpoint,params", sorted(ENDPOINTS.items()))
def test_endpoint_matches_the_contract(client: TestClient, endpoint: str, params: dict):
    response = client.get(f"/api/{endpoint}", params=params)
    assert response.status_code == 200, response.text
    assert_matches(endpoint, response.json())


def test_every_response_carries_the_meta_block(client: TestClient):
    for endpoint, params in ENDPOINTS.items():
        payload = client.get(f"/api/{endpoint}", params=params).json()
        assert "meta" in payload, endpoint
        assert payload["meta"]["source"] in {"mock", "live", "cache", "fixture"}


def test_meta_reports_the_fixture_source_and_the_region(client: TestClient):
    meta = client.get("/api/meta").json()
    # OFFLINE=1 forces the fixture tier.
    assert meta["meta"]["source"] == "fixture"
    assert meta["meta"]["region"]["bbox"] == [88.0, 20.0, 93.0, 27.0]
    assert {s["product"] for s in meta["sensors"]} == {
        "MODIS_SP",
        "VIIRS_SNPP_SP",
        "VIIRS_NOAA20_SP",
        "VIIRS_NOAA21_SP",
    }


def test_mock_files_and_api_responses_share_one_schema():
    """The same JSON Schema holds for the frontend mocks and the API."""
    for endpoint in ENDPOINTS:
        mock = MOCK_DIR / f"{endpoint}.json"
        assert mock.exists(), f"missing mock file {mock}"
        assert_matches(endpoint, json.loads(mock.read_text()))


# --------------------------------------------------------------------------
# Payload internals
# --------------------------------------------------------------------------


def test_series_rows_are_internally_consistent(client: TestClient):
    rows = client.get("/api/series").json()["rows"]
    assert rows
    for row in rows[:50]:
        # Raw counts partition by sensor, so the total is the exact sum.
        assert row["raw_total"] == row["raw_modis"] + row["raw_viirs"]
        # Harmonized counts are distinct cells, so a cell both sensors hit in
        # one day is one cell-day in the total but two across the families:
        # the total is bounded by max(...) <= total <= sum(...).
        per_family = row["harm_modis"] + row["harm_viirs"]
        assert max(row["harm_modis"], row["harm_viirs"]) <= row["harm_total"] <= per_family


def test_methods_cites_every_dataset_with_a_url(client: TestClient):
    payload = client.get("/api/methods").json()
    assert payload["confidence_mapping"] == {"l": 25.0, "n": 60.0, "h": 90.0}
    ids = {d["id"] for d in payload["datasets"]}
    assert ids == {
        "FIRMS_MODIS_SP",
        "FIRMS_VIIRS_SNPP_SP",
        "FIRMS_VIIRS_NOAA20_SP",
        "FIRMS_VIIRS_NOAA21_SP",
    }
    assert all(d["url"].startswith("https://") for d in payload["datasets"])


def test_validation_shows_harmonization_beating_raw(client: TestClient):
    payload = client.get("/api/validation").json()
    assert payload["harmonized"]["pearson"] > payload["raw"]["pearson"]
    assert payload["cell_sweep"]


# --------------------------------------------------------------------------
# Query parameters
# --------------------------------------------------------------------------


def test_cells_window_narrows_the_answer(client: TestClient):
    everything = client.get("/api/cells").json()
    windowed = client.get("/api/cells", params={"start": "2019-02-01", "end": "2019-02-28"}).json()
    assert windowed["rows"], "the February window should still contain fires"
    assert sum(r["raw"] for r in windowed["rows"]) < sum(r["raw"] for r in everything["rows"])
    assert windowed["meta"]["date_range"] == ["2019-01-01", "2020-12-31"]


def test_cells_rejects_a_reversed_window(client: TestClient):
    response = client.get("/api/cells", params={"start": "2019-06-30", "end": "2019-06-01"})
    assert response.status_code == 422


def test_anomaly_answers_for_the_requested_day(client: TestClient):
    payload = client.get("/api/anomaly", params={"date": "2019-06-01"}).json()
    assert payload["date"] == "2019-06-01"
    assert 0.0 <= payload["percentile"] <= 100.0
    assert payload["years_used"] >= 1


def test_anomaly_answers_for_a_quiet_day_with_a_real_zero(client: TestClient):
    """A day with no detections is a zero count, not a missing day."""
    payload = client.get("/api/anomaly", params={"date": "2019-01-01"}).json()
    assert payload["date"] == "2019-01-01"
    assert payload["value"] >= 0.0


def test_anomaly_outside_the_range_is_404(client: TestClient):
    response = client.get("/api/anomaly", params={"date": "1999-01-01"})
    assert response.status_code == 404
    assert "outside the dataset range" in response.json()["detail"]


def test_anomaly_requires_a_date(client: TestClient):
    assert client.get("/api/anomaly").status_code == 422
    assert client.get("/api/anomaly", params={"date": "not-a-date"}).status_code == 422


def test_anomaly_accepts_a_bbox(client: TestClient):
    payload = client.get(
        "/api/anomaly", params={"date": "2019-06-01", "bbox": "88,20,93,27"}
    ).json()
    assert_matches("anomaly", payload)


def test_anomaly_rejects_a_malformed_bbox(client: TestClient):
    for bad in ("88,20,93", "a,b,c,d", "93,20,88,27"):
        response = client.get("/api/anomaly", params={"date": "2019-06-01", "bbox": bad})
        assert response.status_code == 422, bad


# --------------------------------------------------------------------------
# Offline-first resolution: cache, fixture, OFFLINE
# --------------------------------------------------------------------------


def _write_cache(directory: Path, frame: pd.DataFrame) -> Path:
    raw = directory / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    path = raw / "detections.parquet"
    frame.to_parquet(path, index=False)
    return path


def test_cache_is_served_when_present(client: TestClient, tmp_path, fixture_frame, monkeypatch):
    monkeypatch.delenv("OFFLINE", raising=False)
    monkeypatch.setattr(safe, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(safe, "FIXTURE_DIR", tmp_path / "empty")
    _write_cache(tmp_path, fixture_frame)
    dataset_module.reset_dataset_cache()

    meta = client.get("/api/meta").json()
    assert meta["meta"]["source"] == "cache"
    assert meta["meta"]["date_range"] == ["2019-01-01", "2019-04-30"]


def test_offline_forces_the_fixture_even_with_a_cache(
    client: TestClient, tmp_path, fixture_frame, monkeypatch
):
    monkeypatch.setenv("OFFLINE", "1")
    monkeypatch.setattr(safe, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(safe, "FIXTURE_DIR", tmp_path / "fixtures")
    _write_cache(tmp_path, fixture_frame)
    (tmp_path / "fixtures").mkdir()
    fixture_frame.to_parquet(tmp_path / "fixtures" / dataset_module.FIXTURE_NAME, index=False)
    dataset_module.reset_dataset_cache()

    # Both tiers exist and hold the same bytes; OFFLINE must pick the fixture.
    assert client.get("/api/meta").json()["meta"]["source"] == "fixture"


def test_fixture_is_served_when_there_is_no_cache(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.delenv("OFFLINE", raising=False)
    monkeypatch.setattr(safe, "CACHE_DIR", tmp_path / "empty")
    monkeypatch.setattr(safe, "FIXTURE_DIR", REPO_ROOT / "demo_fixtures")
    dataset_module.reset_dataset_cache()
    assert client.get("/api/meta").json()["meta"]["source"] == "fixture"


def test_missing_cache_and_fixture_is_a_503(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.setattr(safe, "CACHE_DIR", tmp_path / "empty")
    monkeypatch.setattr(safe, "FIXTURE_DIR", tmp_path / "empty")
    dataset_module.reset_dataset_cache()
    response = client.get("/api/meta")
    assert response.status_code == 503
    assert "no detections to serve" in response.json()["detail"]


# --------------------------------------------------------------------------
# The API is offline by construction
# --------------------------------------------------------------------------


def test_endpoints_work_with_all_network_blocked(client: TestClient, monkeypatch):
    """The API must answer with sockets unavailable — it has no network tier."""

    def blocked(*_args, **_kwargs):
        raise AssertionError("the API attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    for endpoint, params in ENDPOINTS.items():
        response = client.get(f"/api/{endpoint}", params=params)
        assert response.status_code == 200, endpoint
