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
* ``/api/v1/export?start&end&aoi`` — the filtered hotspot records as CSV
* ``/api/v1/validation`` (alias ``/api/validation``)
* ``/api/v1/methods`` (alias ``/api/methods``)
* ``/api/v1/aoi``

Per ``docs/ARCHITECTURE.md`` §6 the analysis endpoints also accept ``POST``:
``aoi``, ``date`` and ``bbox`` in the body override the query parameters, and
``metric``/``view`` are validated (``metric=density`` is served by the series
payload and refused elsewhere). The ``aoi`` field takes a preset id or the AOI
object ``docs/TRD.md`` §6.1 defines: ``{type: "preset", id}`` for a preset,
``{type: "geojson", geometry}`` for a drawn polygon.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import date as DateType
from typing import Annotated, Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from src.api.dataset import Dataset, NoDataError, _continuous, get_dataset
from src.compute import export, geometry, harmonize, params

#: Origins that may call the API during development: the Vite dev server and
#: the preview server, both loopback-only. No wildcard, so an offline demo
#: never invites a third-party request. The dev port is 5174, which is what
#: ``web/vite.config.ts`` sets; the preview and Playwright server use 4173.
ALLOWED_ORIGINS = [
    "http://127.0.0.1:5174",
    "http://localhost:5174",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
]

#: The AOI presets, from the one shared list: id -> the area it names.
PRESET_BBOX: dict[str, tuple[float, float, float, float]] = {
    str(preset["id"]): tuple(float(v) for v in preset["bbox"])  # type: ignore[misc]
    for preset in export.load_presets()
}

#: The AOI ids the picker offers.
PRESET_IDS: frozenset[str] = frozenset(PRESET_BBOX)

#: The most grid cells one AOI request may cover, and the longest a request
#: may run. Both come from ``config/params.yaml`` (the ``api`` section), the
#: file the project documents as the source of every tunable value; the
#: constants are the fallback when the file cannot be read.
MAX_AOI_CELLS = int(params.param(params.PARAMS_PATH, "api", "max_aoi_cells", 100_000))
REQUEST_TIMEOUT_S = float(params.param(params.PARAMS_PATH, "api", "request_timeout_s", 30))

#: The query parameter a drawn polygon travels in: a JSON list of
#: ``[lon, lat]`` pairs. A shape has no place in a plain ``bbox``, and this
#: lets the frontend ask for one with the same GET it uses for everything
#: else.
PolygonParam = Annotated[
    str | None,
    Query(description="drawn area: a JSON list of [lon, lat] pairs"),
]


class TimeoutMiddleware:
    """Bound how long one request may take before the client is told so.

    The docs promise a 30 s per-request timeout, so the bound has to be
    enforced here rather than left to the caller. FastAPI has no built-in
    request timeout, and the routes are synchronous ``def`` functions that
    Starlette runs in a threadpool, so this waits for the response with
    ``asyncio.wait_for``: when the bound passes, the client gets a 503 in the
    contract's error shape instead of an open-ended wait.

    The worker thread is not killed — Python cannot interrupt it — so it
    finishes in the background and its result is discarded. For a read-only
    local API over an already-loaded dataset that is the safe trade: the
    client stops waiting, and no lock or shared state is left half-written.
    """

    def __init__(self, app: Any, timeout_s: float | None = None) -> None:
        self.app = app
        #: ``None`` means "read the module constant at request time", so the
        #: bound stays in one place and can be adjusted without rebuilding the
        #: middleware stack.
        self.timeout_s = timeout_s

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.timeout_s if self.timeout_s is not None else REQUEST_TIMEOUT_S
        try:
            await asyncio.wait_for(self.app(scope, receive, send), timeout=limit)
        except TimeoutError:
            response = JSONResponse(
                status_code=503,
                content={
                    "code": "timeout",
                    "message": f"the request took longer than {limit:g} s",
                    "field": None,
                },
            )
            await response(scope, receive, send)


