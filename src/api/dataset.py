"""Resolve the detections the API serves — offline-first, cache before fixture.

The API never touches the network. It reads local parquet, harmonizes it with
:mod:`src.compute` and hands the result to the payload builders in
:mod:`src.compute.export`. Where the bytes came from is carried on every
response as ``meta.source``:

* ``"cache"`` — real detections written by ``make cache``
  (``cache/raw/*.parquet``).
* ``"fixture"`` — the committed offline demo fixture
  (``demo_fixtures/detections.parquet``), synthetic by design.

Resolution order, honouring ``OFFLINE=1`` (the plan: *OFFLINE forces
fixtures*, so ``make demo`` is deterministic even when a real cache exists):

* ``OFFLINE`` unset → cache, then fixture.
* ``OFFLINE=1`` → fixture, then cache.

A day with no detections is a count of zero, not a missing day, so the
harmonized series handed to the baseline and the anomaly is reindexed onto a
continuous daily range and zero-filled. That is why ``/api/anomaly`` can
answer for any date the fixture covers — a candidate table, not just a fire.
"""

from __future__ import annotations

import glob as globlib
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock

import pandas as pd

from src.acquire import safe
from src.compute import harmonize

#: Filename of the committed offline fixture, under ``demo_fixtures/``.
FIXTURE_NAME = "detections.parquet"


class NoDataError(RuntimeError):
    """No cache and no fixture was found, so there is nothing to serve."""


@dataclass(frozen=True)
class Dataset:
    """Harmonized detections plus everything the payload builders need."""

    #: Confidence-filtered, gridded detections (one row per detection).
    detections: pd.DataFrame
    #: Distinct cell-days per day, on a continuous zero-filled daily index.
    series: pd.Series
    #: ``"cache"`` or ``"fixture"`` — reported verbatim as ``meta.source``.
    source: str
    #: Timestamp stamped on every payload built from this dataset.
    generated_at: datetime
    #: The path the detections were read from, for logs and tests.
    path: str


def _read_cache() -> tuple[pd.DataFrame, str] | None:
    """Concatenate the raw parquet written by ``src/acquire/firms.py``."""
    pattern = str(safe.CACHE_DIR / "raw" / "*.parquet")
    files = sorted(globlib.glob(pattern))
    if not files:
        return None
    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    return frame, f"{len(files)} file(s) under {pattern}"


def _read_fixture() -> tuple[pd.DataFrame, str] | None:
    """Read the committed offline fixture, if it is present."""
    path = safe.FIXTURE_DIR / FIXTURE_NAME
    if not path.exists():
        return None
    return pd.read_parquet(path), str(path)


def _continuous(series: pd.Series) -> pd.Series:
    """Reindex a daily series onto every day between its ends, filling 0.

    ``harmonize.harmonized_series`` only has rows for days that saw a
    detection. A day that saw none is a real zero, so the baseline and the
    anomaly should see it as one.
    """
    if series.empty:
        return series
    index = pd.date_range(series.index.min(), series.index.max(), freq="D")
    index.name = "date"
    return series.reindex(index, fill_value=0)


def load_dataset(*, offline: bool | None = None) -> Dataset:
    """Read, harmonize and package the dataset to serve.

    Raises :class:`NoDataError` when neither the cache nor the fixture
    exists, so the API can answer with a clear 503 instead of a stack trace.
    """
    if offline is None:
        offline = safe.is_offline()

    order = (_read_fixture, _read_cache) if offline else (_read_cache, _read_fixture)
    for reader in order:
        found = reader()
        if found is None:
            continue
        raw, path = found
        detections = harmonize.harmonize(raw)
        if detections.empty:
            raise NoDataError(f"{path} contained no detections above the confidence cut")
        source = "fixture" if reader is _read_fixture else "cache"
        return Dataset(
            detections=detections,
            series=_continuous(harmonize.harmonized_series(detections)),
            source=source,
            generated_at=datetime.now(UTC),
            path=path,
        )

    raise NoDataError(
        "no detections to serve: ran `make cache`? otherwise run "
        "`python -m src.demo` to write demo_fixtures/detections.parquet"
    )


# --------------------------------------------------------------------------
# Process-wide cache: uvicorn serves many requests from one dataset
# --------------------------------------------------------------------------

_lock = Lock()
_dataset: Dataset | None = None


def get_dataset() -> Dataset:
    """Return the process-wide dataset, loading it on first use."""
    global _dataset
    with _lock:
        if _dataset is None:
            _dataset = load_dataset()
        return _dataset


def reset_dataset_cache() -> None:
    """Drop the cached dataset so the next request reloads it (tests)."""
    global _dataset
    with _lock:
        _dataset = None


__all__ = [
    "FIXTURE_NAME",
    "Dataset",
    "NoDataError",
    "get_dataset",
    "load_dataset",
    "reset_dataset_cache",
]
