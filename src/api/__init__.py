"""FastAPI application exposing harmonized fire data — offline-first.

Track B contract server: the seven ``/api/v1`` endpoints, all carrying the shared
``meta`` block, backed only by local parquet and the committed offline fixture.
Network access is not part of the contract and is never attempted.
"""

from __future__ import annotations

__all__ = ["Dataset", "get_dataset", "load_dataset"]

# Re-exports the public surface of this package.
from .dataset import Dataset, NoDataError, get_dataset, load_dataset  # noqa: F401
