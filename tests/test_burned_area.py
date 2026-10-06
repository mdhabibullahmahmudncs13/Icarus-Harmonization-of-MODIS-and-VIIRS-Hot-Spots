"""Burned-area regridding (``src.acquire.burned_area``) — math and credentials.

The projection and grid arithmetic are pure functions, so they are tested
directly against the published MODIS sinusoidal tile geometry (h26v06, whose
corners the granule's ``StructMetadata.0`` reports). No network, no granules,
and the developer's real token is never read or echoed.
"""

from __future__ import annotations

import pytest

from src.acquire import burned_area as ba

# h26v06, as reported by the granule's StructMetadata.0 (metres).
UL_X, UL_Y = 8895604.157347, 3335851.558997
LR_X, LR_Y = 10007554.677014, 2223901.039330
ROWS = COLS = 2400


@pytest.fixture
def geometry() -> ba.Geometry:
    """The geometry of tile h26v06, derived the way the reader derives it."""
    return ba.Geometry(
        upper_left_x=UL_X,
        upper_left_y=UL_Y,
        pixel_m=abs(UL_X - LR_X) / COLS,
        rows=ROWS,
        cols=COLS,
        tile="h26v06",
        year=2019,
    )


def test_pixel_size_is_the_modis_sinusoidal_grid(geometry):
    # One MODIS sinusoidal tile is 10 degrees of arc; 2400 columns of 500 m.
    assert geometry.pixel_m == pytest.approx(463.3127, abs=1e-3)


def test_tile_corners_match_the_published_geometry(geometry):
    latitude, longitude = ba.to_lat_lon(geometry)
    # Vertical edges are exact: the projection's y is R * phi.
    assert latitude[0, 0] == pytest.approx(30.0, abs=0.01)
    assert latitude[-1, -1] == pytest.approx(20.0, abs=0.01)
    # Longitude converges towards the pole, so the west edge is widest at 20N.
    assert longitude[-1, 0] == pytest.approx(85.14, abs=0.05)
    assert longitude[-1, -1] == pytest.approx(95.78, abs=0.05)
    assert longitude[0, 0] == pytest.approx(92.38, abs=0.05)
    assert longitude[0, -1] == pytest.approx(103.92, abs=0.05)


def test_projection_is_invertible(geometry):
    """Round-trip a pixel through the forward and inverse projection."""
    latitude, longitude = ba.to_lat_lon(geometry)
    row, col = 1200, 1200
    phi = float(latitude[row, col]) * 3.141592653589793 / 180.0
    lam = float(longitude[row, col]) * 3.141592653589793 / 180.0
    x = ba.SPHERE_RADIUS_M * lam * __import__("math").cos(phi)
    y = ba.SPHERE_RADIUS_M * phi
    expected_x = UL_X + (col + 0.5) * geometry.pixel_m
    expected_y = UL_Y - (row + 0.5) * geometry.pixel_m
    assert x == pytest.approx(expected_x, rel=1e-9)
    assert y == pytest.approx(expected_y, rel=1e-9)


def test_load_token_prefers_the_environment_then_dotenv(monkeypatch):
    monkeypatch.setattr(ba, "read_dotenv", lambda *a, **k: {ba.TOKEN_ENV: "from-dotenv"})
    assert ba.load_token({ba.TOKEN_ENV: "from-env"}) == "from-env"
    assert ba.load_token({}) == "from-dotenv"


def test_require_token_explains_where_to_get_one(monkeypatch):
    monkeypatch.setattr(ba, "read_dotenv", lambda *a, **k: {})
    with pytest.raises(RuntimeError, match="EARTHDATA_TOKEN"):
        ba.require_token({})


def test_mcd64cmq_is_not_the_product_fetched():
    # The 0.25 deg CMG product is not in CMR; the module must fetch MCD64A1.
    assert ba.SHORT_NAME == "MCD64A1"
