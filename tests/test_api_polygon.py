"""The API side of a drawn polygon (docs/TRD.md §6.1).

The polygon has to do two honest jobs: decide which detections count, and say
how many grid cells the area holds, so a density means what it says. A drawn
shape is not its bounding box, and the API must not quietly treat it as one.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient

from src.acquire import safe
from src.api import dataset as dataset_module
from src.api.main import app
from src.compute import geometry, harmonize

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((REPO_ROOT / "docs" / "contract.schema.json").read_text())

#: A square well inside the fixture's own extent, in order — the shape the
#: tests draw. The fixture spans lon 88.09–88.70 and lat 22.81–23.37, so a
#: square around Dhaka's edge would hold only part of the data.
SQUARE = [[88.2, 23.0], [88.6, 23.0], [88.6, 23.3], [88.2, 23.3]]

#: A diagonal shape in the same box: half of the square, cut corner to
#: corner. It is the case a bounding box cannot express, so it is the case
#: the polygon tests have to prove.
TRIANGLE = [[88.2, 23.0], [88.6, 23.0], [88.6, 23.3]]


def _polygon(coordinates: list[list[float]]) -> dict:
    """The AOI object ``docs/TRD.md`` §6.1 defines for a drawn shape."""
    return {"type": "geojson", "geometry": {"type": "Polygon", "coordinates": [coordinates]}}


@pytest.fixture(autouse=True)
def _offline_fixture(monkeypatch: pytest.MonkeyPatch):
    """Serve the committed fixture, so the answers are about the geometry."""
    monkeypatch.setenv("OFFLINE", "1")
    monkeypatch.setattr(safe, "FIXTURE_DIR", REPO_ROOT / "demo_fixtures")
    dataset_module.reset_dataset_cache()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _assert_matches(definition: str, payload: dict) -> None:
    jsonschema.Draft202012Validator(
        {"$ref": f"#/$defs/{definition}", "$defs": CONTRACT["$defs"]}
    ).validate(payload)


def _total(payload: dict, column: str) -> float:
    """The sum of a count column over every day.

    Not the first day: most days hold no fire at all, so a single day proves
    nothing about the area.
    """
    return sum(float(row[column]) for row in payload["series"])


def test_a_polygon_is_answered_and_matches_the_contract(client: TestClient):
    response = client.post("/api/v1/series", json={"aoi": _polygon(SQUARE)})
    assert response.status_code == 200, response.text
    _assert_matches("series", response.json())


def test_the_region_carries_the_drawn_shape(client: TestClient):
    """The bbox is the extent; the ring is the shape the user drew."""
    payload = client.post("/api/v1/meta", json={"aoi": _polygon(SQUARE)}).json()
    region = payload["meta"]["region"]
    assert region["bbox"] == [88.2, 23.0, 88.6, 23.3]
    assert region["polygon"][0] == [88.2, 23.0]


def test_a_polygon_filters_out_the_detections_outside_it(client: TestClient):
    """A shape is not its box: the count must drop below the box's.

    The triangle is half the square, so the two differ by a wide margin
    rather than by a rounding error.
    """
    boxed = client.post("/api/v1/series", json={"bbox": [88.2, 23.0, 88.6, 23.3]}).json()
    drawn = client.post("/api/v1/series", json={"aoi": _polygon(TRIANGLE)}).json()
    assert _total(drawn, "raw_total") < _total(boxed, "raw_total")


def test_a_polygon_and_its_box_have_different_params_hashes(client: TestClient):
    """Two areas that share a box must not share a hash.

    The hash is what marks a cached payload stale, so two different shapes
    with the same bounding box have to hash differently.
    """
    boxed = client.post("/api/v1/meta", json={"bbox": [88.2, 23.0, 88.6, 23.3]}).json()
    drawn = client.post("/api/v1/meta", json={"aoi": _polygon(TRIANGLE)}).json()
    assert boxed["meta"]["params_hash"] != drawn["meta"]["params_hash"]


def test_the_density_divisor_is_the_cells_the_shape_holds(client: TestClient):
    """A shape covers fewer cells than its box, so its density is higher."""
    ring = geometry.close_ring([tuple(p) for p in TRIANGLE])
    shape_cells = geometry.ring_cell_count(ring)
    box_cells = harmonize.grid_cell_count(geometry.ring_bbox(ring))
    assert 0 < shape_cells < box_cells

    drawn = client.post(
        "/api/v1/series", json={"aoi": _polygon(TRIANGLE), "metric": "density"}
    ).json()
    boxed = client.post(
        "/api/v1/series",
        json={"bbox": [88.2, 23.0, 88.6, 23.3], "metric": "density"},
    ).json()
    # The same detections, divided by a smaller area, is a larger density.
    assert _total(drawn, "harm_total") > _total(boxed, "harm_total")


def test_the_cells_payload_keeps_only_the_cells_inside_the_shape(client: TestClient):
    """A cell counts when its centre is inside the shape.

    The cell edges are not clipped to the polygon — the grid is the same
    everywhere else in the project — so the test is about the centre, which
    is the rule the density divisor uses too.
    """
    payload = client.post("/api/v1/cells", json={"aoi": _polygon(TRIANGLE)}).json()
    _assert_matches("cells", payload)
    ring = geometry.close_ring([tuple(p) for p in TRIANGLE])
    for cell in payload["cells"]:
        west, south, east, north = cell["bounds"]
        centre_lon = (west + east) / 2
        centre_lat = (south + north) / 2
        assert geometry.point_in_ring(centre_lon, centre_lat, ring)


def test_a_self_crossing_polygon_is_refused(client: TestClient):
    """A nonsense area is worse than no area."""
    bowtie = [[88.2, 23.0], [88.6, 23.3], [88.6, 23.0], [88.2, 23.3]]
    response = client.post("/api/v1/series", json={"aoi": _polygon(bowtie)})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_aoi"
    assert body["field"] == "aoi.geometry.coordinates[0]"


def test_a_polygon_with_too_few_points_is_refused(client: TestClient):
    response = client.post("/api/v1/series", json={"aoi": _polygon([[88.2, 23.0], [88.6, 23.3]])})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_aoi"


def test_a_point_geometry_is_refused(client: TestClient):
    """Only a polygon is an area; a point is not."""
    response = client.post(
        "/api/v1/series",
        json={"aoi": {"type": "geojson", "geometry": {"type": "Point", "coordinates": [90, 23]}}},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_aoi"
    assert body["field"] == "aoi.geometry.type"


def test_a_geojson_area_without_geometry_is_refused(client: TestClient):
    response = client.post("/api/v1/series", json={"aoi": {"type": "geojson"}})
    assert response.status_code == 422
    assert response.json()["field"] == "aoi.geometry"


def test_a_polygon_with_a_hole_is_refused(client: TestClient):
    """The grid cannot honour a hole, so it is refused rather than ignored."""
    coordinates = [
        SQUARE,
        [[88.3, 23.1], [88.4, 23.1], [88.4, 23.2], [88.3, 23.2]],
    ]
    response = client.post("/api/v1/series", json={"aoi": _polygon(coordinates)})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_aoi"


def test_an_unclosed_ring_is_accepted(client: TestClient):
    """A shape drawn by clicking points is not closed, and needs no closing click."""
    open_ring = [[88.2, 23.0], [88.6, 23.0], [88.6, 23.3], [88.2, 23.3]]
    response = client.post("/api/v1/series", json={"aoi": _polygon(open_ring)})
    assert response.status_code == 200, response.text


def test_the_polygon_also_travels_in_a_query_parameter(client: TestClient):
    """A drawn shape fits in a query string, so the frontend can use GET.

    This is the path the web app takes: it asks for every payload with the
    same GET it uses for the presets.
    """
    response = client.get(
        "/api/v1/series", params={"polygon": json.dumps(TRIANGLE)}
    )
    assert response.status_code == 200, response.text
    _assert_matches("series", response.json())
    assert response.json()["meta"]["region"]["polygon"][0] == [88.2, 23.0]


def test_a_malformed_polygon_parameter_is_refused(client: TestClient):
    response = client.get("/api/v1/series", params={"polygon": "not json"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_aoi"
    assert body["field"] == "polygon"


def test_a_polygon_that_is_not_a_list_of_pairs_is_refused(client: TestClient):
    response = client.get("/api/v1/series", params={"polygon": "[[88.2],[23.0]]"})
    assert response.status_code == 422
    assert response.json()["field"] == "polygon"


def test_the_csv_export_honours_the_polygon(client: TestClient):
    response = client.post("/api/v1/export", json={"aoi": _polygon(TRIANGLE)})
    assert response.status_code == 200, response.text
    assert "attachment" in response.headers["content-disposition"]
    rows = response.text.strip().splitlines()
    assert rows[0].startswith("acq_date,")
    for row in rows[1:]:
        latitude = float(row.split(",")[2])
        longitude = float(row.split(",")[3])
        assert 88.2 <= longitude <= 88.6
        assert 23.0 <= latitude <= 23.3
