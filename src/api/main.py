"""Icarus API — the seven contract endpoints, served offline-first.

Every route returns a payload built by :mod:`src.compute.export`, so the API
and the exported static files are the same shapes and both satisfy
``docs/contract.schema.json``. The API reads local parquet only (see
:mod:`src.api.dataset`); it never calls NASA, and ``OFFLINE=1`` makes it
serve the committed fixture.

Endpoints (all ``GET``, all carrying the shared ``meta`` block):

* ``/health``
* ``/api/meta``
* ``/api/series``
* ``/api/cells?start&end``
* ``/api/baseline``
* ``/api/anomaly?date&bbox``
* ``/api/validation``
* ``/api/methods``
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date as DateType
from typing import Annotated, Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.api.dataset import Dataset, NoDataError, get_dataset
from src.compute import export, harmonize

#: Origins that may call the API during development: the Vite dev server and
#: the preview server, both loopback-only. No wildcard, so an offline demo
#: never invites a third-party request.
ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
]

app = FastAPI(title="Icarus", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _dataset() -> Dataset:
    """The served dataset, or 503 when the cache and the fixture are absent."""
    try:
        return get_dataset()
    except NoDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _parse_bbox(raw: str) -> tuple[float, float, float, float]:
    """Parse ``west,south,east,north`` into a bbox, or raise 422."""
    parts = [piece.strip() for piece in raw.split(",")]
    if len(parts) != 4:
        raise HTTPException(
            status_code=422,
            detail="bbox must be four comma-separated degrees: west,south,east,north",
        )
    try:
        west, south, east, north = (float(piece) for piece in parts)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="bbox values must be numbers") from exc
    if not (west < east and south < north):
        raise HTTPException(status_code=422, detail="bbox must satisfy west<east and south<north")
    return west, south, east, north


def _within(frame: pd.DataFrame, bbox: tuple[float, float, float, float]) -> pd.DataFrame:
    """Detections inside ``bbox`` ``[west, south, east, north]``."""
    west, south, east, north = bbox
    return frame[
        (frame["longitude"] >= west)
        & (frame["longitude"] <= east)
        & (frame["latitude"] >= south)
        & (frame["latitude"] <= north)
    ]


def _continuous(series: pd.Series) -> pd.Series:
    """Reindex a daily series onto every day between its ends, filling 0."""
    if series.empty:
        return series
    index = pd.date_range(series.index.min(), series.index.max(), freq="D")
    index.name = "date"
    return series.reindex(index, fill_value=0)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/api/meta")
def meta() -> Mapping[str, Any]:
    """Region, parameters and sensor epochs."""
    dataset = _dataset()
    return export.build_meta_response(
        dataset.detections, source=dataset.source, generated_at=dataset.generated_at
    )


@app.get("/api/series")
def series() -> Mapping[str, Any]:
    """Daily raw and harmonized counts, one row per day."""
    dataset = _dataset()
    return export.build_series(
        dataset.detections, source=dataset.source, generated_at=dataset.generated_at
    )


@app.get("/api/cells")
def cells(
    start: Annotated[DateType | None, Query(description="ISO date, inclusive")] = None,
    end: Annotated[DateType | None, Query(description="ISO date, inclusive")] = None,
) -> Mapping[str, Any]:
    """Grid cells over a date window, with raw and harmonized counts."""
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="start must not be after end")
    dataset = _dataset()
    return export.build_cells(
        dataset.detections,
        start=start,
        end=end,
        source=dataset.source,
        generated_at=dataset.generated_at,
    )


@app.get("/api/baseline")
def baseline() -> Mapping[str, Any]:
    """Seasonal baseline: day-of-year percentiles of the harmonized series."""
    dataset = _dataset()
    return export.build_baseline(
        dataset.series, source=dataset.source, generated_at=dataset.generated_at
    )


@app.get("/api/anomaly")
def anomaly(
    date: Annotated[DateType, Query(description="ISO date to judge")],
    bbox: Annotated[str | None, Query(description="west,south,east,north")] = None,
) -> Mapping[str, Any]:
    """Rank one date against its day-of-year baseline."""
    dataset = _dataset()
    series = dataset.series
    if bbox is not None:
        frame = _within(dataset.detections, _parse_bbox(bbox))
        series = _continuous(harmonize.harmonized_series(frame))

    stamp = pd.Timestamp(date)
    if series.empty:
        raise HTTPException(status_code=404, detail="no detections in the requested area")
    low, high = series.index.min(), series.index.max()
    if stamp < low or stamp > high:
        raise HTTPException(
            status_code=404,
            detail=(
                f"{date.isoformat()} is outside the dataset range "
                f"{low.date().isoformat()}..{high.date().isoformat()}"
            ),
        )

    payload = export.build_anomaly(
        series, date_=stamp, source=dataset.source, generated_at=dataset.generated_at
    )
    if not (math.isfinite(payload["value"]) and math.isfinite(payload["percentile"])):
        # The contract carries real numbers only; never emit NaN.
        raise HTTPException(
            status_code=503,
            detail="the baseline window is too thin to rank this date",
        )
    return payload


@app.get("/api/validation")
def validation() -> Mapping[str, Any]:
    """Overlap-period agreement, raw against harmonized."""
    dataset = _dataset()
    try:
        return export.build_validation(
            dataset.detections, source=dataset.source, generated_at=dataset.generated_at
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/methods")
def methods() -> Mapping[str, Any]:
    """Method text, confidence mapping and dataset citations."""
    dataset = _dataset()
    return export.build_methods(source=dataset.source, generated_at=dataset.generated_at)


__all__ = ["ALLOWED_ORIGINS", "app"]
