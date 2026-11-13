"""Day-of-year helpers (docs/TRD.md §5)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import numpy as np


def doy(iso: str) -> int:
    """Day of year (1-366) for an ISO date string."""
    return date.fromisoformat(iso).timetuple().tm_yday


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile; 0.0 for an empty sequence.

    ``np.percentile``'s default interpolation is the same linear rule the
    project documented, and agrees with the hand-rolled version to ~1e-14.
    """
    if not values:
        return 0.0
    return float(np.percentile(np.asarray(values, dtype="float64"), q * 100))
