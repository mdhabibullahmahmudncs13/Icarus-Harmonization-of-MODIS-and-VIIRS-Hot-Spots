"""Write the exact JSON the API contract defines, from harmonized detections.

This is the bridge between ``src/compute`` and the frontend: it lets real
cached data be served as static files before ``src/api`` exists, and it is
what ``src/api`` will call later. Every payload here validates against the
zod schemas in ``web/src/contract/schemas.ts`` (exported to
``docs/contract.schema.json``).

Deterministic given its inputs (pass ``generated_at`` for byte-stable
output). No LLM, no network.
"""

from __future__ import annotations

import argparse
import glob as globlib
import hashlib
import json
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.acquire import firms
from src.compute import anomaly, coverage, harmonize, schema, season, validate

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "web" / "public" / "data"

BANGLADESH_BBOX: tuple[float, float, float, float] = firms.BANGLADESH_BBOX

#: Sensor epochs and FIRMS product names come from the acquisition table, so
#: the interface and the downloader cannot drift apart.
DATASET_ORDER: tuple[str, ...] = (
    "MODIS_SP",
    "VIIRS_SNPP_SP",
    "VIIRS_NOAA20_SP",
    "VIIRS_NOAA21_SP",
)


#: Stream names each FIRMS product contributes, in the contract's short form
#: (the keys of ``schema.STREAM_BITS``). MODIS_SP covers both Terra and Aqua.
PRODUCT_STREAMS: dict[str, tuple[str, ...]] = {
    "MODIS_SP": ("MOD_T", "MOD_A"),
    "VIIRS_SNPP_SP": ("VIIRS_SNPP",),
    "VIIRS_NOAA20_SP": ("VIIRS_N20",),
    "VIIRS_NOAA21_SP": ("VIIRS_N21",),
}

#: Human labels for the datasets panel, keyed by FIRMS product id.
SENSOR_LABELS: dict[str, tuple[str, str]] = {
    "MODIS_SP": ("MODIS C6.1 (Terra + Aqua), 1 km", "Raw + harmonized MODIS series"),
    "VIIRS_SNPP_SP": ("VIIRS 375 m, Suomi-NPP", "Raw + harmonized VIIRS series"),
    "VIIRS_NOAA20_SP": ("VIIRS 375 m, NOAA-20", "Raw + harmonized VIIRS series"),
    "VIIRS_NOAA21_SP": ("VIIRS 375 m, NOAA-21", "Raw + harmonized VIIRS series"),
}

#: AOI presets, read from ``src/aoi_presets.json`` so this module and
#: ``tools/gen_mock.py`` cannot disagree about the picker list.
AOI_PRESETS_PATH = REPO_ROOT / "src" / "aoi_presets.json"



def load_presets() -> list[dict[str, Any]]:
    """The AOI presets as contract ``presets`` entries."""
    data = json.loads(AOI_PRESETS_PATH.read_text())
    return [
        {"id": str(p["id"]), "name": str(p["name"]), "bbox": [float(v) for v in p["bbox"]]}
        for p in data["presets"]
    ]


def _years_from_range(date_range: tuple[str, str]) -> dict[str, int]:
    """The ``years`` block: first and last calendar year the range covers."""
    return {"start": int(date_range[0][:4]), "end": int(date_range[1][:4])}


def years_in(series: pd.Series) -> list[int]:
    """Distinct calendar years present in a dated series, ascending."""
    if series.empty:
        return []
    return sorted({int(year) for year in series.index.year})


def streams_present(detections: pd.DataFrame) -> list[str]:
    """Streams whose sensor family appears in ``detections``.

    The harmonized frame carries ``sensor_family`` rather than the raw stream
    id, so the streams are those the sensor table assigns to the families in
    play. If a family is absent its streams are omitted, which is what the
    panel should show.
    """
    if detections.empty or "sensor_family" not in detections.columns:
        return []
    families = {str(value) for value in detections["sensor_family"].dropna().unique()}
    streams: list[str] = []
    for source in DATASET_ORDER:
        if firms.PRODUCTS[source].family in families:
            streams.extend(PRODUCT_STREAMS[source])
    return streams


