"""S7 availability and coverage (docs/TRD.md §5.5, docs/DATA_DICTIONARY.md §5).

Coverage answers "was a sensor watching?", not "was there a fire?". The frontend
must never colour an unobserved bin as zero activity, so every harmonized bin
carries two extra facts: how much of it the reference family saw, and which
sensor stream the value is anchored on.

Coverage definition, against the schema this pipeline actually reads
---------------------------------------------------------------

The spec's formula is ``cov_s(y, b) = (1 / n_days) * sum_d a(s, d)`` where
``a(s, d)`` is 1 on a day stream ``s`` was *available*. Availability is an
acquisition fact (the satellite downlinked that day), carried by an ``avail`` /
outage table that this pipeline does not yet ingest. What the detections do
carry is which days a stream actually *reported*, so coverage here is computed
over the bin's **observing days** — the days the bin had any detection at all:

    cov_f(y, b) = reported_days(f, b) / observed_days(b)

where ``observed_days(b)`` counts days in the bin with any family present. A
winter bin with two days of fire and MODIS on both is fully covered (1.0), not
"two eighths"; a bin where VIIRS saw fire on days MODIS did not is genuinely
under-covered by MODIS. ``n_days`` (the calendar length of the bin) is still
reported, for the AUC and for the tests, but it is not the denominator.

Source tagging (docs/DATA_DICTIONARY.md §5)
-------------------------------------------

* ``MODIS``     — MODIS family coverage meets ``cov_min``; the reference family.
* ``VIIRS_CAL`` — MODIS does not meet ``cov_min`` but VIIRS does.
* ``NONE``      — no family meets ``cov_min``; the value must not be read as an
  observed zero.
* ``BRIDGE``    — reserved. A bridge factor needs a *single* MODIS satellite
  distinguished from the pair, and the acquisition table exposes MODIS only as
  the combined ``Terra+Aqua`` product, so this pipeline cannot honestly emit it
  yet. The enum keeps the word so the contract does not change when it can.

Deterministic and network-free. No LLM.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable
from typing import Any

import pandas as pd

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
    "observed_days",
    "modis_days",
    "viirs_days",
    "cov_modis",
    "cov_viirs",
    "coverage",
    "source",
)

#: Floats are rounded to this many decimals so the payload and the goldens are
#: byte-stable across platforms without hiding a real change in the science.
ROUND_DP = 4


def _timestamps(detections: pd.DataFrame) -> pd.Series:
    if "acq_date" not in detections.columns:
        raise ValueError("detections are missing the required column 'acq_date'")
    return pd.to_datetime(detections["acq_date"], errors="coerce").dt.normalize()


def family_availability(detections: pd.DataFrame) -> pd.DataFrame:
    """Per-day family availability: one boolean column per family.

    Indexed by date, one row per day the detections cover (a day with no
    detection contributes no row). ``modis`` is 1 on a day with at least one
    MODIS detection, ``viirs`` likewise for VIIRS.
    """
    if detections.empty:
        return pd.DataFrame(columns=["modis", "viirs"], dtype=bool)
    if "sensor_family" not in detections.columns:
        raise ValueError("detections are missing the required column 'sensor_family'")
    frame = detections[["sensor_family"]].copy()
    frame["date"] = _timestamps(detections)
    frame = frame.dropna(subset=["date"])
    frame["family"] = frame["sensor_family"].astype(str).str.upper()
    if frame.empty:
        return pd.DataFrame(columns=["modis", "viirs"], dtype=bool)

    pivot = (
        frame.assign(present=1)
        .pivot_table(
            index="date", columns="family", values="present", aggfunc="max", fill_value=0
        )
    )
    out = pd.DataFrame(index=pivot.index)
    zero = pd.Series(0, index=pivot.index, dtype="int64")
    out["modis"] = (pivot["MODIS"] if "MODIS" in pivot.columns else zero).astype(bool)
    out["viirs"] = (pivot["VIIRS"] if "VIIRS" in pivot.columns else zero).astype(bool)
    out.index.name = "date"
    return out


def days_in_bin(year: int, bin_number: int, bin_days: int = BIN_DAYS) -> int:
    """Calendar days in ``(year, bin_number)``: 8, or 5/6 for the last bin."""
    if bin_number < 1:
        raise ValueError(f"bin_number must be >= 1, got {bin_number}")
    year_length = 366 if calendar.isleap(year) else 365
    start_doy = (bin_number - 1) * bin_days + 1
    end_doy = min(bin_number * bin_days, year_length)
    return max(0, end_doy - start_doy + 1)


def source_for(cov_modis: float, cov_viirs: float, cov_min: float = COV_MIN) -> str:
    """Tag a bin: MODIS, else VIIRS_CAL, else NONE (BRIDGE is not reachable)."""
    if cov_modis >= cov_min:
        return MODIS_SOURCE
    if cov_viirs >= cov_min:
        return VIIRS_SOURCE
    return NONE_SOURCE


def coverage_for(cov_modis: float, cov_viirs: float, cov_min: float = COV_MIN) -> float:
    """The coverage that goes on the payload: the anchoring stream's fraction.

    Under ``NONE`` the value is the best coverage either family reached, which
    is by definition below ``cov_min``.
    """
    source = source_for(cov_modis, cov_viirs, cov_min)
    if source == MODIS_SOURCE:
        return cov_modis
    if source == VIIRS_SOURCE:
        return cov_viirs
    return max(cov_modis, cov_viirs)


def bin_coverage(
    detections: pd.DataFrame,
    *,
    bin_days: int = BIN_DAYS,
    cov_min: float = COV_MIN,
) -> pd.DataFrame:
    """One row per ``(year, bin)`` present in ``detections``.

    Columns are :data:`COVERAGE_COLUMNS`. A bin that appears at all has at
    least one observing day by construction; ``cov_modis``/``cov_viirs`` are
    still guarded against a zero denominator.
    """
    availability = family_availability(detections)
    if availability.empty:
        return pd.DataFrame(columns=[*COVERAGE_COLUMNS])

    grouped: dict[tuple[int, int], dict[str, Any]] = {}
    for date, row in availability.iterrows():
        year = int(date.year)
        bin_number = bin_of_doy(int(date.dayofyear), bin_days)
        entry = grouped.setdefault(
            (year, bin_number),
            {
                "n_days": days_in_bin(year, bin_number, bin_days),
                "observed_days": 0,
                "modis_days": 0,
                "viirs_days": 0,
            },
        )
        entry["observed_days"] += 1
        entry["modis_days"] += int(bool(row["modis"]))
        entry["viirs_days"] += int(bool(row["viirs"]))

    records: list[dict[str, Any]] = []
    for (year, bin_number), entry in sorted(grouped.items()):
        observed = entry["observed_days"]
        cov_modis = round(entry["modis_days"] / observed, ROUND_DP) if observed else 0.0
        cov_viirs = round(entry["viirs_days"] / observed, ROUND_DP) if observed else 0.0
        records.append(
            {
                "year": year,
                "bin": bin_number,
                "n_days": entry["n_days"],
                "observed_days": observed,
                "modis_days": entry["modis_days"],
                "viirs_days": entry["viirs_days"],
                "cov_modis": cov_modis,
                "cov_viirs": cov_viirs,
                "coverage": round(coverage_for(cov_modis, cov_viirs, cov_min), ROUND_DP),
                "source": source_for(cov_modis, cov_viirs, cov_min),
            }
        )
    return pd.DataFrame.from_records(records, columns=[*COVERAGE_COLUMNS])


def coverage_index(
    detections: pd.DataFrame,
    *,
    bin_days: int = BIN_DAYS,
    cov_min: float = COV_MIN,
) -> dict[tuple[int, int], tuple[float, str]]:
    """Map ``(year, bin)`` -> ``(coverage, source)`` for a date lookup."""
    table = bin_coverage(detections, bin_days=bin_days, cov_min=cov_min)
    return {
        (int(row.year), int(row.bin)): (float(row.coverage), str(row.source))
        for row in table.itertuples()
    }


def coverage_for_date(
    index: dict[tuple[int, int], tuple[float, str]],
    date: object,
    bin_days: int = BIN_DAYS,
) -> tuple[float, str]:
    """Coverage and source for the bin containing ``date``.

    A date with no entry has no observing day, so it is uncovered: coverage
    ``0.0`` and source ``NONE``.
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
    "family_availability",
    "source_for",
)
