"""Tests for src/compute/harmonize.py.

All stub functions are expected to raise ``NotImplementedError``. They
are marked ``xfail`` so the suite records them as pending rather than
failing, while still executing them.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src import compute  # noqa: F401  - import sanity check
from src.compute import harmonize


@pytest.fixture
def empty_df() -> pd.DataFrame:
    """An empty detection table; the stubs don't look at the contents."""
    return pd.DataFrame()


@pytest.mark.xfail(raises=NotImplementedError, reason="stub")
def test_to_grid(harmonize_module):
    _ = harmonize_module


def test_to_grid_call_raises(empty_df):
    with pytest.raises(NotImplementedError):
        harmonize.to_grid(empty_df)


@pytest.mark.xfail(raises=NotImplementedError, reason="stub")
def test_to_grid_signature():
    """Signature-only check: cell_km must default to 5.5."""
    import inspect

    sig = inspect.signature(harmonize.to_grid)
    assert sig.parameters["cell_km"].default == 5.5


@pytest.mark.xfail(raises=NotImplementedError, reason="stub")
def test_harmonize(empty_df):
    with pytest.raises(NotImplementedError):
        harmonize.harmonize(empty_df)


@pytest.mark.xfail(raises=NotImplementedError, reason="stub")
def test_raw_series(empty_df):
    with pytest.raises(NotImplementedError):
        harmonize.raw_series(empty_df)


@pytest.mark.xfail(raises=NotImplementedError, reason="stub")
def test_harmonized_series(empty_df):
    with pytest.raises(NotImplementedError):
        harmonize.harmonized_series(empty_df)


@pytest.mark.xfail(raises=NotImplementedError, reason="stub")
def test_seasonal_baseline():
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    series = pd.Series([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], index=idx)
    with pytest.raises(NotImplementedError):
        harmonize.seasonal_baseline(series)


@pytest.mark.xfail(raises=NotImplementedError, reason="stub")
def test_anomaly_score():
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    series = pd.Series([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], index=idx)
    baseline = pd.Series([0, 1, 1, 1, 1, 1, 1, 1, 1, 1], index=idx)
    with pytest.raises(NotImplementedError):
        harmonize.anomaly_score(series, baseline, pd.Timestamp("2020-01-05"))


@pytest.mark.xfail(raises=NotImplementedError, reason="stub")
def test_overlap_correlation():
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    modis = pd.Series(range(10), index=idx)
    viirs = pd.Series(range(10), index=idx)
    with pytest.raises(NotImplementedError):
        harmonize.overlap_correlation(modis, viirs)


@pytest.fixture
def harmonize_module():
    """Convenience fixture that returns the module under test."""
    return harmonize