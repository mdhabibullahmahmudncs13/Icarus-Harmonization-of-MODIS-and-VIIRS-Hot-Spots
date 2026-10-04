"""Deterministic synthetic detections, shared by the tests and the demo fixture.

This module is the single implementation of the fake MODIS/VIIRS detections
the project uses where real FIRMS data is not available. Two consumers:

* ``tests/synthetic.py`` re-exports it, so the compute tests and this module
  cannot drift apart.
* ``src/api``'s offline fixture is generated from it by ``python -m
  src.demo`` and committed at ``demo_fixtures/detections.parquet``.

Synthetic data is never evidence. ``meta.source`` reports ``"mock"`` or
``"fixture"`` and the UI shows the mock banner, so a number produced from
this data is never presented as a real observation.

The shape is an assumption for the fixture only: a latent set of fire
cell-days on a seasonal curve, a MODIS-like sensor that detects a fraction of
them once each, and a VIIRS-like sensor that detects more of them with
several detections per cell-day. That mirrors the real reason the raw series
steps up while the harmonized series does not, so tests and the demo exercise
the mechanism rather than a coincidence.

Coordinates are drawn as *grid cell centres* with a jitter far smaller than
half a cell, so a sensor pair reporting the same fire really does land in the
same cell. Jittering around an arbitrary point can straddle a cell edge and
quietly manufacture a disagreement the fixture is meant to exclude.

Deterministic (seeded) and offline. No LLM, no network.
"""

from __future__ import annotations

import argparse
import math
import random
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.compute.harmonize import degrees_per_lat, degrees_per_lon

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Where ``python -m src.demo`` writes the committed offline fixture.
DEFAULT_FIXTURE = REPO_ROOT / "demo_fixtures" / "detections.parquet"

#: Latticed distinct cells, indexed row-major. 144 cells is well above the
#: busiest day in the fixture, so harmonized counts are never clamped by a
#: shortage of cells (a capped series loses its correlation).
GRID_ROWS = 12
GRID_COLS = 12

#: Anchor the lattice on real cell indices so the coordinates are in a
#: plausible latitude band; only the spacing matters.
_ROW0 = 460
_COL0 = 1630

#: Half the jitter each sensor may add around a cell centre. 0.004 degrees is
#: ~0.44 km, far inside a 5.5 km cell (half-cell is ~0.0247 degrees).
JITTER = 0.004

#: Default span of the committed demo fixture: two full calendar years, so
#: the seasonal baseline has more than one year to draw on.
DEFAULT_DAYS = 731
DEFAULT_START = date(2019, 1, 1)


def cell_center(index: int) -> tuple[float, float]:
    """Centre of the ``index``-th grid cell."""
    k = index % (GRID_ROWS * GRID_COLS)
    row, col = divmod(k, GRID_COLS)
    dlat = degrees_per_lat()
    dlon = degrees_per_lon()
    return ((_ROW0 + row + 0.5) * dlat, (_COL0 + col + 0.5) * dlon)


def jitter(rng: random.Random, latitude: float, longitude: float) -> tuple[float, float]:
    """Displace a point but keep it inside its own cell."""
    return (latitude + rng.uniform(-JITTER, JITTER), longitude + rng.uniform(-JITTER, JITTER))


def synthetic_detections(
    *,
    days: int = 240,
    start: date = date(2015, 1, 1),
    seed: int = 7,
    modis_detection_rate: float = 0.75,
    viirs_detection_rate: float = 1.0,
    viirs_mean_detections_per_cell_day: float = 3.0,
    extra_viirs_only_rate: float = 0.2,
) -> pd.DataFrame:
    """Build one detection table containing both sensors.

    ``viirs_mean_detections_per_cell_day`` is the inflation factor the
    harmonization is supposed to remove: VIIRS reports several overlapping
    detections for the fire MODIS recorded once.

    ``confidence`` is numeric for MODIS rows and a letter for VIIRS rows, as
    in the real products.
    """
    rng = random.Random(seed)
    rows: list[dict[str, object]] = []
    pool = GRID_ROWS * GRID_COLS

    for offset in range(days):
        day = start + timedelta(days=offset)
        # Seasonal curve (dry-season peak) plus year-to-year noise.
        season = 0.5 + 0.5 * math.sin(2 * math.pi * (offset % 365) / 365.0)
        activity = 4.0 + 18.0 * season + rng.uniform(-2.0, 2.0)
        active_cells = max(1, round(activity))
        # Rotate which cells are burning so consecutive days are not the
        # same handful of cells.
        rotate = rng.randrange(pool)

        for cell_index in range(active_cells):
            latitude, longitude = cell_center(rotate + cell_index)

            if rng.random() < modis_detection_rate:
                jlat, jlon = jitter(rng, latitude, longitude)
                rows.append(
                    {
                        "latitude": jlat,
                        "longitude": jlon,
                        "acq_date": day.isoformat(),
                        "confidence": rng.randint(55, 95),
                        "instrument": "MODIS",
                    }
                )

            if rng.random() < viirs_detection_rate:
                count = max(
                    1, round(rng.expovariate(1.0 / viirs_mean_detections_per_cell_day))
                )
                for _ in range(count):
                    jlat, jlon = jitter(rng, latitude, longitude)
                    rows.append(
                        {
                            "latitude": jlat,
                            "longitude": jlon,
                            "acq_date": day.isoformat(),
                            "confidence": rng.choice(["n", "n", "h"]),
                            "instrument": "VIIRS",
                        }
                    )
            elif rng.random() < extra_viirs_only_rate:
                # A small fire VIIRS sees and MODIS missed.
                jlat, jlon = jitter(rng, latitude, longitude)
                rows.append(
                    {
                        "latitude": jlat,
                        "longitude": jlon,
                        "acq_date": day.isoformat(),
                        "confidence": "n",
                        "instrument": "VIIRS",
                    }
                )

    frame = pd.DataFrame(rows)
    return frame.sort_values(["acq_date", "instrument"], kind="stable").reset_index(drop=True)