app = FastAPI(title="Icarus", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Added last, so it runs first: the timeout bounds the whole request, the CORS
# headers the browser needs included.
app.add_middleware(TimeoutMiddleware)


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

    Two forms are honoured, the two the TRD lists:

    * ``{type: "preset", id}`` maps onto a preset id.
    * ``{type: "geojson", geometry}`` maps onto a drawn polygon.

    Anything else is refused rather than silently falling back to the default
    area.
    """

    type: str
    id: str | None = None
    geometry: dict[str, Any] | None = None


def _parse_ring(aoi: AoiBody) -> geometry.Ring:
    """The polygon an AOI object names, or a 422 saying why it cannot.

    The ring is the first (and only) ring of a GeoJSON polygon: a shape with
    a hole in it is not something the grid can honour, so a second ring is
    refused rather than quietly ignored.
    """
    if aoi.geometry is None:
        fail(422, "invalid_aoi", "aoi.geometry is required for a geojson area", "aoi.geometry")
    shape = aoi.geometry
    if shape.get("type") != "Polygon":
        fail(
            422,
            "invalid_aoi",
            f"aoi.geometry.type must be Polygon, got {shape.get('type')!r}",
            "aoi.geometry.type",
        )
    coordinates = shape.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        fail(
            422,
            "invalid_aoi",
            "aoi.geometry.coordinates must be a list of rings",
            "aoi.geometry.coordinates",
        )
    if len(coordinates) > 1:
        fail(
            422,
            "invalid_aoi",
            "a polygon with a hole in it is not supported",
            "aoi.geometry.coordinates",
        )
    positions: list[tuple[float, float]] = []
    for position in coordinates[0]:
        if (
            not isinstance(position, (list, tuple))
            or len(position) != 2
            or not all(isinstance(value, (int, float)) for value in position)
        ):
            fail(
                422,
                "invalid_aoi",
                "aoi.geometry.coordinates[0] must hold [longitude, latitude] pairs",
                "aoi.geometry.coordinates[0]",
            )
        positions.append((float(position[0]), float(position[1])))
    try:
        return geometry.validate_ring(positions)
    except ValueError as exc:
        fail(422, "invalid_aoi", str(exc), "aoi.geometry.coordinates[0]")


class AnalysisRequest(BaseModel):
    """The optional JSON body ``docs/ARCHITECTURE.md`` §6 describes.

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


def _parse_ring(aoi: AoiBody) -> geometry.Ring:
    """The polygon an AOI object names, or a 422 saying why it cannot.

    The ring is the first (and only) ring of a GeoJSON polygon: a shape with
    a hole in it is not something the grid can honour, so a second ring is
    refused rather than quietly ignored.
    """
    if aoi.geometry is None:
        fail(422, "invalid_aoi", "aoi.geometry is required for a geojson area", "aoi.geometry")
    shape = aoi.geometry
    if shape.get("type") != "Polygon":
        fail(
            422,
            "invalid_aoi",
            f"aoi.geometry.type must be Polygon, got {shape.get('type')!r}",
            "aoi.geometry.type",
        )
    coordinates = shape.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        fail(
            422,
            "invalid_aoi",
            "aoi.geometry.coordinates must be a list of rings",
            "aoi.geometry.coordinates",
        )
    if len(coordinates) > 1:
        fail(
            422,
            "invalid_aoi",
            "a polygon with a hole in it is not supported",
            "aoi.geometry.coordinates",
        )
    return _ring_from_positions(coordinates[0], "aoi.geometry.coordinates[0]")


def _ring_from_positions(raw: Any, field: str) -> geometry.Ring:
    """The ring a list of ``[lon, lat]`` pairs names, or a 422 saying why not."""
    if not isinstance(raw, list):
        fail(422, "invalid_aoi", f"{field} must be a list of positions", field)
    positions: list[tuple[float, float]] = []
    for position in raw:
        if (
            not isinstance(position, (list, tuple))
            or len(position) != 2
            or not all(isinstance(value, (int, float)) for value in position)
        ):
            fail(
                422,
                "invalid_aoi",
                f"{field} must hold [longitude, latitude] pairs",
                field,
            )
        positions.append((float(position[0]), float(position[1])))
    try:
        return geometry.validate_ring(positions)
    except ValueError as exc:
        fail(422, "invalid_aoi", str(exc), field)


def _parse_ring_param(raw: str) -> geometry.Ring:
    """The ring a ``polygon`` query parameter names, or a 422 saying why not.

    The parameter holds a JSON list of ``[lon, lat]`` pairs, so a drawn
    shape fits in a query string and the frontend can ask for it with a GET
    like every other request.
    """
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        fail(422, "invalid_aoi", "polygon must be a JSON list of [lon, lat] pairs", "polygon")
    if not isinstance(decoded, list):
        fail(422, "invalid_aoi", "polygon must be a JSON list of [lon, lat] pairs", "polygon")
    return _ring_from_positions(decoded, "polygon")


def _resolve(
    body: AnalysisRequest | None,
    *,
    aoi: str = "BGD",
    date: DateType | None = None,
    bbox: str | None = None,
    polygon: str | None = None,
    allow_density: bool = False,
) -> tuple[str, DateType | None, tuple[float, float, float, float], geometry.Ring | None]:
    """Merge an optional request body over the query parameters.

    Returns the AOI label, the date, the *area* the request is about and the
    polygon, if the area is one. The area is the explicit ``bbox`` when one
    was given, otherwise the bbox of the named preset — so a caller can never
    ask about a region and get the whole extent back. The label follows the
    area: a preset request is labelled with the preset id, a custom bbox with
    the bbox itself.

    A drawn polygon is both: its bounding box is the area (the grid and the
    map extent work on boxes) and the ring is returned alongside it so the
    detections can be filtered to the shape and the density divided by the
    cells the shape holds. It can arrive two ways — as ``polygon`` in the
    query string, or as the AOI object in the body — and the body wins.

    ``allow_density`` marks the endpoints whose payload actually carries a
    ``metric`` field; elsewhere ``metric=density`` is refused rather than
    ignored.
    """
    ring: geometry.Ring | None = None
    if polygon is not None:
        ring = _parse_ring_param(polygon)
    if body is not None:
        if body.aoi is not None:
            if isinstance(body.aoi, AoiBody):
                if body.aoi.type == "geojson":
                    ring = _parse_ring(body.aoi)
                    aoi = "custom"
                elif body.aoi.type == "preset" and body.aoi.id:
                    aoi = body.aoi.id
                else:
                    fail(
                        422,
                        "invalid_request",
                        "aoi must be a preset id, {type: 'preset', id} or "
                        "{type: 'geojson', geometry}; a custom box is expressed with bbox",
                        "aoi",
                    )
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

    if ring is not None:
        # A drawn shape wins over a preset id: the caller drew it.
        area = geometry.ring_bbox(ring)
        _check_cell_cap(area, cells=geometry.ring_cell_count(ring))
        return "custom", date, area, ring
    parsed = _parse_bbox(bbox) if bbox is not None else None
    if parsed is None:
        if aoi not in PRESET_IDS:
            fail(422, "unknown_aoi", f"unknown AOI {aoi!r}; known: {sorted(PRESET_IDS)}", "aoi")
        parsed = PRESET_BBOX[aoi]
        _check_cell_cap(parsed)
        return aoi, date, parsed, None
    # An explicit bbox is the area, so it is also the label: the same numbers
    # always read the same way, whatever spacing the caller used.
    _check_cell_cap(parsed)
    return ",".join(str(value) for value in parsed), date, parsed, None


def _check_cell_cap(
    area: tuple[float, float, float, float], *, cells: int | None = None
) -> None:
    """Refuse an AOI that covers more grid cells than the limit allows.

    The cap bounds the work one request can ask for: a huge bbox makes the
    density divisor enormous and the cell table enormous, and the docs promise
    a bound ("max cells per AOI request"). It is checked before any query
    runs, so an over-large area costs nothing.

    ``cells`` is the count to check when the caller already knows it — a
    polygon holds fewer cells than its bounding box, so the polygon's own
    count is the honest figure.
    """
    if cells is None:
        cells = harmonize.grid_cell_count(area)
    if cells > MAX_AOI_CELLS:
        fail(
            422,
            "aoi_too_large",
            f"the requested area covers {cells} grid cells; the limit is {MAX_AOI_CELLS}",
            "bbox",
        )


def _within(
    frame: pd.DataFrame,
    bbox: tuple[float, float, float, float],
    ring: geometry.Ring | None = None,
) -> pd.DataFrame:
    """Detections inside ``bbox`` ``[west, south, east, north]``.

    With a ``ring`` the detections are also kept only when they fall inside
    the drawn shape, so a polygon is honoured as a shape and not as its box.
    """
    west, south, east, north = bbox
    inside = frame[
        (frame["longitude"] >= west)
        & (frame["longitude"] <= east)
        & (frame["latitude"] >= south)
        & (frame["latitude"] <= north)
    ]
    if ring is None:
        return inside
    return geometry.within_ring(inside, ring)


def _area_series(
    dataset: Dataset,
    area: tuple[float, float, float, float],
    ring: geometry.Ring | None = None,
) -> pd.Series:
    """The harmonized daily series inside ``area``, zero-filled.

    An area with no detections is an area with no fire, not a missing area:
    the series is a continuous run of zeros over the dataset's own date range,
    the same rule the rest of the project applies to a day without fire.
    """
    frame = _within(dataset.detections, area, ring)
    if frame.empty:
        span = export.detections_date_range(dataset.detections)
        days = pd.date_range(span[0], span[1], freq="D", name="date")
        return pd.Series(0, index=days, dtype="int64", name="harmonized")
    return _continuous(harmonize.harmonized_series(frame))


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
@app.post("/api/v1/meta")
def meta(
    aoi: Annotated[str, Query(description="preset id the request is for")] = "BGD",
    polygon: PolygonParam = None,
    body: AnalysisRequest | None = None,
) -> Mapping[str, Any]:
    """Region, parameters and sensor epochs."""
    _, _, area, ring = _resolve(body, aoi=aoi, polygon=polygon)
    dataset = _dataset()
    frame = _within(dataset.detections, area, ring)
    return export.build_meta_response(
        frame,
        bbox=area,
        polygon=ring,
        # An area with no detections still has a region and a date range: it
        # is described by the dataset's own span rather than refused.
        date_range=export.detections_date_range(dataset.detections),
        source=dataset.source,
        generated_at=dataset.generated_at,
    )


@app.get("/api/series")
@app.get("/api/v1/series")
@app.post("/api/v1/series")
def series(
    polygon: PolygonParam = None,
    body: AnalysisRequest | None = None,
) -> Mapping[str, Any]:
    """Daily raw and harmonized counts, one row per day.

    ``metric=density`` (the default the startup flow in
    ``docs/ARCHITECTURE.md`` §7 asks for) serves the same counts divided by
    the region's grid-cell count; anything else is ``cell_days``.
    """
    _, _, area, ring = _resolve(body, polygon=polygon, allow_density=True)
    metric = body.metric if body is not None and body.metric is not None else "cell_days"
    dataset = _dataset()
    return export.build_series(
        _within(dataset.detections, area, ring),
        metric=metric,
        bbox=area,
        # A polygon divides by the cells the shape holds, not the cells its
        # box touches: a thin diagonal shape covers far fewer cells.
        n_cells=geometry.ring_cell_count(ring) if ring is not None else None,
        polygon=ring,
        # The dataset's span, not the area's: an area with no fire is a run of
        # zeros over the dataset's own dates, not an undatable empty frame.
        date_range=export.detections_date_range(dataset.detections),
        source=dataset.source,
        generated_at=dataset.generated_at,
    )


@app.get("/api/cells")
@app.get("/api/v1/cells")
@app.post("/api/v1/cells")
def cells(
    start: Annotated[DateType | None, Query(description="ISO date, inclusive")] = None,
    end: Annotated[DateType | None, Query(description="ISO date, inclusive")] = None,
    polygon: PolygonParam = None,
    body: AnalysisRequest | None = None,
) -> Mapping[str, Any]:
    """Grid cells over a date window, with raw and harmonized counts."""
    _, _, area, ring = _resolve(body, polygon=polygon)
    if start is not None and end is not None and start > end:
        fail(422, "invalid_window", "start must not be after end", "start")
    dataset = _dataset()
    return export.build_cells(
        _within(dataset.detections, area, ring),
        start=start,
        end=end,
        bbox=area,
        polygon=ring,
        date_range=export.detections_date_range(dataset.detections),
        source=dataset.source,
        generated_at=dataset.generated_at,
    )


@app.get("/api/baseline")
@app.get("/api/v1/baseline")
@app.post("/api/v1/baseline")
def baseline(
    polygon: PolygonParam = None,
    body: AnalysisRequest | None = None,
) -> Mapping[str, Any]:
    """Seasonal baseline: day-of-year percentiles of the harmonized series."""
    _, _, area, ring = _resolve(body, polygon=polygon)
    dataset = _dataset()
    return export.build_baseline(
        _area_series(dataset, area, ring),
        bbox=area,
        polygon=ring,
        source=dataset.source,
        generated_at=dataset.generated_at,
    )


def _anomaly_payload(
    dataset: Dataset,
    *,
    date: DateType | None,
    area: tuple[float, float, float, float],
    aoi: str,
    ring: geometry.Ring | None = None,
) -> Mapping[str, Any]:
    """Rank one date (or the last day in the data) against its season."""
    series = _area_series(dataset, area, ring)
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
        bbox=area,
        polygon=ring,
        source=dataset.source,
        generated_at=dataset.generated_at,
    )


