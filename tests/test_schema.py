"""Tests for src/compute/schema.py.

The confidence mapping is the one place a wrong constant silently changes
every count, so it is tested directly rather than only through harmonize().
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.compute.schema import (
    CANONICAL_COLUMNS,
    MIN_CONFIDENCE,
    MODIS,
    VIIRS,
    confidence_mapping,
    confidence_to_numeric,
    infer_family,
    normalize,
)


def test_infer_family_from_instrument_satellite_or_product():
    assert infer_family("MODIS") == MODIS
    assert infer_family("VIIRS") == VIIRS
    assert infer_family("NP", "VIIRS_SNPP_SP") == VIIRS
    assert infer_family(None, "MODIS_SP") == MODIS
    assert infer_family("unknown-sensor") is None


def test_default_confidence_cut_is_fifty():
    assert MIN_CONFIDENCE == 50.0
    assert confidence_mapping() == {"l": 25.0, "n": 60.0, "h": 90.0}


def test_viirs_letters_map_to_numbers_and_modis_passes_through():
    families = pd.Series([VIIRS, VIIRS, VIIRS, MODIS])
    values = pd.Series(["l", "n", "h", "77"])
    mapped = confidence_to_numeric(values, families)
    assert mapped.tolist() == [25.0, 60.0, 90.0, 77.0]


def test_unmapped_viirs_class_is_dropped_not_guessed(caplog):
    families = pd.Series([VIIRS])
    mapped = confidence_to_numeric(pd.Series(["maybe"]), families)
    assert mapped.isna().all()
    assert "unmapped VIIRS confidence class" in caplog.text


def test_normalize_produces_the_canonical_columns():
    frame = pd.DataFrame(
        {
            "latitude": ["23.1"],
            "longitude": ["90.1"],
            "acq_date": ["2015-01-01"],
            "confidence": ["n"],
            "instrument": ["VIIRS"],
        }
    )
    result = normalize(frame)
    assert list(result.columns)[:2] == list(CANONICAL_COLUMNS)[:2]
    assert set(CANONICAL_COLUMNS).issubset(result.columns)
    assert result["sensor_family"].iloc[0] == VIIRS
    assert result["confidence_num"].iloc[0] == 60.0
    assert str(result["acq_date"].dtype).startswith("datetime64")


def test_normalize_empty_input_is_empty_not_an_error():
    result = normalize(pd.DataFrame())
    assert result.empty
    assert list(result.columns) == list(CANONICAL_COLUMNS)


def test_normalize_raises_on_missing_required_columns():
    with pytest.raises(ValueError, match="missing required columns"):
        normalize(pd.DataFrame({"latitude": [1.0], "longitude": [2.0]}))


def test_normalize_accepts_an_uppercase_and_padded_header():
    frame = pd.DataFrame(
        {
            " Latitude ": [23.1],
            " Longitude ": [90.1],
            " Acq_Date ": ["2015-01-01"],
            " Confidence ": [80],
            " Instrument ": ["MODIS"],
        }
    )
    assert len(normalize(frame)) == 1
