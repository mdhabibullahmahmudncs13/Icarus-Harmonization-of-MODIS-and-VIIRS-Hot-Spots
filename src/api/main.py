"""Icarus API — the seven contract endpoints, served offline-first.

Every route returns a payload built by :mod:`src.compute.export`, so the API and
the exported static files are the same shapes and both satisfy
``docs/contract.schema.json``. The API reads local parquet only (see
:mod:`src.api.dataset`); it never calls NASA, and ``OFFLINE=1`` makes it
serve the committed fixture.

Endpoints, all carrying the shared ``meta`` block. Every payload is served
under the versioned ``/api/v1`` prefix the contract specifies (and the
frontend's ``VITE_DATA=api`` mode calls); the unversioned path is kept as an
alias so earlier callers keep working.

* ``/health``
* ``/api/v1/meta`` (alias ``/api/meta``)
* ``/api/v1/series`` (alias ``/api/series``)
* ``/api/v1/cells?start&end`` (alias ``/api/cells``)
* ``/api/v1/baseline`` (alias ``/api/baseline``)
* ``/api/v1/anomalies?date&bbox&aoi`` (alias ``/api/anomaly?date``)
* ``/api/v1/critical-period?aoi``
* ``/api/v1/validation`` (alias ``/api/validation``)
* ``/api/v1/methods`` (alias ``/api/methods``)
* ``/api/v1/aoi``

Per ``docs/ApplicationFlow.md`` the analysis endpoints also accept ``POST``:
``aoi``, ``date`` and ``bbox`` in the body override the query parameters, and
``metric``/``view`` are validated (``metric=density`` is served by the series
payload and refused elsewhere). The ``aoi`` field takes a preset id or the AOI
object ``docs/TRD.md`` §6.1 defines; custom geometry is expressed with
``bbox``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date as DateType
from typing import Annotated, Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

#: The AOI ids the picker offers, from the one shared preset list.
PRESET_IDS: frozenset[str] = frozenset(
    str(preset["id"]) for preset in export.load_presets()
)

#: Contract error codes by status, for the errors that are not field-specific.
_CODE_BY_STATUS: dict[int, str] = {
    404: "not_found",
    409: "conflict",
    422: "invalid_request",
    503: "unavailable",
}


# --------------------------------------------------------------------------
# Errors: every failure is ``{code, message, field}`` (docs/TRD.md §9)
# --------------------------------------------------------------------------


def fail(status_code: int, code: str, message: str, field: str | None = None) -> None:
    """Raise an error in the contract's shape."""
    raise HTTPException(
        status_code=status_code, detail={"code": code, "message": message, "field": field}
    )


@app.exception_handler(HTTPException)
async def _http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and {"code", "message", "field"} <= set(detail):
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": _CODE_BY_STATUS.get(exc.status_code, "error"),
            "message": str(detail),
            "field": None,
        },
    )


@app.exception_handler(RequestValidationError)
async def _invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """A missing or malformed parameter names the field it came from."""
    errors = exc.errors()
    first = errors[0] if errors else {}
    location = [str(part) for part in first.get("loc", ()) if part not in ("body", "query", "path")]
    return JSONResponse(
        status_code=422,
        content={
            "code": "invalid_request",
            "message": str(first.get("msg", "invalid request")),
            "field": location[0] if location else None,
        },
    )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _dataset() -> Dataset:
    """The served dataset, or 503 when the cache and the fixture are absent."""
    try:
        return get_dataset()
    except NoDataError as exc:
        fail(503, "unavailable", str(exc))


def _parse_bbox(raw: str) -> tuple[float, float, float, float]:
    """Parse ``west,south,east,north`` into a bbox, or raise 422."""
    parts = [piece.strip() for piece in raw.split(",")]
    if len(parts) != 4:
        fail(422, "invalid_bbox", "bbox must be four comma-separated degrees: west,south,east,north", "bbox")
    try:
        west, south, east, north = (float(piece) for piece in parts)
    except ValueError:
        fail(422, "invalid_bbox", "bbox values must be numbers", "bbox")
    if not (west < east and south < north):
        fail(422, "invalid_bbox", "bbox must satisfy west<east and south<north", "bbox")
    return west, south, east, north


class AoiBody(BaseModel):
    """The AOI object ``docs/TRD.md`` §6.1 defines for request bodies.

    ``{type: "preset", id}`` maps onto a preset id. Custom geometry is not a
    preset: it is expressed with the ``bbox`` field, so anything else is
    refused rather than silently falling back to the default area.
    """

    type: str
    id: str | None = None
    geometry: dict[str, Any] | None = None


