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
from src.compute import anomaly, harmonize, schema, validate

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


def build_meta(
    *,
    source: str = "cache",
    bbox: tuple[float, float, float, float] = BANGLADESH_BBOX,
    cell_km: float = harmonize.DEFAULT_CELL_KM,
    min_confidence: float = schema.MIN_CONFIDENCE,
    date_range: tuple[str, str],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """The ``meta`` block every response carries."""
    return {
        "source": source,
        "generated_at": _iso_timestamp(generated_at),
        "region": {"bbox": [float(v) for v in bbox]},
        "cell_km": float(cell_km),
        "min_confidence": float(min_confidence),
        "date_range": [date_range[0], date_range[1]],
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
    """``GET /api/meta`` payload."""
    kwargs.setdefault("date_range", detections_date_range(detections))
    return {"meta": build_meta(**kwargs), "sensors": sensor_table()}


def build_series(detections: pd.DataFrame, **kwargs: Any) -> dict[str, Any]:
    """``GET /api/series`` payload."""
    kwargs.setdefault("date_range", detections_date_range(detections))
    rows = [
        {key: _native(value) for key, value in row.items()}
        for row in harmonize.daily_series(detections).to_dict(orient="records")
    ]
    for row in rows:
        row["date"] = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
    return {"meta": build_meta(**kwargs), "rows": rows}


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
                    "peak_frp": float(row["peak_frp"]),
                }
            )
    return {"meta": build_meta(cell_km=cell_km, **kwargs), "rows": rows}


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
        "years_used": max(harmonize.years_used(series), 1),
        "rows": rows,
    }


def build_anomaly(
    series: pd.Series,
    *,
    date_: pd.Timestamp | str,
    window_days: int = harmonize.DEFAULT_WINDOW_DAYS,
    **kwargs: Any,
) -> dict[str, Any]:
    """``GET /api/anomaly`` payload."""
    report = anomaly.anomaly_report(series, date_, window_days)
    if not series.empty:
        kwargs.setdefault(
            "date_range",
            (
                series.index.min().strftime("%Y-%m-%d"),
                series.index.max().strftime("%Y-%m-%d"),
            ),
        )
    kwargs.setdefault("date_range", ("1970-01-01", "1970-01-01"))
    return {"meta": build_meta(**kwargs), **report}


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
        "min_confidence": float(min_confidence),
        "confidence_mapping": dict(schema.confidence_mapping()),
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
            {"id": f"FIRMS_{product.source}", "product": product.source, "url": DATASET_URL}
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
        "validation.json": build_validation(detections, source=source, generated_at=generated_at),
        "methods.json": build_methods(source=source, generated_at=generated_at),
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
    "BANGLADESH_BBOX",
    "DEFAULT_OUT_DIR",
    "build_anomaly",
    "build_baseline",
    "build_cells",
    "build_meta",
    "build_meta_response",
    "build_methods",
    "build_series",
    "build_validation",
    "detections_date_range",
    "load_detections",
    "main",
    "sensor_table",
    "write_all",
    "write_json",
)


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(main())