def params_hash(
    *,
    bbox: tuple[float, float, float, float] = BANGLADESH_BBOX,
    cell_km: float = harmonize.DEFAULT_CELL_KM,
    min_confidence: float = schema.MIN_CONFIDENCE,
    date_range: tuple[str, str],
) -> str:
    """Stable id for the parameter set a response was produced with.

    Every response carries it so two payloads can be matched and a cached
    response discarded when a parameter changes. It covers parameters only —
    never the data tier, never a timestamp — so the same parameters hash the
    same whether they were served from the cache or from the fixture.
    """
    payload = json.dumps(
        {
            "bbox": [float(v) for v in bbox],
            "cell_km": float(cell_km),
            "min_confidence": int(min_confidence),
            "date_range": [str(date_range[0]), str(date_range[1])],
            "confidence_mapping": dict(schema.confidence_mapping()),
            "collapse": "cell_days",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()[:12]


def sensor_table() -> list[dict[str, Any]]:
    """Sensor epochs in the contract's ``sensors`` shape."""
    order = DATASET_ORDER
    rows: list[dict[str, Any]] = []
    for source in order:
        product = firms.PRODUCTS[source]
        rows.append(
            {
                "product": product.source,
                "family": product.family,
                "start": product.start.isoformat(),
                "end": product.end.isoformat() if product.end else None,
            }
        )
    return rows


DATASET_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/"


def _iso_timestamp(value: datetime | None) -> str:
    stamp = value or datetime.now(UTC)
    return stamp.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _native(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _number_or_null(value: Any) -> float | None:
    """A JSON number, or ``None`` when the value is missing or not finite.

    The schema accepts ``null`` for an undefined quantity and never accepts
    ``NaN`` (invalid JSON), so an un-scored value must become ``None`` here.
    """
    if value is None:
        return None
    number = float(value)
    return number if np.isfinite(number) else None


def _int_or_null(value: Any) -> int | None:
    return None if value is None else int(value)


def build_meta(
    *,
    source: str = "cache",
    bbox: tuple[float, float, float, float] = BANGLADESH_BBOX,
    cell_km: float = harmonize.DEFAULT_CELL_KM,
    min_confidence: float = schema.MIN_CONFIDENCE,
    date_range: tuple[str, str],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """The ``meta`` block every response carries.

    ``params_hash`` is derived here rather than passed in, so it always
    describes the parameters actually used for the payload it sits on.
    """
    return {
        "source": source,
        "generated_at": _iso_timestamp(generated_at),
        "region": {"bbox": [float(v) for v in bbox]},
        "cell_km": float(cell_km),
        "min_confidence": int(min_confidence),
        "date_range": [date_range[0], date_range[1]],
        "params_hash": params_hash(
            bbox=bbox, cell_km=cell_km, min_confidence=min_confidence, date_range=date_range
        ),
    }


def detections_date_range(detections: pd.DataFrame) -> tuple[str, str]:
    """Inclusive ``[start, end]`` ISO dates covered by the detections."""
    if detections.empty:
        raise ValueError("cannot derive a date range from an empty detection set")
    return (
        detections["acq_date"].min().strftime("%Y-%m-%d"),
        detections["acq_date"].max().strftime("%Y-%m-%d"),
    )


def build_meta_response(detections: pd.DataFrame, **kwargs: Any) -> dict[str, Any]:
    """``GET /api/v1/meta`` payload."""
    kwargs.setdefault("date_range", detections_date_range(detections))
    return {
        "meta": build_meta(**kwargs),
        "sensors": sensor_table(),
        "years": _years_from_range(kwargs["date_range"]),
        "streams": streams_present(detections),
    }


def build_series(detections: pd.DataFrame, **kwargs: Any) -> dict[str, Any]:
    """``GET /api/v1/series`` payload: daily counts, one row per calendar day.

    ``metric`` is ``cell_days`` and ``bin_days`` is 1 because the series is not
    binned; an 8-day view would be a different payload, not a different flag.

    Each row also carries S7 ``coverage`` and ``source`` for the eight-day bin
    it falls in (docs/TESTING.md §7). Coverage and source are properties of the
    bin, so every day in a bin reports the same pair.
    """
    kwargs.setdefault("date_range", detections_date_range(detections))
    rows = [
        {key: _native(value) for key, value in row.items()}
        for row in harmonize.daily_series(detections).to_dict(orient="records")
    ]
    index = coverage.coverage_index(detections)
    for row in rows:
        stamp = pd.Timestamp(row["date"])
        coverage_value, source = coverage.coverage_for_date(index, stamp)
        row["date"] = stamp.strftime("%Y-%m-%d")
        row["coverage"] = coverage_value
        row["source"] = source
    return {
        "meta": build_meta(**kwargs),
        "metric": "cell_days",
        "bin_days": 1,
        "series": rows,
    }


def build_cells(
    detections: pd.DataFrame,
    *,
    start: date | None = None,
    end: date | None = None,
    cell_km: float = harmonize.DEFAULT_CELL_KM,
    reference_latitude_deg: float = harmonize.REFERENCE_LATITUDE_DEG,
    **kwargs: Any,
) -> dict[str, Any]:
    """``GET /api/cells`` payload over a window."""
    kwargs.setdefault("date_range", detections_date_range(detections))
    frame = detections
    if start is not None:
        frame = frame[frame["acq_date"] >= pd.Timestamp(start)]
    if end is not None:
        frame = frame[frame["acq_date"] <= pd.Timestamp(end)]

    rows: list[dict[str, Any]] = []
    if not frame.empty:
        grouped = frame.assign(date=frame["acq_date"].dt.normalize()).groupby("cell_id")
        peak = (
            grouped["frp"].max()
            if "frp" in frame.columns
            else pd.Series(0.0, index=grouped.size().index)
        )
        counts = pd.DataFrame(
            {
                "raw": grouped.size(),
                "harmonized": grouped["date"].nunique(),
                "peak_frp": peak,
            }
        ).sort_index()
        for cell, row in counts.iterrows():
            rows.append(
                {
                    "cell_id": str(cell),
                    "bounds": [float(v) for v in harmonize.cell_bounds(cell, cell_km, reference_latitude_deg)],
                    "raw": int(row["raw"]),
                    "harmonized": int(row["harmonized"]),
                    "peak_frp": _number_or_null(row["peak_frp"]),
                }
            )
    window = {
        "start": start.isoformat() if start is not None else kwargs["date_range"][0],
        "end": end.isoformat() if end is not None else kwargs["date_range"][1],
    }
    return {"meta": build_meta(cell_km=cell_km, **kwargs), "window": window, "cells": rows}


def build_baseline(
    series: pd.Series,
    *,
    window_days: int = harmonize.DEFAULT_WINDOW_DAYS,
    **kwargs: Any,
) -> dict[str, Any]:
    """``GET /api/baseline`` payload."""
    if not series.empty:
        kwargs.setdefault(
            "date_range",
            (
                series.index.min().strftime("%Y-%m-%d"),
                series.index.max().strftime("%Y-%m-%d"),
            ),
        )
    kwargs.setdefault("date_range", ("1970-01-01", "1970-01-01"))
    percentiles = harmonize.baseline_percentiles(series, window_days).dropna(how="any")
    rows = [
        {"doy": int(doy), **{k: float(v) for k, v in row.items()}}
        for doy, row in percentiles.iterrows()
    ]
    return {
        "meta": build_meta(**kwargs),
        "window_days": int(window_days),
        "years_used": years_in(series),
        "baseline": rows,
    }


def build_anomaly(
    series: pd.Series,
    *,
    date_: pd.Timestamp | str,
    aoi: str = "BGD",
    window_days: int = harmonize.DEFAULT_WINDOW_DAYS,
    **kwargs: Any,
) -> dict[str, Any]:
    """``GET /api/v1/anomalies`` payload: one date ranked against its season.

    Uses the flag-bearing scorer rather than the percentile report: the card
    needs ``flag``/``reason`` so a not-scored day can say why it was not
    scored, and the schema allows ``value``/``percentile`` to be null.
    """
    if not series.empty:
        kwargs.setdefault(
            "date_range",
            (
                series.index.min().strftime("%Y-%m-%d"),
                series.index.max().strftime("%Y-%m-%d"),
            ),
        )
    kwargs.setdefault("date_range", ("1970-01-01", "1970-01-01"))
    score = anomaly(series, date_, window_days=window_days)
    low, high = score["doy_range"]
    return {
        "meta": build_meta(**kwargs),
        "query": {"date": pd.Timestamp(date_).strftime("%Y-%m-%d"), "aoi": aoi},
        "value": _number_or_null(score["value"]),
        "percentile": _number_or_null(score["percentile"]),
        "flag": score["flag"],
        "baseline_window": int(score["baseline_window"]),
        "doy_range": [int(low), int(high)],
        "years_used": [int(year) for year in score["years_used"]],
        "reason": score["reason"],
    }


def year_timing_deviation(
    series: pd.Series,
    *,
    bin_days: int = season.BIN_DAYS,
) -> list[dict[str, int]]:
    """Per-year shift of the burning peak, in days, from the multi-year mean.

    Each year's 46-bin seasonal profile is built from that year's harmonized
    counts and its argmax is that year's peak bin. ``days`` is the distance
    from the mean peak bin across years, so a positive number means that year
    burned later than the average. A year with no activity peaks at bin 0; that
    is a real statement (no fire), not a missing value.
    """
    if series.empty:
        return []
    per_year: dict[int, list[float]] = {}
    for stamp, value in series.items():
        bins = per_year.setdefault(int(stamp.year), [0.0] * 46)
        bins[season.bin_of_doy(int(stamp.dayofyear), bin_days) - 1] += float(value)
    peaks = {year: max(range(46), key=lambda i: bins[i]) for year, bins in per_year.items()}
    mean_peak = sum(peaks.values()) / len(peaks)
    return [
        {"year": year, "days": round((peak - mean_peak) * bin_days)}
        for year, peak in sorted(peaks.items())
    ]


def build_critical_period(
    series: pd.Series,
    *,
    aoi: str = "BGD",
    bin_days: int = season.BIN_DAYS,
    **kwargs: Any,
) -> dict[str, Any]:
    """``GET /api/v1/critical-period`` payload.

    When the season carries too little activity to define a window, ``window``
    is ``null`` and ``insufficient_activity`` is true: the contract accepts a
    null window (its ``start_bin`` is bounded to 1-46, so there is no zero
    window to invent) and the frontend already renders that state.
    """
    if not series.empty:
        kwargs.setdefault(
            "date_range",
            (
                series.index.min().strftime("%Y-%m-%d"),
                series.index.max().strftime("%Y-%m-%d"),
            ),
        )
    kwargs.setdefault("date_range", ("1970-01-01", "1970-01-01"))
    rows = [
        {"date": pd.Timestamp(stamp).strftime("%Y-%m-%d"), "harm_total": float(value)}
        for stamp, value in series.items()
    ]
    result = season.critical_period(rows, bin_days=bin_days)
    window = result["window"]
    return {
        "meta": build_meta(**kwargs),
        "aoi": aoi,
        "insufficient_activity": bool(result["insufficient_activity"]),
        "onset_bin": _int_or_null(result["onset_bin"]),
        "peak_bin": _int_or_null(result["peak_bin"]),
        "end_bin": _int_or_null(result["end_bin"]),
        "window": (
            None
            if window is None
            else {
                "start_bin": int(window["start_bin"]),
                "end_bin": int(window["end_bin"]),
                "mass": float(window["mass"]),
            }
        ),
        "year_timing_deviation": year_timing_deviation(series, bin_days=bin_days),
    }


def build_aoi(**kwargs: Any) -> dict[str, Any]:
    """``GET /api/v1/aoi`` payload: the preset list."""
    kwargs.setdefault("date_range", ("2003-01-01", "2026-09-30"))
    return {"meta": build_meta(**kwargs), "presets": load_presets()}


def build_validation(
    detections: pd.DataFrame,
    *,
    cell_km: float = harmonize.DEFAULT_CELL_KM,
    **kwargs: Any,
) -> dict[str, Any]:
    """``GET /api/validation`` payload."""
    kwargs.setdefault("date_range", detections_date_range(detections))
    kwargs.setdefault("cell_km", cell_km)
    report = validate.validate_overlap(detections, cell_km=cell_km)
    return {"meta": build_meta(**kwargs), **report.as_dict()}


def build_methods(
    *,
    cell_km: float = harmonize.DEFAULT_CELL_KM,
    min_confidence: float = schema.MIN_CONFIDENCE,
    date_range: tuple[str, str] = ("2003-01-01", "2026-09-30"),
    **kwargs: Any,
) -> dict[str, Any]:
    """``GET /api/methods`` payload."""
    kwargs.setdefault("cell_km", cell_km)
    kwargs.setdefault("min_confidence", min_confidence)
    kwargs.setdefault("date_range", date_range)
    return {
        "meta": build_meta(**kwargs),
        "cell_km": float(cell_km),
        "min_confidence": int(min_confidence),
        # The panel reports the VIIRS classes by their documented names, not by
        # the single letters the product files carry.
        "confidence_mapping": {
            "low": int(schema.VIIRS_CONFIDENCE_MAP["l"]),
            "nominal": int(schema.VIIRS_CONFIDENCE_MAP["n"]),
            "high": int(schema.VIIRS_CONFIDENCE_MAP["h"]),
        },
        "collapse_rule": (
            f"Detections are assigned to {cell_km:g} km grid cells by their coordinates, with "
            "longitude steps scaled by cos(reference latitude) so cells stay close to the stated "
            "size (an approximation, not a geodesic). Within each cell and calendar day all "
            "detections collapse to one cell-day. The harmonized daily count is the number of "
            "distinct cell-days detected by any sensor that day; the raw daily count is the number "
            "of detections at or above the confidence threshold."
        ),
        "notices": [
            "Suomi-NPP VIIRS data ends 1 Nov 2026; NASA stops serving it after that date.",
            "MODIS is being retired; prefer VIIRS on NOAA-20 and NOAA-21 for continuity.",
            "Sensor epoch dates are placeholders pending verification against FIRMS docs.",
        ],
        "datasets": [
            {
                "id": f"FIRMS_{product.source}",
                "product": product.source,
                "sensor": SENSOR_LABELS[product.source][0],
                "used_for": SENSOR_LABELS[product.source][1],
                "url": DATASET_URL,
            }
            for product in (firms.PRODUCTS[source] for source in DATASET_ORDER)
        ],
    }


def write_json(payload: Mapping[str, Any], path: Path) -> Path:
    """Write ``payload`` as pretty JSON, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    return path


def write_all(
    detections: pd.DataFrame,
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    series: pd.Series | None = None,
    anomaly_date: str | None = None,
    source: str = "cache",
    generated_at: datetime | None = None,
) -> list[Path]:
    """Write every contract payload to ``out_dir`` and return the paths.

    ``detections`` must already be harmonized (filtered and gridded). The
    series defaults to the harmonized *total* series, which is what the
    baseline and the anomaly are computed against.
    """
    if series is None:
        series = harmonize.harmonized_series(detections)
    packets: dict[str, Mapping[str, Any]] = {
        "meta.json": build_meta_response(detections, source=source, generated_at=generated_at),
        "series.json": build_series(detections, source=source, generated_at=generated_at),
        "cells.json": build_cells(detections, source=source, generated_at=generated_at),
        "baseline.json": build_baseline(series, source=source, generated_at=generated_at),
        "critical-period.json": build_critical_period(
            series, source=source, generated_at=generated_at
        ),
        "validation.json": build_validation(detections, source=source, generated_at=generated_at),
        "methods.json": build_methods(source=source, generated_at=generated_at),
        "aoi.json": build_aoi(source=source, generated_at=generated_at),
    }
    if anomaly_date is not None:
        packets["anomaly.json"] = build_anomaly(
            series, date_=anomaly_date, source=source, generated_at=generated_at
        )
    return [write_json(payload, out_dir / name) for name, payload in packets.items()]


def load_detections(pattern: str = "cache/raw/*.parquet") -> pd.DataFrame:
    """Read the raw parquet written by ``src/acquire/firms.py``.

    Returns the concatenated frames; the caller harmonizes them.
    """
    absolute = pattern if os.path.isabs(pattern) else str(REPO_ROOT / pattern)
    paths = sorted(Path(path) for path in globlib.glob(absolute))
    if not paths:
        raise FileNotFoundError(f"no parquet matched {pattern!r}; run `make cache` first")
    return pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.compute.export",
        description="Write the API contract JSON from cached FIRMS parquet.",
    )
    parser.add_argument("--glob", default="cache/raw/*.parquet")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--anomaly-date", default=None)
    args = parser.parse_args(argv)

    try:
        raw = load_detections(args.glob)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    detections = harmonize.harmonize(raw)
    if detections.empty:
        print("no detections survived harmonization", file=sys.stderr)
        return 1
    written = write_all(detections, args.out, anomaly_date=args.anomaly_date)
    for path in written:
        print(f"wrote {path}")
    return 0


__all__: Iterable[str] = (
    "AOI_PRESETS_PATH",
    "BANGLADESH_BBOX",
    "DEFAULT_OUT_DIR",
    "PRODUCT_STREAMS",
    "SENSOR_LABELS",
    "build_anomaly",
    "build_aoi",
    "build_baseline",
    "build_cells",
    "build_critical_period",
    "build_meta",
    "build_meta_response",
    "build_methods",
    "build_series",
    "build_validation",
    "detections_date_range",
    "load_detections",
    "load_presets",
    "main",
    "params_hash",
    "sensor_table",
    "streams_present",
    "write_all",
    "write_json",
    "year_timing_deviation",
    "years_in",
)


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(main())