class AnalysisRequest(BaseModel):
    """The optional JSON body ``docs/ApplicationFlow.md`` §4 describes.

    ``aoi`` (a preset id or the ``{type: "preset", id}`` object), ``date`` and
    ``bbox`` are honoured and take precedence over the query parameters.
    ``metric`` and ``view`` are validated so a caller cannot believe they
    changed anything: every payload carries both the raw and the harmonized
    view, and ``metric`` selects the series units.

    ``metric=density`` is served by ``/api/v1/series`` (the only payload with
    a ``metric`` field) and refused on the other endpoints, which would
    otherwise silently answer in ``cell_days``.
    """

    aoi: str | AoiBody | None = None
    date: DateType | None = None
    bbox: list[float] | None = None
    metric: str | None = None
    view: str | None = None


def _resolve(
    body: AnalysisRequest | None,
    *,
    aoi: str = "BGD",
    date: DateType | None = None,
    bbox: str | None = None,
    allow_density: bool = False,
) -> tuple[str, DateType | None, tuple[float, float, float, float] | None]:
    """Merge an optional request body over the query parameters.

    ``allow_density`` marks the endpoints whose payload actually carries a
    ``metric`` field; elsewhere ``metric=density`` is refused rather than
    ignored.
    """
    if body is not None:
        if body.aoi is not None:
            if isinstance(body.aoi, AoiBody):
                if body.aoi.type != "preset" or not body.aoi.id:
                    fail(
                        422,
                        "invalid_request",
                        "aoi must be a preset id or {type: 'preset', id}; "
                        "custom geometry is expressed with bbox",
                        "aoi",
                    )
                aoi = body.aoi.id
            else:
                aoi = body.aoi
        if body.date is not None:
            date = body.date
        if body.bbox is not None:
            bbox = ",".join(str(value) for value in body.bbox)
        if body.metric is not None:
            if body.metric not in ("cell_days", "density"):
                fail(422, "invalid_metric", "metric must be density or cell_days", "metric")
            if body.metric == "density" and not allow_density:
                fail(
                    422,
                    "unsupported_metric",
                    "metric=density is served only by /api/v1/series; "
                    "this payload has no metric field",
                    "metric",
                )
        if body.view is not None and body.view not in ("raw", "harmonized"):
            fail(422, "invalid_view", "view must be raw or harmonized", "view")

    parsed = _parse_bbox(bbox) if bbox is not None else None
    if parsed is None and aoi not in PRESET_IDS:
        fail(422, "unknown_aoi", f"unknown AOI {aoi!r}; known: {sorted(PRESET_IDS)}", "aoi")
    return aoi, date, parsed


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


@app.get("/meta")  # docs/TRD.md §6 and the runbook's smoke test call /meta
@app.get("/api/meta")
@app.get("/api/v1/meta")
def meta() -> Mapping[str, Any]:
    """Region, parameters and sensor epochs."""
    dataset = _dataset()
    return export.build_meta_response(
        dataset.detections, source=dataset.source, generated_at=dataset.generated_at
    )


@app.get("/api/series")
@app.get("/api/v1/series")
@app.post("/api/v1/series")
def series(body: AnalysisRequest | None = None) -> Mapping[str, Any]:
    """Daily raw and harmonized counts, one row per day.

    ``metric=density`` (the default the startup flow in
    ``docs/ApplicationFlow.md`` §3 asks for) serves the same counts divided by
    the region's grid-cell count; anything else is ``cell_days``.
    """
    _resolve(body, allow_density=True)
    metric = body.metric if body is not None and body.metric is not None else "cell_days"
    dataset = _dataset()
    return export.build_series(
        dataset.detections,
        metric=metric,
        source=dataset.source,
        generated_at=dataset.generated_at,
    )


@app.get("/api/cells")
@app.get("/api/v1/cells")
@app.post("/api/v1/cells")
def cells(
    start: Annotated[DateType | None, Query(description="ISO date, inclusive")] = None,
    end: Annotated[DateType | None, Query(description="ISO date, inclusive")] = None,
    body: AnalysisRequest | None = None,
) -> Mapping[str, Any]:
    """Grid cells over a date window, with raw and harmonized counts."""
    _resolve(body)
    if start is not None and end is not None and start > end:
        fail(422, "invalid_window", "start must not be after end", "start")
    dataset = _dataset()
    return export.build_cells(
        dataset.detections,
        start=start,
        end=end,
        source=dataset.source,
        generated_at=dataset.generated_at,
    )


@app.get("/api/baseline")
@app.get("/api/v1/baseline")
@app.post("/api/v1/baseline")
def baseline(body: AnalysisRequest | None = None) -> Mapping[str, Any]:
    """Seasonal baseline: day-of-year percentiles of the harmonized series."""
    _resolve(body)
    dataset = _dataset()
    return export.build_baseline(
        dataset.series, source=dataset.source, generated_at=dataset.generated_at
    )


