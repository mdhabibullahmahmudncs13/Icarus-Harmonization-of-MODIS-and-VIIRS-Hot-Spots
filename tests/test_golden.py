"""Golden-file tests for the Phase 2 compute core (docs/IMPLEMENTATION_PLAN.md §4).

``tests/golden/`` holds the committed output of the deterministic pipeline over
two seeded, offline inputs. ``tools/gen_golden.py`` writes them; these tests
fail when the committed files drift from a fresh run, so a change in the
science surfaces as a failing test rather than a silently rewritten number.

The goldens are also asserted against the mechanism the project exists to
prove: raw counts step up ~3x at the sensor transition and harmonized counts do
not, and harmonized MODIS/VIIRS agreement beats raw agreement.

Synthetic data is never evidence. Every golden records what the core computes
over synthetic detections, not an observation.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from tools.gen_golden import GOLDEN_DIR, build, compare, render, step_detections

#: Every golden the generator writes, computed once for the whole module.
PAYLOADS: dict[str, Any] = build()


def _reject_constant(token: str) -> Any:
    raise ValueError(f"golden file carries the non-strict JSON token {token!r}")


def _headline() -> dict[str, Any]:
    return PAYLOADS["headline"]


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


# --- the fixtures themselves ----------------------------------------------


@pytest.mark.parametrize("name", sorted(PAYLOADS))
def test_every_golden_is_committed_and_matches_a_fresh_run(name: str) -> None:
    """The drift guard: a moved number in the science fails this test."""
    path = GOLDEN_DIR / f"{name}.json"
    assert path.is_file(), f"{name}.json is not committed; run `make golden`"
    assert path.read_text() == render(PAYLOADS[name]), f"{name}.json is stale; run `make golden`"


@pytest.mark.parametrize("name", sorted(PAYLOADS))
def test_goldens_are_strict_json(name: str) -> None:
    """No NaN/Infinity tokens, so any JSON consumer can read the file."""
    text = (GOLDEN_DIR / f"{name}.json").read_text()
    json.loads(text, parse_constant=_reject_constant)


def test_generator_check_reports_no_drift() -> None:
    assert compare(GOLDEN_DIR) == []


# --- the mechanism the project exists to prove ----------------------------


def test_step_scenario_input_is_pinned() -> None:
    """300 detections: 75 MODIS-only pre-transition, then 75 MODIS and 150 VIIRS."""
    dets = step_detections()
    assert len(dets) == 300
    pre = [d for d in dets if d.acq_date < "2012-01-20"]
    post = [d for d in dets if d.acq_date >= "2012-01-20"]
    assert len(pre) == 75
    assert len(post) == 225
    assert len([d for d in post if d.stream == "VIIRS_SNPP"]) == 150
    assert {d.stream for d in pre} == {"MOD_T"}, "no VIIRS stream exists before the transition"
    assert {d.stream for d in post} == {"MOD_T", "VIIRS_SNPP"}


def test_raw_series_steps_and_harmonized_series_does_not() -> None:
    headline = _headline()
    assert 2.5 <= headline["raw_step_ratio"] <= 3.5, headline["raw_step_ratio"]
    assert headline["harmonized_step_ratio"] <= 1.2, headline["harmonized_step_ratio"]

    series = PAYLOADS["step_series"]
    pre = [r for r in series if r["date"] < "2012-01-20"]
    post = [r for r in series if r["date"] >= "2012-01-20"]
    assert all(r["raw_viirs"] == 0 for r in pre), "VIIRS must be absent before the transition"
    assert all(r["raw_viirs"] > 0 for r in post)


def test_identical_overlap_collapses_the_three_x_inflation() -> None:
    identical = PAYLOADS["identical_overlap"]
    assert identical["raw"]["ratio"] == pytest.approx(3.0, rel=0.05)
    assert identical["harmonized"]["ratio"] == pytest.approx(1.0, rel=0.05)
    assert identical["raw"]["ratio"] > identical["harmonized"]["ratio"]


def test_noisy_overlap_harmonization_beats_raw() -> None:
    noisy = PAYLOADS["noisy_overlap"]
    assert noisy["raw"]["pearson"] > 0.5, "the sensors should still agree in direction"
    assert noisy["harmonized"]["pearson"] > noisy["raw"]["pearson"]
    assert noisy["harmonized"]["ratio"] < noisy["raw"]["ratio"]


def test_golden_headline_is_consistent_with_the_overlap_files() -> None:
    headline = _headline()
    assert headline["identical_overlap"]["raw_ratio"] == PAYLOADS["identical_overlap"]["raw"]["ratio"]
    assert (
        headline["identical_overlap"]["harmonized_ratio"]
        == PAYLOADS["identical_overlap"]["harmonized"]["ratio"]
    )
    assert headline["noisy_overlap"]["raw_pearson"] == PAYLOADS["noisy_overlap"]["raw"]["pearson"]


def test_step_critical_period_lands_in_june() -> None:
    """June is day-of-year 152-181, i.e. bins 19-23 of the 46 eight-day bins."""
    period = PAYLOADS["step_critical_period"]
    assert period["insufficient_activity"] is False
    assert 19 <= period["onset_bin"] <= 23
    assert 19 <= period["peak_bin"] <= 23
    assert period["window"]["mass"] > 0.5


def test_step_cells_cover_the_scenario_cells() -> None:
    cells = PAYLOADS["step_cells"]
    assert len(cells) == 5
    assert all(cell["harmonized"] > 0 for cell in cells)
    assert all(_finite(cell["peak_frp"]) for cell in cells)


def test_golden_directory_contains_no_untracked_extras() -> None:
    """A stray file in tests/golden/ means the generator and the dir disagree."""
    on_disk = {path.stem for path in Path(GOLDEN_DIR).glob("*.json")}
    assert on_disk == set(PAYLOADS)
