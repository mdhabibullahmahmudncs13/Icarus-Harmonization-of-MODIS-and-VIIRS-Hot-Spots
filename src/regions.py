"""The region registry: every selectable area, in one place.

``config/regions.json`` is the single source of truth. The API builds its
``/api/v1/aoi`` payload from :func:`preset_entries`, the acquisition CLI
resolves ``--region`` through :func:`get_region`, and :mod:`tools.gen_mock`
writes the same list to the offline mock, so the picker, the API and the data
layer cannot disagree about a region or its bounding box.

The FIRMS entries and their boxes come from the official Regional Coordinates
table (https://firms.modaps.eosdis.nasa.gov/active_fire/coordinates.html);
the local entries are the project's pilot AOIs. Every entry also names the
FIRMS products it may be queried with, which is what
:func:`require_supported` enforces: a region/sensor pair that does not exist
is refused before a request is built.

No network, no numpy, no pandas: this module is import-safe for every layer.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REGIONS_PATH = REPO_ROOT / "config" / "regions.json"

#: Region the app opens on (the pilot AOI the committed fixture covers).
DEFAULT_REGION_ID = "BGD"

#: FIRMS source ids the project downloads. A region may only name a sensor
#: from this tuple, so a region's ``sensors`` list can never promise data the
#: acquisition layer does not know how to fetch.
KNOWN_SENSORS: tuple[str, ...] = (
    "MODIS_SP",
    "VIIRS_SNPP_SP",
    "VIIRS_NOAA20_SP",
    "VIIRS_NOAA21_NRT",
)

REGION_KINDS = frozenset({"firms", "local"})


@dataclass(frozen=True)
class Region:
    """One selectable area and the products it supports."""

    id: str
    label: str
    bbox: tuple[float, float, float, float]
    sensors: tuple[str, ...]
    search_terms: tuple[str, ...]
    kind: str

    @property
    def west(self) -> float:
        return self.bbox[0]

    @property
    def south(self) -> float:
        return self.bbox[1]

    @property
    def east(self) -> float:
        return self.bbox[2]

    @property
    def north(self) -> float:
        return self.bbox[3]


def _fail(index: int, message: str) -> ValueError:
    return ValueError(f"config/regions.json: region #{index}: {message}")


def _parse_region(index: int, raw: Any) -> Region:
    if not isinstance(raw, dict):
        raise _fail(index, "must be an object")
    region_id = raw.get("id")
    label = raw.get("label")
    if not isinstance(region_id, str) or not region_id.strip():
        raise _fail(index, "id must be a non-empty string")
    if not isinstance(label, str) or not label.strip():
        raise _fail(index, "label must be a non-empty string")

    bbox = raw.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise _fail(index, f"bbox must be four numbers, got {bbox!r}")
    try:
        west, south, east, north = (float(value) for value in bbox)
    except (TypeError, ValueError) as exc:
        raise _fail(index, f"bbox values must be numbers, got {bbox!r}") from exc
    if not (west < east and south < north):
        raise _fail(index, f"bbox needs west<east and south<north, got {bbox!r}")

    sensors = raw.get("sensors")
    if not isinstance(sensors, list) or not sensors:
        raise _fail(index, "sensors must be a non-empty list")
    unknown = [value for value in sensors if value not in KNOWN_SENSORS]
    if unknown:
        raise _fail(
            index,
            f"unknown sensor(s) {unknown}; known: {list(KNOWN_SENSORS)}",
        )

    terms = raw.get("search_terms", [])
    if not isinstance(terms, list) or any(not isinstance(value, str) for value in terms):
        raise _fail(index, "search_terms must be a list of strings")

    kind = raw.get("kind", "firms")
    if kind not in REGION_KINDS:
        raise _fail(index, f"kind must be one of {sorted(REGION_KINDS)}, got {kind!r}")

    return Region(
        id=region_id.strip(),
        label=label.strip(),
        bbox=(west, south, east, north),
        sensors=tuple(str(value) for value in sensors),
        search_terms=tuple(terms),
        kind=str(kind),
    )


def load_regions(path: Path | None = None) -> tuple[Region, ...]:
    """Read and validate the registry, preserving its file order."""
    source = path or REGIONS_PATH
    data = json.loads(source.read_text(encoding="utf-8"))
    raw_regions = data.get("regions")
    if not isinstance(raw_regions, list) or not raw_regions:
        raise ValueError(f"{source}: 'regions' must be a non-empty list")
    regions = tuple(_parse_region(index, raw) for index, raw in enumerate(raw_regions))
    ids = [region.id for region in regions]
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    if duplicates:
        raise ValueError(f"{source}: duplicate region id(s) {duplicates}")
    return regions


@lru_cache(maxsize=1)
def all_regions() -> tuple[Region, ...]:
    """The registry, loaded once per process."""
    return load_regions()


def region_map() -> dict[str, Region]:
    """Every region, keyed by id."""
    return {region.id: region for region in all_regions()}


def region_ids() -> frozenset[str]:
    """The ids the API and the picker accept."""
    return frozenset(region_map())


def get_region(region_id: str) -> Region:
    """The named region, or ``KeyError`` listing the ids that exist."""
    try:
        return region_map()[region_id]
    except KeyError as exc:
        raise KeyError(
            f"unknown region {region_id!r}; known: {sorted(region_map())}"
        ) from exc


def bbox_for(region_id: str) -> tuple[float, float, float, float]:
    """The region's bounding box as ``west, south, east, north``."""
    return get_region(region_id).bbox


def preset_entries() -> list[dict[str, Any]]:
    """The contract's ``presets`` rows: ``id``, ``name`` and ``bbox``."""
    return [
        {"id": region.id, "name": region.label, "bbox": list(region.bbox)}
        for region in all_regions()
    ]


def require_supported(region_id: str, sensor: str) -> Region:
    """Return the region, or raise when that region/sensor pair does not exist.

    The registry is the authority, not the caller: a product the region does
    not list (a sensor the area has no product for, or a typo) is refused here
    rather than sent to FIRMS, which would answer an empty CSV or an error.
    """
    region = get_region(region_id)
    if sensor not in region.sensors:
        raise ValueError(
            f"region {region.id!r} is not available for sensor {sensor!r}; "
            f"supported: {list(region.sensors)}"
        )
    return region


__all__: Iterable[str] = (
    "DEFAULT_REGION_ID",
    "KNOWN_SENSORS",
    "REGIONS_PATH",
    "REGION_KINDS",
    "Region",
    "all_regions",
    "bbox_for",
    "get_region",
    "load_regions",
    "preset_entries",
    "region_ids",
    "region_map",
    "require_supported",
)