@app.get("/api/anomaly")
def anomaly(
    date: Annotated[DateType, Query(description="ISO date to judge")],
    bbox: Annotated[str | None, Query(description="west,south,east,north")] = None,
    aoi: Annotated[str, Query(description="preset id the request is for")] = "BGD",
    polygon: PolygonParam = None,
    body: AnalysisRequest | None = None,
) -> Mapping[str, Any]:
    """Rank one date against its day-of-year baseline."""
    resolved_aoi, resolved_date, area, ring = _resolve(
        body, aoi=aoi, date=date, bbox=bbox, polygon=polygon
    )
    return _anomaly_payload(
        _dataset(), date=resolved_date, area=area, aoi=resolved_aoi, ring=ring
    )


@app.get("/api/v1/anomalies")
@app.post("/api/v1/anomalies")
def anomalies(
    date: Annotated[
        DateType | None, Query(description="ISO date to judge; defaults to the last day")
    ] = None,
    bbox: Annotated[str | None, Query(description="west,south,east,north")] = None,
    aoi: Annotated[str, Query(description="preset id the request is for")] = "BGD",
    polygon: PolygonParam = None,
    body: AnalysisRequest | None = None,
) -> Mapping[str, Any]:
    """The frontend's anomalies view: the requested date, or the latest day."""
    resolved_aoi, resolved_date, area, ring = _resolve(
        body, aoi=aoi, date=date, bbox=bbox, polygon=polygon
    )
    return _anomaly_payload(
        _dataset(), date=resolved_date, area=area, aoi=resolved_aoi, ring=ring
    )


