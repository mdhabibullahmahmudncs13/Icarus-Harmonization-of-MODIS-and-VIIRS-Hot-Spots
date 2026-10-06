"""Fetch and regrid MCD64A1 burned area onto the 0.25° grid E8 validates against.

The external validation (docs/TESTING.md §9 E8) needs burned area on a regular
latitude/longitude grid. The reachable product is MODIS **MCD64A1 v061**
(monthly, 500 m, HDF4, MODIS sinusoidal tiles); the 0.25° climate-modelling
grid product (MCD64CMQ) is not published to CMR, so it cannot be discovered by
``earthaccess``.

This module is network-touching and optional: importing it is cheap, and the
heavy dependencies (``earthaccess``, ``pyhdf``) are imported lazily so the
offline test suite never needs them. Credentials: an Earthdata Login bearer
token in ``EARTHDATA_TOKEN`` — read from the process environment, then from
``.env`` (the same reader ``src.acquire.firms`` uses).

Nothing here is evidence until :func:`src.validate.experiments` correlates it;
a fetch failure must never masquerade as a result.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.acquire import safe
from src.acquire.firms import read_dotenv

#: Product the pipeline fetches. MCD64CMQ is not in CMR; MCD64A1 v061 is.
SHORT_NAME = "MCD64A1"

#: Environment variable holding the Earthdata Login bearer token.
TOKEN_ENV = "EARTHDATA_TOKEN"

#: The burned-area layer and the land/water QA layer in each granule.
BURN_SDS = "Burn Date"
QA_SDS = "QA"

#: MODIS sinusoidal sphere radius (metres), from the product's grid definition.
SPHERE_RADIUS_M = 6371007.181

#: Target grid resolution for the comparison, in degrees.
DEFAULT_CELL_DEG = 0.25

#: ``Burn Date`` marks: a burn is an ordinal day in 1..366.
BURN_MIN, BURN_MAX = 1, 366

#: Directory names under ``cache/``.
RAW_DIR = "burned_area/raw"
DERIVED_NAME = "burned_area/derived.parquet"


def load_token(environ: Mapping[str, str] | None = None) -> str:
    """Return the Earthdata bearer token from the environment, then ``.env``."""
    environ = os.environ if environ is None else environ
    return (environ.get(TOKEN_ENV) or read_dotenv().get(TOKEN_ENV, "")).strip()


def require_token(environ: Mapping[str, str] | None = None) -> str:
    """Return the token or raise with the exact place to get one."""
    token = load_token(environ)
    if not token:
        raise RuntimeError(
            f"{TOKEN_ENV} is not set. Generate one at "
            "https://urs.earthdata.nasa.gov (Profile -> Generate Token) and put it "
            "in .env (see .env.example); tokens expire after ~60 days."
        )
    return token


def authenticate(environ: Mapping[str, str] | None = None) -> bool:
    """Log in to Earthdata with the token and return whether it succeeded.

    ``earthaccess`` reads ``os.environ``, so the token from ``.env`` is bridged
    onto the environment here — ``.env`` is not loaded by anything else.
    """
    token = require_token(environ)
    os.environ[TOKEN_ENV] = token
    import earthaccess

    return bool(earthaccess.login(strategy="environment").authenticated)


def search(
    bbox: tuple[float, float, float, float],
    start: date,
    end: date,
    *,
    count: int = 200,
) -> list[Any]:
    """Granules of :data:`SHORT_NAME` covering ``bbox`` over ``start..end``."""
    import earthaccess

    return list(
        earthaccess.search_data(
            short_name=SHORT_NAME,
            bounding_box=bbox,
            temporal=(start.isoformat(), end.isoformat()),
            count=count,
        )
    )


def download(
    bbox: tuple[float, float, float, float],
    start: date,
    end: date,
    *,
    dest: Path | None = None,
) -> list[Path]:
    """Download every granule covering ``bbox`` and return the local paths."""
    import earthaccess

    target = dest or (safe.CACHE_DIR / RAW_DIR)
    target.mkdir(parents=True, exist_ok=True)
    authenticate()
    files = earthaccess.download(search(bbox, start, end), str(target))
    return [Path(str(path)) for path in files]


# --------------------------------------------------------------------------
# Reading a granule
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Geometry:
    """The sinusoidal grid of one MODIS tile."""

    upper_left_x: float
    upper_left_y: float
    pixel_m: float
    rows: int
    cols: int
    tile: str
    year: int

    def pixel_centres(self) -> tuple[np.ndarray, np.ndarray]:
        """Sinusoidal ``(x, y)`` of every pixel centre, shape ``(rows, cols)``."""
        cols = self.upper_left_x + (np.arange(self.cols) + 0.5) * self.pixel_m
        rows = self.upper_left_y - (np.arange(self.rows) + 0.5) * self.pixel_m
        return np.meshgrid(cols, rows)


def _mtrs(metadata: str, key: str) -> tuple[float, float] | None:
    match = re.search(rf"{key}=\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\)", metadata)
    if not match:
        return None
    return (float(match.group(1)), float(match.group(2)))


def read_granule(path: Path) -> tuple[np.ndarray, np.ndarray, Geometry]:
    """Return ``(burn_date, qa, geometry)`` for one granule.

    ``burn_date`` is the ordinal day of burn (0 unburned, -1 fill, -2 water);
    ``qa`` carries the land/water bit the aggregation uses.
    """
    from pyhdf.SD import SD, SDC

    handle = SD(str(path), SDC.READ)
    burn = np.asarray(handle.select(BURN_SDS)[:, :], dtype="int32")
    qa = np.asarray(handle.select(QA_SDS)[:, :], dtype="int32")
    attributes = handle.attributes()
    metadata = str(attributes.get("StructMetadata.0", ""))
    ul = _mtrs(metadata, "UpperLeftPointMtrs")
    lr = _mtrs(metadata, "LowerRightMtrs")
    rows, cols = burn.shape
    if ul is None or lr is None:
        raise ValueError(f"{path.name}: StructMetadata.0 has no grid corners")
    pixel = abs(ul[0] - lr[0]) / cols
    texture = str(attributes.get("tile", ""))
    match = re.match(r"h(\d{2})v(\d{2})", texture)
    tile = match.group(0) if match else texture
    return (
        burn,
        qa,
        Geometry(
            upper_left_x=ul[0],
            upper_left_y=ul[1],
            pixel_m=pixel,
            rows=rows,
            cols=cols,
            tile=tile,
            year=int(attributes.get("year", 0) or 0),
        ),
    )


def to_lat_lon(geometry: Geometry) -> tuple[np.ndarray, np.ndarray]:
    """Invert the MODIS sinusoidal projection to ``(lat, lon)`` in degrees.

    ``y = R * phi`` and ``x = R * (lambda) * cos(phi)`` about a 0° central
    meridian, so ``phi = y / R`` and ``lambda = x / (R * cos(phi))``.
    """
    x, y = geometry.pixel_centres()
    phi = y / SPHERE_RADIUS_M
    lam = x / (SPHERE_RADIUS_M * np.cos(phi))
    return np.degrees(phi), np.degrees(lam)


# --------------------------------------------------------------------------
# Aggregating to the comparison grid
# --------------------------------------------------------------------------


def aggregate_to_grid(
    paths: Sequence[Path],
    *,
    cell_deg: float = DEFAULT_CELL_DEG,
) -> pd.DataFrame:
    """Burned-area fraction per ``(year, month, 0.25° cell)``.

    A cell's burned fraction is burned pixels over *land* pixels, so a cell that
    is mostly water is not diluted by the sea. Cells with no land are dropped.
    """
    lat_bins = round(180.0 / cell_deg)
    lon_bins = round(360.0 / cell_deg)
    records: list[dict[str, Any]] = []

    for path in paths:
        burn, qa, geometry = read_granule(path)
        name = path.name
        # MCD64A1.A2019001.h26v06.061.* -> year 2019, month 01
        match = re.match(r"MCD64A1\.A(\d{4})(\d{3})\.", name)
        if not match:
            raise ValueError(f"{name}: cannot read the year/date from the name")
        year, doy = int(match.group(1)), int(match.group(2))
        month = (date(year, 1, 1) + pd.Timedelta(days=doy - 1)).month

        latitude, longitude = to_lat_lon(geometry)
        lat_index = np.floor((latitude + 90.0) / cell_deg).astype("int64")
        lon_index = np.floor((longitude + 180.0) / cell_deg).astype("int64")
        flat = lat_index * lon_bins + lon_index

        land = (qa & 1) == 1
        burned = (burn >= BURN_MIN) & (burn <= BURN_MAX)
        size = lat_bins * lon_bins
        land_count = np.bincount(flat[land].ravel(), minlength=size)
        burned_count = np.bincount(flat[burned].ravel(), minlength=size)

        occupied = np.flatnonzero(land_count)
        for key in occupied:
            rows_index, cols_index = divmod(int(key), lon_bins)
            records.append(
                {
                    "year": year,
                    "month": month,
                    "lat": round(rows_index * cell_deg - 90.0 + cell_deg / 2.0, 6),
                    "lon": round(cols_index * cell_deg - 180.0 + cell_deg / 2.0, 6),
                    "land_pixels": int(land_count[key]),
                    "burned_pixels": int(burned_count[key]),
                    "burned_fraction": float(burned_count[key]) / float(land_count[key]),
                    "tile": geometry.tile,
                }
            )

    frame = pd.DataFrame.from_records(records)
    if frame.empty:
        return frame
    # Tiles can overlap at their edges; sum the counts per cell-month.
    grouped = (
        frame.groupby(["year", "month", "lat", "lon"], as_index=False)
        .agg(land_pixels=("land_pixels", "sum"), burned_pixels=("burned_pixels", "sum"))
        .sort_values(["year", "month", "lat", "lon"], kind="stable")
    )
    grouped["burned_fraction"] = grouped["burned_pixels"] / grouped["land_pixels"]
    return grouped.reset_index(drop=True)


def raw_paths() -> list[Path]:
    """Every downloaded granule currently in the cache, sorted."""
    return sorted((safe.CACHE_DIR / RAW_DIR).glob("*.hdf"))


def derive(paths: Sequence[Path] | None = None, *, cell_deg: float = DEFAULT_CELL_DEG) -> Path:
    """Aggregate the cached granules and write the derived parquet."""
    selected = list(paths) if paths is not None else raw_paths()
    if not selected:
        raise FileNotFoundError(
            f"no MCD64A1 granules under {safe.CACHE_DIR / RAW_DIR}; run "
            "`python -m src.acquire.burned_area` first"
        )
    frame = aggregate_to_grid(selected, cell_deg=cell_deg)
    out = safe.CACHE_DIR / DERIVED_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out, index=False)
    return out


def load_derived() -> pd.DataFrame | None:
    """The derived burned-area grid, or ``None`` when it has not been built."""
    path = safe.CACHE_DIR / DERIVED_NAME
    if not path.exists():
        return None
    return pd.read_parquet(path)


#: The pilot region, matching the FIRMS default bbox in ``src/acquire/firms.py``.
PILOT_BBOX: tuple[float, float, float, float] = (88.0, 20.0, 93.0, 27.0)


def main(argv: Sequence[str] | None = None) -> int:
    """Download the granules for a window and build the 0.25° grid.

    The window is required: one year over the pilot box is ~36 granules and
    ~113 MB, so widening it is a deliberate choice rather than a default. Use
    ``--dry-run`` to see the granule count before fetching.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m src.acquire.burned_area", description=__doc__
    )
    parser.add_argument("--start", required=True, help="ISO date, e.g. 2019-01-01")
    parser.add_argument("--end", required=True, help="ISO date, e.g. 2019-12-31")
    parser.add_argument("--bbox", default=",".join(str(v) for v in PILOT_BBOX))
    parser.add_argument("--dry-run", action="store_true", help="list the granules, fetch nothing")
    args = parser.parse_args(argv)

    bbox = tuple(float(part) for part in args.bbox.split(","))  # type: ignore[assignment]
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    try:
        authenticate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    granules = search(bbox, start, end)  # type: ignore[arg-type]
    print(f"{SHORT_NAME}: {len(granules)} granule(s) for {start}..{end} over bbox {args.bbox}")
    if args.dry_run:
        return 0

    paths = download(bbox, start, end)  # type: ignore[arg-type]
    print(f"downloaded {len(paths)} granule(s) to {safe.CACHE_DIR / RAW_DIR}")
    out = derive(paths)
    frame = load_derived()
    print(f"wrote {out} ({len(frame) if frame is not None else 0} cell-months)")
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(main())


__all__: Sequence[str] = (
    "DEFAULT_CELL_DEG",
    "DERIVED_NAME",
    "PILOT_BBOX",
    "RAW_DIR",
    "SHORT_NAME",
    "TOKEN_ENV",
    "Geometry",
    "aggregate_to_grid",
    "authenticate",
    "derive",
    "download",
    "load_derived",
    "load_token",
    "main",
    "raw_paths",
    "read_granule",
    "require_token",
    "search",
    "to_lat_lon",
)
