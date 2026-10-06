"""S7 availability and per-bin coverage (docs/TRD.md §5.5, DATA_DICTIONARY.md §5).

Coverage answers "was a stream watching?", which is what stops the calendar
colouring an unobserved bin as zero activity. It is computed from the stream
availability calendar in :mod:`src.compute.availability` (product epochs minus
the outage table), not from whether a fire happened:

    cov_s(y, b) = expected_days(s) inside the bin / days of the bin in the record

The denominator is the bin's days that fall inside the requested record window,
so a bin clipped at the edge of the record is not punished for the days before
the window. ``n_days`` (the bin's full calendar length, 8 or 5/6) is reported
alongside.

Source tagging (docs/DATA_DICTIONARY.md §5)
-------------------------------------------

* ``MODIS``     — both MODIS satellites available (``both_frac >= cov_min``).
* ``BRIDGE``    — a single MODIS satellite available with adequate coverage.
* ``VIIRS_CAL`` — MODIS below ``cov_min`` but VIIRS meets it.
* ``NONE``      — no stream meets ``cov_min``; the bin carries no observation.

Deterministic, network-free, no LLM.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

import pandas as pd

from .availability import STREAM_FAMILY
from .series_util import BIN_DAYS, bin_of_doy

#: Minimum coverage fraction for a stream to anchor a bin (docs/PARAMETERS.md).
COV_MIN = 0.75

#: The full source vocabulary the contract allows.
SOURCES: tuple[str, ...] = ("MODIS", "BRIDGE", "VIIRS_CAL", "NONE")

MODIS_SOURCE = "MODIS"
BRIDGE_SOURCE = "BRIDGE"
VIIRS_SOURCE = "VIIRS_CAL"
NONE_SOURCE = "NONE"

#: Columns ``bin_coverage`` guarantees, in order.
COVERAGE_COLUMNS: tuple[str, ...] = (
    "year",
    "bin",
    "n_days",
    "window_days",
    "mod_t_days",
    "mod_a_days",
    "both_days",
    "both_frac",
    "cov_mod_t",
    "cov_mod_a",
    "cov_modis",
    "cov_viirs",
    "coverage",
    "source",
)

#: Floats are rounded to this many decimals so payloads and goldens are
#: byte-stable across platforms without hiding a real change in the science.
ROUND_DP = 4


def days_in_bin(year: int, bin_number: int, bin_days: int = BIN_DAYS) -> int:
    """Calendar days in ``(year, bin_number)``: 8, or 5/6 for the last bin."""
    if bin_number < 1:
        raise ValueError(f"bin_number must be >= 1, got {bin_number}")
    year_length = 366 if calendar.isleap(year) else 365
    start_doy = (bin_number - 1) * bin_days + 1
    end_doy = min(bin_number * bin_days, year_length)
    return max(0, end_doy - start_doy + 1)


def _stream_flags(day: date, availability: Mapping[str, set[date]]) -> tuple[bool, bool, bool]:
    """``(mod_t, mod_a, viirs_any)`` availability for one day."""
    mod_t = "MOD_T" in availability and day in availability["MOD_T"]
    mod_a = "MOD_A" in availability and day in availability["MOD_A"]
    viirs = any(
        day in days
        for stream, days in availability.items()
        if STREAM_FAMILY.get(stream) == "VIIRS"
    )
    return mod_t, mod_a, viirs


def source_for(
    *,
    both_frac: float,
    cov_mod_t: float,
    cov_mod_a: float,
    cov_viirs: float,
    cov_min: float = COV_MIN,
) -> str:
    """Tag a bin from the documented coverage rule."""
    if both_frac >= cov_min:
        return MODIS_SOURCE
    if max(cov_mod_t, cov_mod_a) >= cov_min:
        return BRIDGE_SOURCE
    if cov_viirs >= cov_min:
        return VIIRS_SOURCE
    return NONE_SOURCE


def coverage_for(
    source: str,
    *,
    both_frac: float,
    cov_mod_t: float,
    cov_mod_a: float,
    cov_viirs: float,
) -> float:
    """The coverage that goes on the payload: the anchoring stream's fraction.

    ``NONE`` falls back to the best MODIS coverage either way, which is by
    definition below ``cov_min``.
    """
    if source == MODIS_SOURCE:
        return both_frac
    if source == BRIDGE_SOURCE:
        return max(cov_mod_t, cov_mod_a)
    if source == VIIRS_SOURCE:
        return cov_viirs
    return max(cov_mod_t, cov_mod_a, cov_viirs)


def bin_coverage(
    availability: Mapping[str, set[date]],
    *,
    start: date,
    end: date,
    bin_days: int = BIN_DAYS,
    cov_min: float = COV_MIN,
) -> pd.DataFrame:
    """One row per ``(year, bin)`` in ``start..end`` inclusive.

    Columns are :data:`COVERAGE_COLUMNS`. A bin whose every stream is
    unavailable is still emitted, tagged ``NONE`` with zero coverage, so the
    caller can hatch it rather than drop it.
    """
    if end < start:
        return pd.DataFrame(columns=[*COVERAGE_COLUMNS])

    buckets: dict[tuple[int, int], dict[str, int]] = {}
    cursor = start
    while cursor <= end:
        year = cursor.year
        bin_number = bin_of_doy(cursor.timetuple().tm_yday, bin_days)
        entry = buckets.setdefault(
            (year, bin_number),
            {"window_days": 0, "mod_t": 0, "mod_a": 0, "both": 0, "modis": 0, "viirs": 0},
        )
        mod_t, mod_a, viirs = _stream_flags(cursor, availability)
        entry["window_days"] += 1
        entry["mod_t"] += int(mod_t)
        entry["mod_a"] += int(mod_a)
        entry["both"] += int(mod_t and mod_a)
        entry["modis"] += int(mod_t or mod_a)
        entry["viirs"] += int(viirs)
        cursor += timedelta(days=1)

    records: list[dict[str, Any]] = []
    for (year, bin_number), entry in sorted(buckets.items()):
        window = entry["window_days"]
        div = window if window else 1
        cov_mod_t = round(entry["mod_t"] / div, ROUND_DP)
        cov_mod_a = round(entry["mod_a"] / div, ROUND_DP)
        both_frac = round(entry["both"] / div, ROUND_DP)
        cov_modis = round(entry["modis"] / div, ROUND_DP)
        cov_viirs = round(entry["viirs"] / div, ROUND_DP)
        source = source_for(
            both_frac=both_frac,
            cov_mod_t=cov_mod_t,
            cov_mod_a=cov_mod_a,
            cov_viirs=cov_viirs,
            cov_min=cov_min,
        )
        records.append(
            {
                "year": year,
                "bin": bin_number,
                "n_days": days_in_bin(year, bin_number, bin_days),
                "window_days": window,
                "mod_t_days": entry["mod_t"],
                "mod_a_days": entry["mod_a"],
                "both_days": entry["both"],
                "both_frac": both_frac,
                "cov_mod_t": cov_mod_t,
                "cov_mod_a": cov_mod_a,
                "cov_modis": cov_modis,
                "cov_viirs": cov_viirs,
                "coverage": round(
                    coverage_for(
                        source,
                        both_frac=both_frac,
                        cov_mod_t=cov_mod_t,
                        cov_mod_a=cov_mod_a,
                        cov_viirs=cov_viirs,
                    ),
                    ROUND_DP,
                ),
                "source": source,
            }
        )
    return pd.DataFrame.from_records(records, columns=[*COVERAGE_COLUMNS])


def coverage_index(
    availability: Mapping[str, set[date]],
    *,
    start: date,
    end: date,
    bin_days: int = BIN_DAYS,
    cov_min: float = COV_MIN,
) -> dict[tuple[int, int], tuple[float, str]]:
    """Map ``(year, bin)`` -> ``(coverage, source)`` for a date lookup."""
    table = bin_coverage(availability, start=start, end=end, bin_days=bin_days, cov_min=cov_min)
    return {
        (int(row.year), int(row.bin)): (float(row.coverage), str(row.source))
        for row in table.itertuples()
    }


def coverage_for_date(
    index: Mapping[tuple[int, int], tuple[float, str]],
    date: object,
    bin_days: int = BIN_DAYS,
) -> tuple[float, str]:
    """Coverage and source for the bin containing ``date``.

    A date outside the indexed window is uncovered: ``0.0`` and ``NONE``.
    """
    stamp = pd.Timestamp(date)
    key = (int(stamp.year), bin_of_doy(int(stamp.dayofyear), bin_days))
    return index.get(key, (0.0, NONE_SOURCE))


__all__: Iterable[str] = (
    "BRIDGE_SOURCE",
    "COVERAGE_COLUMNS",
    "COV_MIN",
    "MODIS_SOURCE",
    "NONE_SOURCE",
    "ROUND_DP",
    "SOURCES",
    "VIIRS_SOURCE",
    "bin_coverage",
    "coverage_for",
    "coverage_for_date",
    "coverage_index",
    "days_in_bin",
    "source_for",
)
