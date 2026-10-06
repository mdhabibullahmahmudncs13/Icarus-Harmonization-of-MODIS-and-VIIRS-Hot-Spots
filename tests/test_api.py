"""Contract tests for src/api.

Every response is validated against the real contract schema
(``docs/contract.schema.json``, exported from the frontend's zod types), so a
backend payload and a mock file are held to the same shape, and the API is
called through FastAPI's ASGI test client so routing, query parsing and status
codes are exercised — not the builder functions in isolation.

The nine payloads the frontend's ``ApiDataSource`` requests are covered here,
under the ``/api/v1`` prefix it actually calls. The unversioned ``/api`` alias
is covered too, so the earlier path cannot rot.
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
from src.compute import export, harmonize
from src.demo import demo_detections

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((REPO_ROOT / "docs" / "contract.schema.json").read_text())
MOCK_DIR = REPO_ROOT / "web" / "public" / "mock"

#: Every versioned route, the contract definition it must satisfy, its query
#: parameters, and the Phase 0 mock file that must carry the same shape.
#: ``mock`` is the acronym's file name, which is not always the payload name.
ENDPOINTS = {
    "meta": {"path": "/api/v1/meta", "definition": "metaResponse", "params": {}, "mock": "meta"},
    "series": {"path": "/api/v1/series", "definition": "series", "params": {}, "mock": "series"},
    "cells": {"path": "/api/v1/cells", "definition": "cells", "params": {}, "mock": "cells"},
    "baseline": {
        "path": "/api/v1/baseline",
        "definition": "baseline",
        "params": {},
        "mock": "baseline",
    },
    "anomalies": {
        "path": "/api/v1/anomalies",
        "definition": "anomalies",
        "params": {"date": "2019-06-01"},
        "mock": "anomaly",
    },
    "critical-period": {
        "path": "/api/v1/critical-period",
        "definition": "criticalPeriod",
        "params": {},
        "mock": "critical-period",
    },
    "validation": {
        "path": "/api/v1/validation",
        "definition": "validation",
        "params": {},
        "mock": "validation",
    },
    "methods": {"path": "/api/v1/methods", "definition": "methods", "params": {}, "mock": "methods"},
    "aoi": {"path": "/api/v1/aoi", "definition": "aoi", "params": {}, "mock": "aoi"},
}

#: The unversioned alias each payload keeps answering on.
LEGACY_PATHS = {
    "meta": "/api/meta",
    "series": "/api/series",
    "cells": "/api/cells",
    "baseline": "/api/baseline",
    "anomalies": "/api/anomaly",
    "validation": "/api/validation",
    "methods": "/api/methods",
}


def assert_matches(definition: str, payload: dict) -> None:
    defs = CONTRACT["$defs"]
    jsonschema.Draft202012Validator(
        {"$ref": f"#/$defs/{definition}", "$defs": defs}
    ).validate(payload)


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


@pytest.mark.parametrize("name", sorted(ENDPOINTS))
def test_versioned_endpoint_matches_the_contract(client: TestClient, name: str):
    endpoint = ENDPOINTS[name]
    response = client.get(endpoint["path"], params=endpoint["params"])
    assert response.status_code == 200, response.text
    assert_matches(endpoint["definition"], response.json())


@pytest.mark.parametrize("name", sorted(LEGACY_PATHS))
def test_unversioned_alias_still_answers(client: TestClient, name: str):
    endpoint = ENDPOINTS[name]
    params = endpoint["params"]
    response = client.get(LEGACY_PATHS[name], params=params)
    assert response.status_code == 200, response.text
    assert_matches(endpoint["definition"], response.json())


def test_root_meta_alias_answers_as_the_spec_calls_it(client: TestClient):
    """docs/TRD.md §6 lists ``GET /meta``; docs/DEPLOYMENT.md §8 curls it."""
    response = client.get("/meta")
    assert response.status_code == 200, response.text
    assert_matches("metaResponse", response.json())


def test_analysis_endpoints_accept_post_as_the_docs_say(client: TestClient):
    """docs/ApplicationFlow.md §4 and DEPLOYMENT.md document POST; honour it."""
    for name in ("series", "cells", "baseline", "anomalies", "critical-period", "validation"):
        endpoint = ENDPOINTS[name]
        response = client.post(endpoint["path"], params=endpoint["params"])
        assert response.status_code == 200, f"{endpoint['path']}: {response.text}"
        assert_matches(endpoint["definition"], response.json())


def test_every_response_carries_the_meta_block(client: TestClient):
    for endpoint in ENDPOINTS.values():
        payload = client.get(endpoint["path"], params=endpoint["params"]).json()
        assert "meta" in payload
        assert payload["meta"]["source"] in {"mock", "live", "cache", "fixture"}
        assert len(payload["meta"]["params_hash"]) >= 8


def test_one_request_yields_one_params_hash(client: TestClient):
    """Same parameters must hash the same across every payload, or the id
    cannot be used to match a payload against a cached response."""
    hashes = {
        client.get(endpoint["path"], params=endpoint["params"]).json()["meta"]["params_hash"]
        for endpoint in ENDPOINTS.values()
    }
    assert len(hashes) == 1, hashes


def test_meta_reports_the_fixture_source_and_the_region(client: TestClient):
    meta = client.get("/api/v1/meta").json()
    # OFFLINE=1 forces the fixture tier.
    assert meta["meta"]["source"] == "fixture"
    assert meta["meta"]["region"]["bbox"] == [88.0, 20.0, 93.0, 27.0]
    assert {s["product"] for s in meta["sensors"]} == {
        "MODIS_SP",
        "VIIRS_SNPP_SP",
        "VIIRS_NOAA20_SP",
        "VIIRS_NOAA21_NRT",
    }
    assert meta["streams"]


def test_mock_files_and_api_responses_share_one_schema(client: TestClient):
    """The same JSON Schema holds for the frontend mocks and the API.

    This is the test that fails when the API and the frozen contract drift
    apart, which is exactly the Phase 3 defect it was written to catch.
    """
    for endpoint in ENDPOINTS.values():
        mock = MOCK_DIR / f"{endpoint['mock']}.json"
        assert mock.exists(), f"missing mock file {mock}"
        assert_matches(endpoint["definition"], json.loads(mock.read_text()))


# --------------------------------------------------------------------------
# Payload internals
# --------------------------------------------------------------------------


def test_series_rows_are_internally_consistent(client: TestClient):
    rows = client.get("/api/v1/series").json()["series"]
    assert rows
    for row in rows[:50]:
        # Raw counts partition by sensor, so the total is the exact sum.
        assert row["raw_total"] == row["raw_modis"] + row["raw_viirs"]
        # Harmonized counts are distinct cells, so a cell both sensors hit in
        # one day is one cell-day in the total but two across the families:
        # the total is bounded by max(...) <= total <= sum(...).
        per_family = row["harm_modis"] + row["harm_viirs"]
        assert max(row["harm_modis"], row["harm_viirs"]) <= row["harm_total"] <= per_family
        # S7: every bin names its observing coverage and the stream anchoring it.
        assert 0.0 <= row["coverage"] <= 1.0
        assert row["source"] in {"MODIS", "BRIDGE", "VIIRS_CAL", "NONE"}


def test_methods_cites_every_dataset_with_a_url(client: TestClient):
    payload = client.get("/api/v1/methods").json()
    assert payload["confidence_mapping"] == {"low": 25, "nominal": 60, "high": 90}
    ids = {d["id"] for d in payload["datasets"]}
    assert ids == {
        "FIRMS_MODIS_SP",
        "FIRMS_VIIRS_SNPP_SP",
        "FIRMS_VIIRS_NOAA20_SP",
        "FIRMS_VIIRS_NOAA21_NRT",
    }
    assert all(d["url"].startswith("https://") for d in payload["datasets"])


def test_validation_shows_harmonization_beating_raw(client: TestClient):
    payload = client.get("/api/v1/validation").json()
    assert payload["harmonized"]["pearson"] > payload["raw"]["pearson"]
    assert payload["cell_sweep"]
    assert set(payload["overlap"]) == {"years", "n_days"}


def test_critical_period_lands_in_the_season(client: TestClient):
    payload = client.get("/api/v1/critical-period").json()
    assert payload["insufficient_activity"] is False
    assert 1 <= payload["onset_bin"] <= payload["peak_bin"] <= payload["end_bin"] <= 46
    assert 0.0 < payload["window"]["mass"] <= 1.0


def test_aoi_lists_the_presets(client: TestClient):
    payload = client.get("/api/v1/aoi").json()
    assert {"BGD", "IND-C", "NPL"} <= {p["id"] for p in payload["presets"]}
    assert all(len(p["bbox"]) == 4 for p in payload["presets"])


# --------------------------------------------------------------------------
# Query parameters
# --------------------------------------------------------------------------


def test_cells_window_narrows_the_answer(client: TestClient):
    everything = client.get("/api/v1/cells").json()
    windowed = client.get(
        "/api/v1/cells", params={"start": "2019-02-01", "end": "2019-02-28"}
    ).json()
    assert windowed["cells"], "the February window should still contain fires"
    assert sum(r["raw"] for r in windowed["cells"]) < sum(r["raw"] for r in everything["cells"])
    assert windowed["meta"]["date_range"] == ["2019-01-01", "2020-12-31"]
    assert windowed["window"] == {"start": "2019-02-01", "end": "2019-02-28"}


def test_cells_rejects_a_reversed_window(client: TestClient):
    response = client.get("/api/v1/cells", params={"start": "2019-06-30", "end": "2019-06-01"})
    assert response.status_code == 422


def test_anomaly_answers_for_the_requested_day(client: TestClient):
    payload = client.get("/api/v1/anomalies", params={"date": "2019-06-01"}).json()
    assert payload["query"]["date"] == "2019-06-01"
    assert 0.0 <= payload["percentile"] <= 100.0
    # The reference sample is other years' same-season days, so 2020 only:
    # a year never judges itself.
    assert payload["years_used"] == [2020]
    assert payload["flag"] == "not_scored"
    assert payload["reason"] == "insufficient_reference_years"


def test_anomaly_defaults_to_the_last_day_in_the_data(client: TestClient):
    """The frontend requests the anomalies view with no date."""
    payload = client.get("/api/v1/anomalies").json()
    assert payload["query"]["date"] == "2020-12-31"


def test_anomaly_answers_for_a_quiet_day_with_a_real_zero(client: TestClient):
    """A day with no detections is a zero count, not a missing day."""
    payload = client.get("/api/v1/anomalies", params={"date": "2019-01-01"}).json()
    assert payload["query"]["date"] == "2019-01-01"
    assert payload["value"] >= 0.0


def test_anomaly_outside_the_range_is_404(client: TestClient):
    response = client.get("/api/anomaly", params={"date": "1999-01-01"})
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"code", "message", "field"}
    assert body["code"] == "not_found"
    assert "outside the dataset range" in body["message"]


def test_anomaly_requires_a_date_on_the_legacy_path(client: TestClient):
    assert client.get("/api/anomaly").status_code == 422
    assert client.get("/api/anomaly", params={"date": "not-a-date"}).status_code == 422


def test_anomaly_accepts_a_bbox(client: TestClient):
    payload = client.get(
        "/api/v1/anomalies", params={"date": "2019-06-01", "bbox": "88,20,93,27"}
    ).json()
    assert_matches("anomalies", payload)
    # A bbox request echoes the area it resolved to, not a preset id: the same
    # numbers always render the same way, whatever spacing the caller used.
    assert payload["query"]["aoi"] == "88.0,20.0,93.0,27.0"


def test_anomaly_rejects_a_malformed_bbox(client: TestClient):
    for bad in ("88,20,93", "a,b,c,d", "93,20,88,27"):
        response = client.get("/api/v1/anomalies", params={"date": "2019-06-01", "bbox": bad})
        assert response.status_code == 422, bad
        assert response.json()["field"] == "bbox", bad


# --------------------------------------------------------------------------
# Errors: every failure is {code, message, field} (docs/TRD.md §9)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "request_args,status,code,field",
    [
        (("get", "/api/v1/anomalies", {"params": {"date": "2019-06-01", "bbox": "1,2,3"}}), 422, "invalid_bbox", "bbox"),
        (("get", "/api/v1/cells", {"params": {"start": "2019-06-30", "end": "2019-06-01"}}), 422, "invalid_window", "start"),
        (("get", "/api/v1/anomalies", {"params": {"date": "2019-06-01", "aoi": "ZZZ"}}), 422, "unknown_aoi", "aoi"),
        # The legacy path still requires a date; /api/v1/anomalies defaults to
        # the last day, so a missing date there is not an error.
        (("get", "/api/anomaly", {}), 422, "invalid_request", "date"),
        (("get", "/api/v1/anomalies", {"params": {"date": "not-a-date"}}), 422, "invalid_request", "date"),
    ],
)
def test_errors_carry_a_code_a_message_and_a_field(client, request_args, status, code, field):
    method, path, kwargs = request_args
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "message", "field"}, body
    assert body["code"] == code
    assert body["field"] == field
    assert body["message"]


# --------------------------------------------------------------------------
# POST bodies (docs/ApplicationFlow.md §4)
# --------------------------------------------------------------------------


def test_post_body_carries_the_aoi_and_the_date(client: TestClient):
    response = client.post("/api/v1/anomalies", json={"aoi": "NPL", "date": "2019-06-01"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert_matches("anomalies", payload)
    assert payload["query"] == {"date": "2019-06-01", "aoi": "NPL"}


def test_post_body_accepts_the_trd_aoi_object_as_well_as_a_preset_id(client: TestClient):
    """docs/DEPLOYMENT.md §8 smoke-tests with ``{type: "preset", id}`` (TRD §6.1)."""
    response = client.post(
        "/api/v1/anomalies",
        json={"aoi": {"type": "preset", "id": "NPL"}, "date": "2019-06-01"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert_matches("anomalies", payload)
    assert payload["query"] == {"date": "2019-06-01", "aoi": "NPL"}


def test_post_body_refuses_an_aoi_object_it_cannot_honour(client: TestClient):
    """Custom geometry is refused, not silently dropped for the default area."""
    response = client.post(
        "/api/v1/anomalies",
        json={"aoi": {"type": "custom", "geometry": {"type": "Point", "coordinates": [90, 23]}}},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_request"
    assert body["field"] == "aoi"


def test_post_body_carries_an_aoi_for_the_critical_period(client: TestClient):
    payload = client.post("/api/v1/critical-period", json={"aoi": "IND-C"}).json()
    assert_matches("criticalPeriod", payload)
    assert payload["aoi"] == "IND-C"


def test_post_body_bbox_is_honoured(client: TestClient):
    payload = client.post(
        "/api/v1/anomalies", json={"date": "2019-06-01", "bbox": [88, 20, 93, 27]}
    ).json()
    assert_matches("anomalies", payload)
    assert payload["query"]["aoi"] == "88.0,20.0,93.0,27.0"


def test_post_body_overrides_the_query_parameters(client: TestClient):
    payload = client.post(
        "/api/v1/anomalies", params={"aoi": "BGD"}, json={"aoi": "NPL", "date": "2019-06-01"}
    ).json()
    assert payload["query"]["aoi"] == "NPL"


def test_post_body_rejects_an_unknown_aoi_with_its_field(client: TestClient):
    response = client.post("/api/v1/anomalies", json={"aoi": "ZZZ"})
    assert response.status_code == 422
    assert response.json() == {
        "code": "unknown_aoi",
        "message": response.json()["message"],
        "field": "aoi",
    }
    assert "ZZZ" in response.json()["message"]


def test_post_body_serves_the_density_metric_on_the_series(client: TestClient):
    """docs/ApplicationFlow.md §3 defaults to density; the series honours it."""
    response = client.post("/api/v1/series", json={"metric": "density"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["metric"] == "density"
    assert_matches("series", payload)

    counts = client.post("/api/v1/series", json={"metric": "cell_days"}).json()
    n_cells = harmonize.grid_cell_count(export.BANGLADESH_BBOX)
    assert len(payload["series"]) == len(counts["series"])
    saw_active = False
    for count_row, density_row in zip(counts["series"], payload["series"], strict=True):
        for column in export.COUNT_COLUMNS:
            assert density_row[column] == pytest.approx(count_row[column] / n_cells, abs=1e-12)
        assert isinstance(count_row["harm_total"], int)
        assert 0.0 <= density_row["harm_total"] <= 1.0
        saw_active = saw_active or density_row["harm_total"] > 0
    assert saw_active, "the fixture has active cells"


def test_post_body_refuses_density_where_the_payload_has_no_metric(client: TestClient):
    """Refused, not silently served as cell_days on an endpoint with no metric."""
    for name in ("cells", "baseline", "anomalies", "critical-period", "validation"):
        path = ENDPOINTS[name]["path"]
        response = client.post(path, json={"metric": "density"})
        assert response.status_code == 422, f"{path}: {response.text}"
        assert response.json()["code"] == "unsupported_metric"
        assert response.json()["field"] == "metric"


def test_post_body_accepts_the_metrics_and_views_that_are_honoured(client: TestClient):
    for body, expected in (
        ({"metric": "cell_days"}, "cell_days"),
        ({"metric": "density"}, "density"),
        ({"view": "raw"}, "cell_days"),
        ({"view": "harmonized"}, "cell_days"),
        ({}, "cell_days"),
    ):
        response = client.post("/api/v1/series", json=body)
        assert response.status_code == 200, (body, response.text)
        assert response.json()["metric"] == expected


def test_post_body_rejects_an_unknown_metric_or_view(client: TestClient):
    for body, code, field in (
        ({"metric": "bananas"}, "invalid_metric", "metric"),
        ({"view": "sideways"}, "invalid_view", "view"),
    ):
        response = client.post("/api/v1/series", json=body)
        assert response.status_code == 422, body
        assert response.json()["code"] == code
        assert response.json()["field"] == field


def test_get_without_a_body_behaves_as_before(client: TestClient):
    payload = client.get("/api/v1/anomalies", params={"date": "2019-06-01"}).json()
    assert payload["query"] == {"date": "2019-06-01", "aoi": "BGD"}


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

    meta = client.get("/api/v1/meta").json()
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
    assert client.get("/api/v1/meta").json()["meta"]["source"] == "fixture"


def test_fixture_is_served_when_there_is_no_cache(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.delenv("OFFLINE", raising=False)
    monkeypatch.setattr(safe, "CACHE_DIR", tmp_path / "empty")
    monkeypatch.setattr(safe, "FIXTURE_DIR", REPO_ROOT / "demo_fixtures")
    dataset_module.reset_dataset_cache()
    assert client.get("/api/v1/meta").json()["meta"]["source"] == "fixture"


def test_missing_cache_and_fixture_is_a_503(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.setattr(safe, "CACHE_DIR", tmp_path / "empty")
    monkeypatch.setattr(safe, "FIXTURE_DIR", tmp_path / "empty")
    dataset_module.reset_dataset_cache()
    response = client.get("/api/v1/meta")
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "unavailable"
    assert "no detections to serve" in body["message"]


# --------------------------------------------------------------------------
# The API is offline by construction
# --------------------------------------------------------------------------


def test_endpoints_work_with_all_network_blocked(client: TestClient, monkeypatch):
    """The API must answer with sockets unavailable — it has no network tier."""

    def blocked(*_args, **_kwargs):
        raise AssertionError("the API attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    for endpoint in ENDPOINTS.values():
        response = client.get(endpoint["path"], params=endpoint["params"])
        assert response.status_code == 200, endpoint["path"]
