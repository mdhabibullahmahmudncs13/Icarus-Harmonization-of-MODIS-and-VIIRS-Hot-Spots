#!/usr/bin/env python3
"""Write the API contract payloads from cached FIRMS parquet.

The static-export half of :mod:`src.compute.export`: the payload builders
live there because the API serves them, and the writing lives here because
only a command-line run writes files. The API never imports this module.

Usage:
    python -m tools.export_payloads                      # write to web/public/data
    python -m tools.export_payloads --out DIR
    python -m tools.export_payloads --anomaly-date 2015-03-01

Deterministic given its inputs: pass ``generated_at`` for byte-stable output.
No LLM, no network.
"""

from __future__ import annotations

import argparse
import glob as globlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.compute import export, harmonize

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "web" / "public" / "data"


def write_json(payload: Mapping[str, object], path: Path) -> Path:
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
    packets: dict[str, Mapping[str, object]] = {
        "meta.json": export.build_meta_response(detections, source=source, generated_at=generated_at),
        "series.json": export.build_series(detections, source=source, generated_at=generated_at),
        "cells.json": export.build_cells(detections, source=source, generated_at=generated_at),
        "baseline.json": export.build_baseline(series, source=source, generated_at=generated_at),
        "critical-period.json": export.build_critical_period(
            series, source=source, generated_at=generated_at
        ),
        "validation.json": export.build_validation(detections, source=source, generated_at=generated_at),
        "methods.json": export.build_methods(source=source, generated_at=generated_at),
        "aoi.json": export.build_aoi(source=source, generated_at=generated_at),
    }
    if anomaly_date is not None:
        packets["anomaly.json"] = export.build_anomaly(
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
        prog="python -m tools.export_payloads",
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


__all__ = (
    "DEFAULT_OUT_DIR",
    "load_detections",
    "main",
    "write_all",
    "write_json",
)


if __name__ == "__main__":
    raise SystemExit(main())
