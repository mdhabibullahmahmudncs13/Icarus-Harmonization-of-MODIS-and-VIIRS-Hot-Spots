"""Small shared helpers for the compute package."""

from __future__ import annotations


def bin_of_doy(day_of_year: int, bin_days: int = 8) -> int:
    """MODIS 8-day convention: 46 bins per year, restarting 1 January."""
    return min((day_of_year - 1) // bin_days + 1, 46)

BIN_DAYS = 8
