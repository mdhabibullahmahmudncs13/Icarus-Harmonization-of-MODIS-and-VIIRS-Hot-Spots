"""The CSV export: the filtered hotspot records, downloadable.

The challenge asks for the records behind the view to be exportable, so the
export is a deliverable in its own right and is tested like one: the route
answers, the file is well-formed CSV, the window and the area filter it, and
the bytes are stable.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.acquire import safe
from src.api import dataset as dataset_module
from src.api.main import app
from src.compute import export

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def test_the_export_route_answers_as_csv(client: TestClient):
    response = client.get("/api/v1/export")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert ".csv" in response.headers["content-disposition"]


def test_the_export_carries_the_hotspot_columns(client: TestClient):
    rows = _rows(client.get("/api/v1/export").text)
    assert rows, "the fixture tier must export some rows"
    assert set(export.CSV_COLUMNS) <= set(rows[0])
    # The record itself, not a derived cell-day.
    assert {"latitude", "longitude", "acq_date", "satellite"} <= set(rows[0])


def test_the_export_is_well_formed_csv(client: TestClient):
    text = client.get("/api/v1/export").text
    # Every line has the same number of fields, so a spreadsheet reads it.
    widths = {len(row) for row in csv.reader(io.StringIO(text))}
    assert len(widths) == 1, f"ragged CSV: {widths}"


def test_the_date_window_narrows_the_export(client: TestClient):
    everything = client.get("/api/v1/export").text
    window = client.get("/api/v1/export?start=2019-06-01&end=2019-06-30").text
    assert len(window.splitlines()) < len(everything.splitlines())
    dates = {row["acq_date"] for row in _rows(window)}
    assert dates
    assert all(date.startswith("2019-06") for date in dates)


def test_the_export_is_ordered_so_two_runs_agree(client: TestClient):
    first = client.get("/api/v1/export").text
    second = client.get("/api/v1/export").text
    assert first == second
    dates = [row["acq_date"] for row in _rows(first)]
    assert dates == sorted(dates)


def test_the_area_filters_the_export(client: TestClient):
    """A bbox the fixture does not reach must come back empty, not all of it."""
    response = client.get("/api/v1/export?bbox=0,0,0.5,0.5")
    assert response.status_code == 200, response.text
    rows = _rows(response.text)
    assert rows == []


def test_a_reversed_window_is_refused(client: TestClient):
    response = client.get("/api/v1/export?start=2019-06-30&end=2019-06-01")
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "invalid_window"
    assert body["field"] == "start"


def test_an_empty_area_still_downloads_a_header(client: TestClient):
    """A download with no rows must still be a CSV a tool can read."""
    response = client.get("/api/v1/export?bbox=0,0,0.5,0.5")
    assert response.status_code == 200
    assert response.text.strip().splitlines() == [",".join(export.CSV_COLUMNS)]


def test_the_builder_agrees_with_the_frame_it_is_given():
    """The builder is the tested unit; the route is a thin wrapper over it."""
    from src.demo import demo_detections

    detections = demo_detections(days=30)
    text = export.build_csv(detections)
    rows = _rows(text)
    assert len(rows) == len(detections)
    assert {row["sensor_family"] for row in rows} <= {"MODIS", "VIIRS"}


def test_the_builder_narrows_a_window():
    from src.demo import demo_detections

    detections = demo_detections(days=30)
    text = export.build_csv(detections, start=pd.Timestamp("2019-01-15"), end=pd.Timestamp("2019-01-20"))
    rows = _rows(text)
    assert rows
    assert all("2019-01-15" <= row["acq_date"] <= "2019-01-20" for row in rows)


def test_the_unversioned_alias_answers_too(client: TestClient):
    assert client.get("/api/export").status_code == 200
