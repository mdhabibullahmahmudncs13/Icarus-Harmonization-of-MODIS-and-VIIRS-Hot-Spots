"""Tests for the S7 availability calendar (``src/compute/availability.py``).

Availability is a property of the acquisition schedule — product epochs minus
the outage table — and it is what makes BRIDGE reachable and NONE visible. These
tests pin the epoch/outage edges and keep the stream-to-product map in step with
the payload builders.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.compute import availability, export


def test_stream_product_map_matches_the_payload_builders():
    """One stream table: this module's map must equal export.PRODUCT_STREAMS."""
    derived = {
        stream: product
        for product, streams in export.PRODUCT_STREAMS.items()
        for stream in streams
    }
    assert derived == availability.STREAM_PRODUCT


def test_expected_days_honours_the_stream_epoch():
    # VIIRS SNPP starts 2012-01-01; a 2011 window has no expected days.
    assert availability.expected_days("VIIRS_SNPP", date(2011, 1, 1), date(2011, 12, 31)) == set()
    days = availability.expected_days("VIIRS_SNPP", date(2012, 1, 1), date(2012, 1, 3))
    assert days == {date(2012, 1, 1), date(2012, 1, 2), date(2012, 1, 3)}


def test_expected_days_subtracts_the_outage_table():
    days = availability.expected_days("MOD_A", date(2019, 3, 1), date(2019, 3, 3))
    assert days == set(), "the demo Aqua outage covers 1-16 March 2019"


def test_an_all_outage_silences_every_stream():
    days = availability.expected_days("MOD_T", date(2019, 8, 1), date(2019, 8, 5))
    assert days == set()


def test_a_single_modis_outage_leaves_the_other_up():
    """The March outage is Aqua-only, so Terra still has full coverage."""
    days = availability.expected_days("MOD_T", date(2019, 3, 1), date(2019, 3, 3))
    assert days == {date(2019, 3, 1), date(2019, 3, 2), date(2019, 3, 3)}


def test_unknown_stream_is_rejected():
    with pytest.raises(ValueError):
        availability.expected_days("NOPE", date(2020, 1, 1), date(2020, 1, 2))


def test_families_available_rolls_streams_up():
    table = {
        "MOD_T": {date(2019, 1, 1)},
        "MOD_A": set(),
        "VIIRS_SNPP": {date(2019, 1, 1)},
    }
    assert availability.families_available(table) == {date(2019, 1, 1): {"MODIS", "VIIRS"}}
