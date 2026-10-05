"""S4/S5 — grid snapping, cell-day collapse, and aggregation to series/cells.

Extension over the spec's `cell_day` table: in addition to the combined `n_det`,
each cell-day carries `n_modis` and `n_viirs`. The spec stores only the combined
count, which cannot yield per-stream *detection* totals for the raw series; the
per-stream counts make the raw series derivable without a second pass over the
detections.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .schema import STREAM_BITS, Detection

K = 20  # cells per degree -> 0.05 deg, ~5.5 km at the pilot latitude
MODIS_MASK = STREAM_BITS["MOD_T"] | STREAM_BITS["MOD_A"]
VIIRS_MASK = STREAM_BITS["VIIRS_SNPP"] | STREAM_BITS["VIIRS_N20"] | STREAM_BITS["VIIRS_N21"]


def grid_snap(lon: float, lat: float, k: int = K) -> tuple[int, int]:
    """S4: floor semantics; boundary detections belong to the higher index."""
    return math.floor(lon * k), math.floor(lat * k)


def area_weight(lat: float) -> float:
    """Relative ground area of a cell at this latitude."""
    return math.cos(math.radians(lat))


@dataclass(frozen=True)
class CellDay:
    """S5: one stream-presence record for a cell on a UTC date."""

    cell_x: int
    cell_y: int
    date: str
    stream_mask: int
    n_det: int
    max_frp: float | None
    n_modis: int = 0
    n_viirs: int = 0


def _to_cell_day(det: Detection, k: int) -> CellDay:
    cx, cy = grid_snap(det.lon, det.lat, k)
    is_modis = bool(det.stream_bit & MODIS_MASK)
    return CellDay(
        cell_x=cx,
        cell_y=cy,
        date=det.acq_date,
        stream_mask=det.stream_bit,
        n_det=1,
        max_frp=det.frp,
        n_modis=1 if is_modis else 0,
        n_viirs=0 if is_modis else 1,
    )


def _merge(items: Iterable[CellDay]) -> list[CellDay]:
    groups: dict[tuple[int, int, str], list] = {}
    for cd in items:
        key = (cd.cell_x, cd.cell_y, cd.date)
        state = groups.setdefault(key, [0, 0, None, 0, 0])  # mask, n, frp, n_modis, n_viirs
        state[0] |= cd.stream_mask
        state[1] += cd.n_det
        if cd.max_frp is not None:
            state[2] = cd.max_frp if state[2] is None else max(state[2], cd.max_frp)
        state[3] += cd.n_modis
        state[4] += cd.n_viirs
    return [
        CellDay(x, y, d, s[0], s[1], s[2], s[3], s[4])
        for (x, y, d), s in sorted(groups.items())
    ]


def collapse_cell_days(dets: Iterable[Detection], k: int = K) -> list[CellDay]:
    """S5: collapse detections to one presence record per cell and day."""
    return _merge(_to_cell_day(d, k) for d in dets)


def merge_cell_days(cell_days: Iterable[CellDay]) -> list[CellDay]:
    """Normalize cell-days; idempotent (merge(merge(x)) == merge(x))."""
    return _merge(cell_days)


def to_series(cell_days: Iterable[CellDay]) -> list[dict]:
    """Daily raw (detections) and harmonized (distinct cell-days) series."""
    days: dict[str, dict] = {}
    for cd in cell_days:
        row = days.setdefault(
            cd.date,
            {
                "date": cd.date,
                "raw_modis": 0,
                "raw_viirs": 0,
                "raw_total": 0,
                "harm_modis": 0,
                "harm_viirs": 0,
                "harm_total": 0,
            },
        )
        has_modis = bool(cd.stream_mask & MODIS_MASK)
        has_viirs = bool(cd.stream_mask & VIIRS_MASK)
        if has_modis:
            row["raw_modis"] += cd.n_modis
            row["harm_modis"] += 1
        if has_viirs:
            row["raw_viirs"] += cd.n_viirs
            row["harm_viirs"] += 1
        if has_modis or has_viirs:
            row["harm_total"] += 1
        row["raw_total"] = row["raw_modis"] + row["raw_viirs"]
    return [days[d] for d in sorted(days)]


def to_cells(cell_days: Iterable[CellDay], k: int = K) -> list[dict]:
    """Per-cell totals over the window: raw detections, harmonized cell-days."""
    cells: dict[tuple[int, int], dict] = {}
    for cd in cell_days:
        key = (cd.cell_x, cd.cell_y)
        entry = cells.setdefault(
            key,
            {
                "cell_id": f"{cd.cell_x}_{cd.cell_y}",
                "bounds": [cd.cell_x / k, cd.cell_y / k, (cd.cell_x + 1) / k, (cd.cell_y + 1) / k],
                "raw": 0,
                "harmonized": 0,
                "peak_frp": None,
            },
        )
        entry["raw"] += cd.n_det
        entry["harmonized"] += 1
        if cd.max_frp is not None:
            entry["peak_frp"] = (
                cd.max_frp if entry["peak_frp"] is None else max(entry["peak_frp"], cd.max_frp)
            )
    return [cells[k_] for k_ in sorted(cells)]