def _anomaly_payload(
    dataset: Dataset,
    *,
    date: DateType | None,
    area: tuple[float, float, float, float] | None,
    aoi: str,
) -> Mapping[str, Any]:
    """Rank one date (or the last day in the data) against its season."""
    series = dataset.series
    if area is not None:
        series = _continuous(harmonize.harmonized_series(_within(dataset.detections, area)))
        aoi = ",".join(str(v) for v in area)

    if series.empty:
        fail(404, "not_found", "no detections in the requested area")
    stamp = pd.Timestamp(date) if date is not None else series.index.max()
    low, high = series.index.min(), series.index.max()
    if stamp < low or stamp > high:
        fail(
            404,
            "not_found",
            f"{stamp.date().isoformat()} is outside the dataset range "
            f"{low.date().isoformat()}..{high.date().isoformat()}",
            "date",
        )
    return export.build_anomaly(
        series,
        date_=stamp,
        aoi=aoi,
        source=dataset.source,
        generated_at=dataset.generated_at,
    )


@app.get("/api/anomaly")
def anomaly(
    date: Annotated[DateType, Query(description="ISO date to judge")],
    bbox: Annotated[str | None, Query(description="west,south,east,north")] = None,
    aoi: Annotated[str, Query(description="preset id the request is for")] = "BGD",
    body: AnalysisRequest | None = None,
) -> Mapping[str, Any]:
    """Rank one date against its day-of-year baseline."""
    resolved_aoi, resolved_date, area = _resolve(body, aoi=aoi, date=date, bbox=bbox)
    return _anomaly_payload(
        _dataset(), date=resolved_date, area=area, aoi=resolved_aoi
    )


@app.get("/api/v1/anomalies")
@app.post("/api/v1/anomalies")
def anomalies(
    date: Annotated[
        DateType | None, Query(description="ISO date to judge; defaults to the last day")
    ] = None,
    bbox: Annotated[str | None, Query(description="west,south,east,north")] = None,
    aoi: Annotated[str, Query(description="preset id the request is for")] = "BGD",
    body: AnalysisRequest | None = None,
) -> Mapping[str, Any]:
    """The frontend's anomalies view: the requested date, or the latest day."""
    resolved_aoi, resolved_date, area = _resolve(body, aoi=aoi, date=date, bbox=bbox)
    return _anomaly_payload(
        _dataset(), date=resolved_date, area=area, aoi=resolved_aoi
    )


@app.get("/api/critical-period")
@app.get("/api/v1/critical-period")
@app.post("/api/v1/critical-period")
def critical_period(
    aoi: Annotated[str, Query(description="preset id the request is for")] = "BGD",
    body: AnalysisRequest | None = None,
) -> Mapping[str, Any]:
    """Onset, peak, end and window mass of the burning season."""
    resolved_aoi, _, _ = _resolve(body, aoi=aoi)
    dataset = _dataset()
    return export.build_critical_period(
        dataset.series,
        aoi=resolved_aoi,
        source=dataset.source,
        generated_at=dataset.generated_at,
    )


@app.get("/api/aoi")
@app.get("/api/v1/aoi")
def aoi() -> Mapping[str, Any]:
    """The preset AOIs the picker offers."""
    dataset = _dataset()
    return export.build_aoi(
        source=dataset.source,
        generated_at=dataset.generated_at,
        date_range=export.detections_date_range(dataset.detections),
    )


@app.get("/api/validation")
@app.get("/api/v1/validation")
@app.post("/api/v1/validation")
def validation(body: AnalysisRequest | None = None) -> Mapping[str, Any]:
    """Overlap-period agreement, raw against harmonized."""
    _resolve(body)
    dataset = _dataset()
    try:
        return export.build_validation(
            dataset.detections, source=dataset.source, generated_at=dataset.generated_at
        )
    except ValueError as exc:
        fail(409, "conflict", str(exc))


@app.get("/api/methods")
@app.get("/api/v1/methods")
@app.post("/api/v1/methods")
def methods() -> Mapping[str, Any]:
    """Method text, confidence mapping and dataset citations."""
    dataset = _dataset()
    # The dataset's own date range, so one request yields one params_hash
    # across all nine payloads and two payloads can be matched against each
    # other (docs/ApplicationFlow.md: same inputs + same hash => same output).
    return export.build_methods(
        source=dataset.source,
        generated_at=dataset.generated_at,
        date_range=export.detections_date_range(dataset.detections),
    )


__all__ = ["ALLOWED_ORIGINS", "PRESET_IDS", "AnalysisRequest", "app", "fail"]
