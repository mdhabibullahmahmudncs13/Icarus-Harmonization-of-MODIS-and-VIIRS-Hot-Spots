"""Pre-registered validation experiments (E1-E9) — ``docs/TESTING.md`` §9.

Deterministic, network-free, no LLM. The experiments read the same canonical
detections the API serves and return plain dictionaries so the results can be
written to ``validation/results.json`` and ``docs/VALIDATION.md``.
"""

from __future__ import annotations

from .experiments import (
    Experiment,
    run_all,
)

__all__ = ["Experiment", "run_all"]
