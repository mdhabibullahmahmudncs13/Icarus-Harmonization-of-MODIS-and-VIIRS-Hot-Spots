"""Synthetic detections for the compute tests.

The generator now lives in :mod:`src.demo`, because the same deterministic
data is also what the API serves as its offline fixture. This module keeps
the historical ``tests.synthetic`` import path working, so the tests and the
fixture cannot drift apart.

See :mod:`src.demo` for the shape and the reasons behind it. Synthetically
produced numbers are never evidence.
"""

from __future__ import annotations

from src.demo import GRID_COLS, GRID_ROWS, JITTER, identical_cell_days, synthetic_detections

__all__ = [
    "GRID_COLS",
    "GRID_ROWS",
    "JITTER",
    "identical_cell_days",
    "synthetic_detections",
]
