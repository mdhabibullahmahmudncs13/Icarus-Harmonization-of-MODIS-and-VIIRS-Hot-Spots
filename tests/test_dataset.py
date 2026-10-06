"""Tests for the DuckDB data tier in ``src/api/dataset.py``.

The tier must read the cache and the fixture through DuckDB, union a multi-file
cache glob, and keep every value a direct pandas read would have produced. The
resolution order and the truthful ``source`` are covered in ``tests/test_api.py``;
these tests pin the reader itself.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.acquire import safe
from src.api import dataset as dataset_module
from src.demo import demo_detections

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "demo_fixtures" / "detections.parquet"


def test_read_parquet_matches_a_direct_pandas_read():
    """Reading through DuckDB must not change the frame the science sees."""
    through_duckdb = dataset_module.read_parquet(str(FIXTURE_PATH))
    through_pandas = pd.read_parquet(FIXTURE_PATH)
    assert list(through_duckdb.columns) == list(through_pandas.columns)
    assert through_duckdb.equals(through_pandas)


def test_read_parquet_unifies_a_multi_file_glob(tmp_path: Path):
    """DuckDB unions the files by column name in one query, not a manual concat."""
    frame = demo_detections(days=60)
    raw = tmp_path / "raw"
    raw.mkdir(parents=True)
    split = len(frame) // 2
    frame.iloc[:split].to_parquet(raw / "a.parquet", index=False)
    frame.iloc[split:].to_parquet(raw / "b.parquet", index=False)

    combined = dataset_module.read_parquet(str(raw / "*.parquet"))
    assert len(combined) == len(frame)
    assert set(combined.columns) == set(frame.columns)


def test_read_parquet_unions_products_that_do_not_share_a_csv_shape(tmp_path: Path):
    """MODIS reports ``brightness`` where VIIRS reports ``bright_ti4``.

    The real cache glob holds both products, and DuckDB's default by-position
    read fails the whole dataset with a schema mismatch the moment a second
    product lands under ``cache/raw/`` — the API then 500s on every route.
    ``union_by_name`` keeps each product's own columns and nulls the other.
    """
    frame = demo_detections(days=60)
    raw = tmp_path / "raw"
    raw.mkdir(parents=True)
    frame.assign(brightness=349.9).to_parquet(raw / "MODIS_SP.parquet", index=False)
    frame.assign(bright_ti4=320.5).to_parquet(raw / "VIIRS_SNPP_SP.parquet", index=False)

    combined = dataset_module.read_parquet(str(raw / "*.parquet"))
    assert len(combined) == 2 * len(frame)
    assert {"brightness", "bright_ti4"} <= set(combined.columns)
    assert combined["brightness"].isna().sum() == len(frame)
    assert combined["bright_ti4"].isna().sum() == len(frame)


def test_the_fixture_is_read_through_duckdb_not_pandas(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """If pandas' reader were still in the path, this test would fail loudly."""

    def blocked(*_args, **_kwargs):
        raise AssertionError("the data tier used pandas.read_parquet, not DuckDB")

    monkeypatch.setenv("OFFLINE", "1")
    monkeypatch.setattr(safe, "CACHE_DIR", tmp_path / "empty")
    monkeypatch.setattr(safe, "FIXTURE_DIR", REPO_ROOT / "demo_fixtures")
    monkeypatch.setattr(dataset_module.pd, "read_parquet", blocked)
    dataset_module.reset_dataset_cache()
    try:
        loaded = dataset_module.load_dataset()
    finally:
        dataset_module.reset_dataset_cache()
    assert loaded.source == "fixture"
    assert not loaded.detections.empty


def test_the_cache_is_read_through_duckdb_over_the_whole_glob(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """A two-file cache is served as one dataset, still labelled ``cache``."""
    frame = demo_detections(days=90)
    raw = tmp_path / "raw"
    raw.mkdir(parents=True)
    split = len(frame) // 3
    chunks = (frame.iloc[:split], frame.iloc[split : 2 * split], frame.iloc[2 * split :])
    for index, chunk in enumerate(chunks):
        chunk.to_parquet(raw / f"chunk{index}.parquet", index=False)

    def blocked(*_args, **_kwargs):
        raise AssertionError("the data tier used pandas.read_parquet, not DuckDB")

    monkeypatch.delenv("OFFLINE", raising=False)
    monkeypatch.setattr(safe, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(safe, "FIXTURE_DIR", tmp_path / "empty")
    monkeypatch.setattr(dataset_module.pd, "read_parquet", blocked)
    dataset_module.reset_dataset_cache()
    try:
        loaded = dataset_module.load_dataset()
    finally:
        dataset_module.reset_dataset_cache()
    assert loaded.source == "cache"
    assert "3 file(s)" in loaded.path
