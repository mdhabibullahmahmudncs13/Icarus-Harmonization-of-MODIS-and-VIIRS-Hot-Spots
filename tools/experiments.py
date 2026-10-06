#!/usr/bin/env python3
"""Run the E1-E9 validation experiments and write the report.

Deterministic and network-free. Reads the served detections (the cache, or the
offline fixture with ``--data fixture``), runs every experiment, and writes:

* ``validation/results.json`` — machine-readable results
* ``validation/figures/E*.svg`` — one figure per experiment
* ``docs/VALIDATION.md`` — the human report

E9 measures the environment (cache size, API latency), so the report is a
record of one run rather than a byte-reproducible artifact; there is no
``--check`` gate. The experiments themselves are covered by
``tests/test_experiments.py`` on the deterministic synthetic input.

Usage:
    python -m tools.experiments                  # run over the cache
    python -m tools.experiments --data fixture   # run over the offline fixture
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from src.acquire import burned_area, safe
from src.compute import export, harmonize
from src.validate import run_all
from src.validate.report import render_markdown, render_svg

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "validation"
REPORT_PATH = REPO_ROOT / "docs" / "VALIDATION.md"


def measure_api_latency(detections) -> float | None:
    """Seconds to build one ``/api/v1/series`` payload from the detections.

    Measures the payload build only — the API gridds and caches the dataset at
    startup, so a request pays for ``build_series``, not for ``harmonize``.
    """
    try:
        gridded = harmonize.harmonize(detections)
        start = time.perf_counter()
        export.build_series(gridded)
        return time.perf_counter() - start
    except Exception:  # noqa: BLE001 - a measurement must never break the run
        return None


def load(data: str):
    """Return ``(detections, source_label)`` for the requested data tier."""
    if data == "fixture":
        path = safe.FIXTURE_DIR / "detections.parquet"
        if not path.exists():
            print(f"no fixture at {path}; run `python -m src.demo`", file=sys.stderr)
            raise SystemExit(2)
        return export.load_detections(str(path)), "fixture"
    if safe.is_offline() and (safe.FIXTURE_DIR / "detections.parquet").exists():
        return export.load_detections(str(safe.FIXTURE_DIR / "detections.parquet")), "fixture"
    return export.load_detections(), "cache"


def artifacts(results) -> dict[Path, str]:
    """The exact files the run writes, as ``path -> text``."""
    written: dict[Path, str] = {
        RESULTS_DIR / "results.json": json.dumps(results, indent=2, sort_keys=False) + "\n",
        REPORT_PATH: render_markdown(results) + "\n",
    }
    for experiment in results["experiments"]:
        svg = render_svg(experiment.get("figure"))
        if svg:
            written[RESULTS_DIR / "figures" / f"{experiment['id']}.svg"] = svg + "\n"
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", choices=("cache", "fixture"), default="cache")
    parser.add_argument("--cold-start", type=float, default=None, help="measured offline cold start, seconds")
    args = parser.parse_args(argv)

    detections, source = load(args.data)
    cache_dir = safe.CACHE_DIR if source == "cache" else None
    # E8 needs the 0.25° burned-area grid; when it has not been fetched the
    # experiment reports a limitation instead of a number.
    burned = burned_area.load_derived()
    results = run_all(
        detections,
        source=source,
        cache_dir=cache_dir,
        api_latency_s=measure_api_latency(detections),
        cold_start_s=args.cold_start,
        burned_area=burned,
    )

    written = artifacts(results)
    for path, text in written.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    print(f"validation experiments ({source})")
    print(f"  params_hash : {results['params_hash']}")
    for experiment in results["experiments"]:
        print(f"  {experiment['id']}: {experiment['verdict']}")
    print(f"  report      : {REPORT_PATH.relative_to(REPO_ROOT)}")
    print(f"  results     : {(RESULTS_DIR / 'results.json').relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