@app.get("/api/critical-period")
@app.get("/api/v1/critical-period")
@app.post("/api/v1/critical-period")
def critical_period(
    aoi: Annotated[str, Query(description="preset id the request is for")] = "BGD",
    polygon: PolygonParam = None,
    body: AnalysisRequest | None = None,
) -> Mapping[str, Any]:
    """Onset, peak, end and window mass of the burning season."""
    resolved_aoi, _, area, ring = _resolve(body, aoi=aoi, polygon=polygon)
    dataset = _dataset()
    series = _area_series(dataset, area, ring)
    return export.build_critical_period(
        series,
        aoi=resolved_aoi,
        bbox=area,
        polygon=ring,
        source=dataset.source,
        generated_at=dataset.generated_at,
    )


@app.get("/api/export")
@app.get("/api/v1/export")
@app.post("/api/v1/export")
def export_csv(
    start: Annotated[DateType | None, Query(description="ISO date, inclusive")] = None,
    end: Annotated[DateType | None, Query(description="ISO date, inclusive")] = None,
    aoi: Annotated[str, Query(description="preset id the request is for")] = "BGD",
    bbox: Annotated[str | None, Query(description="west,south,east,north")] = None,
    polygon: PolygonParam = None,
    body: AnalysisRequest | None = None,
) -> Response:
    """The filtered hotspot records, as CSV.

    The challenge asks for the records behind the view to be downloadable, so
    this serves the observations themselves — one row per detection, with the
    original satellite named — rather than the derived cell-days the calendar
    shows. The date window and the area are the same ones the other
    endpoints take, so what comes out is what the screen showed.

    It takes a POST body too, because a drawn polygon can also arrive as the
    AOI object of ``docs/TRD.md`` §6.1.
    """
    _, _, area, ring = _resolve(body, aoi=aoi, bbox=bbox, polygon=polygon)
    if start is not None and end is not None and start > end:
        fail(422, "invalid_window", "start must not be after end", "start")
    dataset = _dataset()
    text = export.build_csv(
        _within(dataset.detections, area, ring),
        start=start,
        end=end,
    )
    stamp = f"{start or 'all'}_{end or 'all'}".replace(":", "-")
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="icarus_hotspots_{stamp}.csv"'
        },
    )