def identical_cell_days(
    *,
    days: int = 60,
    start: date = date(2015, 1, 1),
    seed: int = 11,
    multiplier: int = 3,
) -> pd.DataFrame:
    """Both sensors see exactly the same cell-days; VIIRS reports ``multiplier`` each.

    The clean case for "harmonized counts match, raw counts do not": the
    collapse must make the two sensors identical after harmonization. Both
    sensors sample around the same cell centre with in-cell jitter, so the
    fixture cannot disagree for a reason other than the collapse itself.
    """
    rng = random.Random(seed)
    rows: list[dict[str, object]] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        active = rng.randint(1, 6)
        for cell_index in range(active):
            latitude, longitude = cell_center(cell_index)
            mlat, mlon = jitter(rng, latitude, longitude)
            rows.append(
                {
                    "latitude": mlat,
                    "longitude": mlon,
                    "acq_date": day.isoformat(),
                    "confidence": 80,
                    "instrument": "MODIS",
                }
            )
            for _ in range(multiplier):
                vlat, vlon = jitter(rng, latitude, longitude)
                rows.append(
                    {
                        "latitude": vlat,
                        "longitude": vlon,
                        "acq_date": day.isoformat(),
                        "confidence": "n",
                        "instrument": "VIIRS",
                    }
                )
    return pd.DataFrame(rows)


def demo_detections(
    *,
    days: int = DEFAULT_DAYS,
    start: date = DEFAULT_START,
    seed: int = 7,
    frp_seed: int = 1007,
) -> pd.DataFrame:
    """The committed offline fixture, in a parquet-safe shape.

    :func:`synthetic_detections` returns a mixed-type ``confidence`` column
    (numeric for MODIS, letters for VIIRS) which parquet cannot store in one
    column, so the values are written as text — the compute schema parses
    either form. A deterministic ``frp`` column is added so ``peak_frp`` in
    the cells payload is a real number rather than a constant zero.
    """
    frame = synthetic_detections(days=days, start=start, seed=seed).copy()
    frame["confidence"] = frame["confidence"].astype(str)
    rng = random.Random(frp_seed)
    frame["frp"] = [round(rng.uniform(0.5, 80.0), 2) for _ in range(len(frame))]
    return frame


def write_fixture(
    path: Path = DEFAULT_FIXTURE,
    *,
    days: int = DEFAULT_DAYS,
    start: date = DEFAULT_START,
    seed: int = 7,
) -> Path:
    """Write the demo detections to ``path`` as zstd parquet. Returns the path."""
    frame = demo_detections(days=days, start=start, seed=seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False, compression="zstd")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.demo",
        description="Write the deterministic offline detections fixture.",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--start", default=DEFAULT_START.isoformat())
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    path = write_fixture(
        args.out,
        days=args.days,
        start=date.fromisoformat(args.start),
        seed=args.seed,
    )
    print(f"wrote {path} ({path.stat().st_size} bytes)")
    return 0


__all__ = [
    "DEFAULT_DAYS",
    "DEFAULT_FIXTURE",
    "DEFAULT_START",
    "GRID_COLS",
    "GRID_ROWS",
    "JITTER",
    "cell_center",
    "demo_detections",
    "identical_cell_days",
    "jitter",
    "main",
    "synthetic_detections",
    "write_fixture",
]


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(main())
