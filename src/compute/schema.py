"""Normalize MODIS and VIIRS detections to one schema.

FIRMS publishes the two sensors with different confidence conventions:
MODIS reports 0-100, VIIRS reports ``l`` / ``n`` / ``h``. This module maps
both onto a single numeric column so the rest of ``src/compute`` can apply
one confidence filter.

Deterministic and network-free. No LLM. Nothing here computes for the UI;
it is the shared input contract for the harmonization and validation steps.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping

import pandas as pd

logger = logging.getLogger(__name__)

MODIS = "MODIS"
VIIRS = "VIIRS"

#: VIIRS confidence classes -> numeric, per docs/METHODS.md. Single source of
#: truth: the same mapping is reported in the methods payload for the UI.
VIIRS_CONFIDENCE_MAP: dict[str, float] = {
    "l": 25.0,
    "low": 25.0,
    "n": 60.0,
    "nominal": 60.0,
    "h": 90.0,
    "high": 90.0,
}

#: Detections below this numeric confidence are dropped (both sensors).
MIN_CONFIDENCE = 50.0

#: Columns the raw detections must carry, after lower-casing.
REQUIRED_COLUMNS = ("latitude", "longitude", "acq_date", "confidence")

#: Columns ``normalize`` guarantees on its output.
CANONICAL_COLUMNS = (
    "latitude",
    "longitude",
    "acq_date",
    "confidence_num",
    "sensor_family",
)

_FAMILY_HINTS = (("MODIS", MODIS), ("VIIRS", VIIRS))


def _as_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    return out


def infer_family(*candidates: object) -> str | None:
    """Infer MODIS vs VIIRS from any of instrument, satellite or product id."""
    for candidate in candidates:
        if candidate is None:
            continue
        text = str(candidate).upper()
        if not text or text == "NAN":
            continue
        for needle, family in _FAMILY_HINTS:
            if needle in text:
                return family
    return None


def normalize(
    df: pd.DataFrame,
    *,
    default_family: str | None = None,
    min_confidence: float | None = None,
) -> pd.DataFrame:
    """Return detections on the canonical schema.

    Adds ``confidence_num`` (numeric, after the VIIRS mapping) and
    ``sensor_family``. Coerces ``acq_date`` to midnight timestamps and the
    coordinates to floats. An empty input returns an empty canonical frame,
    so a day with no fire is not an error. A non-empty input missing a
    required column raises ``ValueError`` rather than silently dropping data.

    ``min_confidence`` only *reports* how many rows fall below the cut; the
    filter itself is applied by :func:`src.compute.harmonize.harmonize`.
    """
    frame = _as_frame(df)
    if frame.empty:
        return pd.DataFrame(columns=[*CANONICAL_COLUMNS])

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(
            f"detections are missing required columns {missing}; "
            f"got {sorted(frame.columns)}"
        )

    frame["latitude"] = pd.to_numeric(frame["latitude"], errors="coerce")
    frame["longitude"] = pd.to_numeric(frame["longitude"], errors="coerce")
    frame["acq_date"] = pd.to_datetime(frame["acq_date"], errors="coerce").dt.normalize()

    family = _family_column(frame, default_family)
    frame["sensor_family"] = family
    frame["confidence_num"] = confidence_to_numeric(frame["confidence"], family)

    dropped = int(frame["acq_date"].isna().sum() + frame["latitude"].isna().sum())
    if dropped:
        logger.warning("dropping %d detection(s) with an unparseable date or coordinate", dropped)
        frame = frame.dropna(subset=["latitude", "longitude", "acq_date"]).copy()
    frame = frame.dropna(subset=["confidence_num"]).copy()

    if min_confidence is not None:
        below = int((frame["confidence_num"] < min_confidence).sum())
        if below:
            logger.info("%d detection(s) below the confidence cut", below)
    return frame


def _family_column(frame: pd.DataFrame, default_family: str | None) -> pd.Series:
    """Resolve a MODIS/VIIRS family per row, warning on anything unknown."""
    if "sensor_family" in frame.columns:
        resolved = frame["sensor_family"].map(lambda v: infer_family(v))
    else:
        columns = [c for c in ("instrument", "satellite", "source_product") if c in frame.columns]
        resolved = pd.Series([None] * len(frame), index=frame.index, dtype=object)
        if columns:
            resolved = frame[columns].apply(
                lambda row: infer_family(*row.tolist()), axis=1
            )
    unknown = resolved.isna()
    if bool(unknown.any()):
        if default_family is not None:
            resolved = resolved.fillna(default_family)
        else:
            logger.warning(
                "%d detection(s) have an unrecognised sensor; tagging them UNKNOWN",
                int(unknown.sum()),
            )
            resolved = resolved.fillna("UNKNOWN")
    return resolved.astype(str)


def confidence_to_numeric(values: pd.Series, families: pd.Series) -> pd.Series:
    """Map confidence to a number, per row, using the row's sensor family.

    MODIS values are already numeric. VIIRS values are letters (or words)
    mapped through :data:`VIIRS_CONFIDENCE_MAP`. An unmapped VIIRS class is
    logged and yields ``NaN`` so it is dropped by the filter rather than
    silently counted.
    """

    def convert(value: object, family: object) -> float:
        if value is None or pd.isna(value):
            return float("nan")
        text = str(value).strip().lower()
        if str(family).upper() == VIIRS:
            if text in VIIRS_CONFIDENCE_MAP:
                return VIIRS_CONFIDENCE_MAP[text]
            numeric = pd.to_numeric(text, errors="coerce")
            if pd.notna(numeric):  # already numeric after all
                return float(numeric)
            logger.warning("unmapped VIIRS confidence class %r; dropping", value)
            return float("nan")
        numeric = pd.to_numeric(text, errors="coerce")
        return float(numeric) if pd.notna(numeric) else float("nan")

    return pd.Series(
        [convert(v, f) for v, f in zip(values.tolist(), families.tolist(), strict=True)],
        index=values.index,
        dtype="float64",
    )


def confidence_mapping() -> Mapping[str, float]:
    """The VIIRS ``l``/``n``/``h`` mapping the methods panel reports."""
    return {"l": VIIRS_CONFIDENCE_MAP["l"], "n": VIIRS_CONFIDENCE_MAP["n"], "h": VIIRS_CONFIDENCE_MAP["h"]}


__all__: Iterable[str] = (
    "CANONICAL_COLUMNS",
    "MIN_CONFIDENCE",
    "MODIS",
    "REQUIRED_COLUMNS",
    "VIIRS",
    "VIIRS_CONFIDENCE_MAP",
    "confidence_mapping",
    "confidence_to_numeric",
    "infer_family",
    "normalize",
)
