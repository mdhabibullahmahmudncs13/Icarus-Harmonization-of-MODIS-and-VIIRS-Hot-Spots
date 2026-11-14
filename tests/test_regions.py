"""The region registry: official FIRMS coverage, one source, valid combinations.

The expected table below is copied from NASA FIRMS' Regional Coordinates page
(https://firms.modaps.eosdis.nasa.gov/active_fire/coordinates.html). It is
deliberately a second copy: if someone edits a bbox in the config to something
plausible-looking, this test fails and points back at the authority.
"""

from __future__ import annotations

import json

import pytest

from src import regions
from src.acquire import firms

#: id -> (official label, west, south, east, north), in FIRMS page order.
FIRMS_REGIONS = {
    "WORLD": ("World", -180.0, -90.0, 180.0, 90.0),
    "CANADA": ("Canada", -150.0, 40.0, -49.0, 79.0),
    "ALASKA": ("Alaska", -180.0, 50.0, -139.0, 72.0),
    "USA_CONUS_HAWAII": (
        "USA (Conterminous) and Hawaii",
        -160.5,
        17.5,
        -63.8,
        50.0,
    ),
    "CENTRAL_AMERICA": ("Central America", -119.5, 7.0, -58.5, 33.5),
    "SOUTH_AMERICA": ("South America", -112.0, -60.0, -26.0, 13.0),
    "EUROPE": ("Europe", -26.0, 34.0, 35.0, 82.0),
    "NORTH_CENTRAL_AFRICA": ("North and Central Africa", -27.0, -10.0, 52.0, 37.5),
    "SOUTHERN_AFRICA": ("Southern Africa", 10.0, -36.0, 58.5, -4.0),
    "RUSSIA_ASIA": ("Russia and Asia", 26.0, 9.0, 180.0, 83.5),
    "SOUTH_ASIA": ("South Asia", 54.0, 5.5, 102.0, 40.0),
    "SOUTHEAST_ASIA": ("South East Asia", 88.0, -12.0, 163.0, 31.0),
    "AUSTRALIA_NZ": ("Australia and New Zealand", 110.0, -55.0, 180.0, -10.0),
}


def test_every_firms_region_is_present_with_its_official_bbox():
    by_id = regions.region_map()
    for region_id, (label, west, south, east, north) in FIRMS_REGIONS.items():
        assert region_id in by_id, f"missing FIRMS region {region_id}"
        region = by_id[region_id]
        assert region.label == label
        assert region.bbox == (west, south, east, north)
        assert region.kind == "firms"


def test_the_global_option_covers_the_whole_globe():
    global_region = regions.get_region("WORLD")
    assert global_region.bbox == (-180.0, -90.0, 180.0, 90.0)


def test_every_region_supports_modis_and_all_three_viirs_satellites():
    """A region's sensor list is what the data layer is allowed to request."""
    for region in regions.all_regions():
        missing = set(firms.PRODUCTS) - set(region.sensors)
        assert not missing, f"{region.id} cannot be queried with {sorted(missing)}"
        assert "MODIS_SP" in region.sensors
        for sensor in ("VIIRS_SNPP_SP", "VIIRS_NOAA20_SP", "VIIRS_NOAA21_NRT"):
            assert sensor in region.sensors


def test_an_unknown_region_is_refused_with_the_known_ids():
    with pytest.raises(KeyError) as excinfo:
        regions.get_region("ATLANTIS")
    assert "ATLANTIS" in str(excinfo.value)
    assert "WORLD" in str(excinfo.value)


def test_a_region_sensor_combination_that_does_not_exist_is_refused():
    # LANDSAT is a real FIRMS product, but not one this project downloads, so
    # no region may claim it and the combination is refused before a request.
    with pytest.raises(ValueError) as excinfo:
        regions.require_supported("EUROPE", "LANDSAT_NRT")
    assert "LANDSAT_NRT" in str(excinfo.value)
    assert regions.require_supported("EUROPE", "MODIS_SP").id == "EUROPE"


def test_the_registry_rejects_a_region_with_an_unknown_sensor(tmp_path):
    path = tmp_path / "regions.json"
    path.write_text(
        json.dumps(
            {
                "regions": [
                    {
                        "id": "BAD",
                        "label": "Bad",
                        "bbox": [0, 0, 1, 1],
                        "sensors": ["LANDSAT_NRT"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown sensor"):
        regions.load_regions(path)


def test_the_registry_rejects_a_reversed_bbox(tmp_path):
    path = tmp_path / "regions.json"
    path.write_text(
        json.dumps(
            {
                "regions": [
                    {
                        "id": "BAD",
                        "label": "Bad",
                        "bbox": [10, 0, 5, 1],
                        "sensors": ["MODIS_SP"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="west<east"):
        regions.load_regions(path)


def test_the_acquisition_cli_refuses_an_unknown_region(capsys):
    assert firms.main(["--region", "ATLANTIS", "--products", "MODIS_SP"]) == 2
    assert "unknown region" in capsys.readouterr().err


def test_the_acquisition_cli_checks_the_region_supports_each_product(capsys, monkeypatch):
    monkeypatch.setitem(firms.PRODUCTS, "TEST_SENSOR", firms.PRODUCTS["MODIS_SP"])
    try:
        assert firms.main(["--region", "EUROPE", "--products", "TEST_SENSOR"]) == 2
        assert "not available for sensor" in capsys.readouterr().err
    finally:
        monkeypatch.delitem(firms.PRODUCTS, "TEST_SENSOR", raising=False)


def test_download_resolves_the_region_bbox_and_sensor(monkeypatch):
    """The downloader reads its area from the registry, not a second constant."""
    calls: list[tuple] = []

    def fake_chunk(product, chunk, bbox, map_key="", **kwargs):
        calls.append((product.source, bbox))
        return firms.ChunkResult(chunk, "missing")

    monkeypatch.setattr(firms, "download_chunk", fake_chunk)
    report = firms.download_product(
        "MODIS_SP",
        region="SOUTH_ASIA",
        start=firms.DEFAULT_START,
        end=firms.DEFAULT_START,
        merge=False,
        offline=True,
    )
    assert calls
    assert calls[0] == ("MODIS_SP", regions.bbox_for("SOUTH_ASIA"))
    assert report.window is not None
