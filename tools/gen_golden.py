#!/usr/bin/env python3
"""Phase 2 golden-fixture generator for Project Icarus.

The compute core is deterministic: the same detections always produce the same
series, cells, baseline, critical period and validation report. These goldens
freeze that output, so a change in the science that moves a number fails a test
instead of quietly rewriting history.

Two canonical inputs, both offline and seeded:

* the **step** scenario -- five cells burning in June 2011 (MODIS only) and
  June 2013 (MODIS plus two VIIRS detections per cell-day). This is the
  mechanism the project exists to fix: the raw series steps up ~3x at the
  sensor transition while the harmonized series does not.
* the synthetic detections from :mod:`src.demo` -- the same generator behind
  the committed offline demo fixture -- pushed through the overlap validator.

Usage:
    python3 tools/gen_golden.py            # rewrite tests/golden/
    python3 tools/gen_golden.py --check    # fail if the committed goldens drift

Determinism: fixed seed, fixed iteration order, floats rounded to 6 decimals
-> identical bytes on every run.

Synthetic data is never evidence: every golden records what the deterministic
core computes over synthetic detections, not an observation.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.compute import (
    STREAM_BITS,
    Detection,
    collapse_cell_days,
    critical_period,
    seasonal_baseline,
    to_cells,
    to_series,
    validate_overlap,
)
from src.compute.coverage import bin_coverage
from src.compute.harmonize import harmonize
from src.demo import identical_cell_days, synthetic_detections

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Where the committed goldens live.
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"

#: The VIIRS start date used to split the series into "pre" and "post".
STEP_TRANSITION = "2012-01-20"

#: Floats are rounded to this many decimals before serialising, so the file is
#: stable across platforms without hiding a real change in the science.
ROUND_DP = 6


# --- canonical "step" scenario ---------------------------------------------


def _detection(
    lon: float,
    lat: float,
    date: str,
    stream: str,
    instrument: str,
    *,
    conf_num: int | None = None,
    conf_class: str | None = None,
    hs_type: int | None = 0,
    frp: float = 10.0,
) -> Detection:
    return Detection(
        acq_date=date,
        acq_time="1200",
        lon=lon,
        lat=lat,
        frp=frp,
        conf_num=conf_num,
        conf_class=conf_class,
        hs_type=hs_type,
        instrument=instrument,
        sat="T" if stream == "MOD_T" else "S-NPP",
        stream=stream,
        stream_bit=STREAM_BITS[stream],
    )


def _modis(lon: float, lat: float, date: str) -> Detection:
    return _detection(lon, lat, date, "MOD_T", "MODIS", conf_num=80)


def _viirs(lon: float, lat: float, date: str) -> Detection:
    return _detection(lon, lat, date, "VIIRS_SNPP", "VIIRS", conf_class="h")


def step_detections() -> list[Detection]:
    """MODIS-only June 2011, then MODIS plus 2x VIIRS per cell-day in June 2013."""
    dets: list[Detection] = []
    cells = [(0.1 + 0.2 * i, 0.1 + 0.2 * i) for i in range(5)]
    for month_year in ("2011-06", "2013-06"):
        for day in range(1, 31):
            date = f"{month_year}-{day:02d}"
            for i, (lon, lat) in enumerate(cells):
                if (day + i) % 2 == 0:
                    dets.append(_modis(lon, lat, date))
                    if month_year == "2013-06":  # VIIRS only after the transition
                        dets.append(_viirs(lon, lat, date))
                        dets.append(_viirs(lon, lat, date))
    return dets


def _mean(rows: list[dict], key: str) -> float:
    return sum(row[key] for row in rows) / len(rows)


def step_payloads() -> dict[str, Any]:
    """Series, cells, baseline and critical period for the step scenario."""
    cell_days = collapse_cell_days(step_detections())
    series = to_series(cell_days)

    pre = [r for r in series if r["date"] < STEP_TRANSITION]
    post = [r for r in series if r["date"] >= STEP_TRANSITION]

    # Only the days the scenario covers carry a baseline; the empty rest of the
    # year would be 300+ rows of zeros with no information in them.
    baseline = [row for row in seasonal_baseline(series) if row["p95"] > 0.0]

    return {
        "series": series,
        "cells": to_cells(cell_days),
        "baseline": baseline,
        "critical_period": critical_period(series),
        "headline": {
            "transition": STEP_TRANSITION,
            "pre_days": len(pre),
            "post_days": len(post),
            "raw_step_ratio": _mean(post, "raw_total") / _mean(pre, "raw_total"),
            "harmonized_step_ratio": _mean(post, "harm_total") / _mean(pre, "harm_total"),
        },
    }


# --- overlap validation over the synthetic detections ----------------------


def identical_overlap_payload() -> dict[str, Any]:
    """The clean case: both sensors see the same cell-days, VIIRS 3x each."""
    detections = identical_cell_days(days=40, multiplier=3)
    return validate_overlap(detections, cell_km=5.5).as_dict()


def noisy_overlap_payload() -> dict[str, Any]:
    """The seasonal case: VIIRS adds variable detections on top of MODIS."""
    detections = synthetic_detections(days=240)
    return validate_overlap(detections, cell_km=5.5).as_dict()


#: Two 8-day bins of the 240-day synthetic span in which MODIS is silenced, so
#: the golden exercises the ``VIIRS_CAL`` source tag as well as ``MODIS``.
MODIS_OUTAGE_DAYS = slice(64, 80)


def coverage_detections() -> Any:
    """Synthetic detections with a MODIS outage over two bins.

    A real observing gap is what coverage exists to expose. Dropping MODIS for
    sixteen days makes those bins fall back to VIIRS, so the golden records a
    payload with more than one source class rather than a uniform 1.0.
    """
    frame = synthetic_detections(days=240)
    dates = sorted({str(value) for value in frame["acq_date"].tolist()})
    outage = set(dates[MODIS_OUTAGE_DAYS])
    drop = (frame["instrument"] == "MODIS") & frame["acq_date"].isin(outage)
    return frame[~drop].reset_index(drop=True)


def coverage_payload() -> list[dict[str, Any]]:
    """S7 per-bin coverage and source over the synthetic detections.

    Frozen as a golden so a change to the coverage definition or its source
    tagging fails a test instead of silently re-hatching the calendar.
    """
    table = bin_coverage(harmonize(coverage_detections()))
    return [
        {
            "year": int(row.year),
            "bin": int(row.bin),
            "n_days": int(row.n_days),
            "observed_days": int(row.observed_days),
            "modis_days": int(row.modis_days),
            "viirs_days": int(row.viirs_days),
            "cov_modis": float(row.cov_modis),
            "cov_viirs": float(row.cov_viirs),
            "coverage": float(row.coverage),
            "source": str(row.source),
        }
        for row in table.itertuples()
    ]


def build() -> dict[str, Any]:
    """Every golden keyed by file stem (``<stem>.json``)."""
    step = step_payloads()
    identical = identical_overlap_payload()
    noisy = noisy_overlap_payload()
    return {
        "step_series": step["series"],
        "step_cells": step["cells"],
        "step_baseline": step["baseline"],
        "step_critical_period": step["critical_period"],
        "identical_overlap": identical,
        "noisy_overlap": noisy,
        "coverage_bins": coverage_payload(),
        "headline": {
            **step["headline"],
            "identical_overlap": {
                "raw_ratio": identical["raw"]["ratio"],
                "harmonized_ratio": identical["harmonized"]["ratio"],
            },
            "noisy_overlap": {
                "raw_pearson": noisy["raw"]["pearson"],
                "harmonized_pearson": noisy["harmonized"]["pearson"],
                "raw_ratio": noisy["raw"]["ratio"],
                "harmonized_ratio": noisy["harmonized"]["ratio"],
            },
        },
    }


# --- serialisation and comparison -----------------------------------------


def canonical(value: Any) -> Any:
    """Round floats and strip non-finite values so the JSON is strict."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        rounded = round(value, ROUND_DP)
        return 0.0 if rounded == 0 else rounded  # collapse -0.0
    if isinstance(value, Mapping):
        return {str(k): canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    return value


def render(payload: Any) -> str:
    """The exact bytes written for one golden."""
    return json.dumps(canonical(payload), indent=2, sort_keys=False, allow_nan=False) + "\n"


def write(out_dir: Path = GOLDEN_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, payload in build().items():
        path = out_dir / f"{name}.json"
        path.write_text(render(payload))
        written.append(path)
    return written


def compare(out_dir: Path = GOLDEN_DIR) -> list[str]:
    """Names of goldens whose committed content differs from a fresh run."""
    drifted: list[str] = []
    for name, payload in build().items():
        path = out_dir / f"{name}.json"
        expected = render(payload)
        if not path.exists():
            drifted.append(f"{name}: missing ({path})")
        elif path.read_text() != expected:
            drifted.append(f"{name}: committed contents differ from a fresh run")
    return drifted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=GOLDEN_DIR, help="golden directory")
    parser.add_argument("--check", action="store_true", help="verify instead of writing")
    args = parser.parse_args(argv)

    payloads = build()
    if args.check:
        drifted = compare(args.out)
        if drifted:
            print("GOLDEN DRIFT:", file=sys.stderr)
            for item in drifted:
                print("  " + item, file=sys.stderr)
            return 1
        print(f"golden: OK ({len(payloads)} files, {args.out})")
        return 0

    written = write(args.out)
    headline = payloads["headline"]
    print(f"wrote {len(written)} goldens to {args.out}")
    print(f"  raw step ratio  : {headline['raw_step_ratio']:.2f}x")
    print(f"  harm step ratio : {headline['harmonized_step_ratio']:.2f}x")
    print(f"  identical ratio : {headline['identical_overlap']['raw_ratio']} raw"
          f" -> {headline['identical_overlap']['harmonized_ratio']} harmonized")
    print(f"  noisy pearson   : {headline['noisy_overlap']['raw_pearson']} raw"
          f" -> {headline['noisy_overlap']['harmonized_pearson']} harmonized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