@app.get("/api/aoi")
@app.get("/api/v1/aoi")
def aoi() -> Mapping[str, Any]:
    """The preset AOIs the picker offers."""
    dataset = _dataset()
    return export.build_aoi(
        bbox=PRESET_BBOX["BGD"],
        source=dataset.source,
        generated_at=dataset.generated_at,
        date_range=export.detections_date_range(dataset.detections),
    )


@app.get("/api/validation")
@app.get("/api/v1/validation")
@app.post("/api/v1/validation")
def validation(
    polygon: PolygonParam = None,
    body: AnalysisRequest | None = None,
) -> Mapping[str, Any]:
    """Overlap-period agreement, raw against harmonized."""
    _, _, area, ring = _resolve(body, polygon=polygon)
    dataset = _dataset()
    try:
        return export.build_validation(
            _within(dataset.detections, area, ring),
            bbox=area,
            polygon=ring,
            date_range=export.detections_date_range(dataset.detections),
            source=dataset.source,
            generated_at=dataset.generated_at,
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
    # other (docs/ARCHITECTURE.md §13: same inputs + same hash => same output).
    return export.build_methods(
        bbox=PRESET_BBOX["BGD"],
        source=dataset.source,
        generated_at=dataset.generated_at,
        date_range=export.detections_date_range(dataset.detections),
    )


__all__ = [
    "ALLOWED_ORIGINS",
    "MAX_AOI_CELLS",
    "PRESET_IDS",
    "REQUEST_TIMEOUT_S",
    "AnalysisRequest",
    "TimeoutMiddleware",
    "app",
    "fail",
]
