"""E1-E9 harness (``src.validate``) — structure, decision rules, determinism.

Runs on the deterministic synthetic generator, so the test needs no cache and
no network. ``src.demo.synthetic_detections`` gives both sensors over three
years, which is what E2's leave-one-year-out needs.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from src.demo import synthetic_detections
from src.validate import run_all
from src.validate.experiments import EXPERIMENT_ORDER
from src.validate.report import render_markdown, render_svg

VALID_VERDICTS = {"supported", "partial", "not supported", "limitation"}


@pytest.fixture(scope="module")
def detections():
    return synthetic_detections(days=1095, start=date(2013, 1, 1))


@pytest.fixture(scope="module")
def results(detections):
    return run_all(detections, source="fixture")


def test_every_experiment_is_present_and_ordered(results):
    ids = [experiment["id"] for experiment in results["experiments"]]
    assert ids == list(EXPERIMENT_ORDER)


def test_results_are_json_serialisable_without_nan(results):
    # allow_nan=False is the point: the contract forbids NaN, so the report must
    # never carry one. A NaN raises here.
    text = json.dumps(results, allow_nan=False)
    assert "\"E1\"" in text


def test_every_verdict_is_from_the_allowed_set(results):
    for experiment in results["experiments"]:
        assert experiment["verdict"] in VALID_VERDICTS, experiment["id"]


def test_e1_artificial_step_shrinks(results):
    e1 = results["experiments"][0]
    assert e1["verdict"] == "supported"
    assert e1["metrics"]["synthetic_harmonized_step"] < e1["metrics"]["synthetic_raw_step"]
    assert e1["metrics"]["synthetic_harmonized_step"] < 1.5


def test_e2_calibration_improves_the_offset(results):
    e2 = next(e for e in results["experiments"] if e["id"] == "E2")
    assert e2["metrics"]["overlap_years"] >= 2
    assert e2["metrics"]["median_abs_offset_calibrated"] < e2["metrics"]["median_abs_offset_raw"]


def test_e8_is_reported_as_a_limitation_not_a_number(results):
    e8 = next(e for e in results["experiments"] if e["id"] == "E8")
    assert e8["verdict"] == "limitation"
    assert e8["metrics"] == {}


def test_figures_render_to_svg(results):
    for experiment in results["experiments"]:
        figure = experiment["figure"]
        if figure is None:
            continue
        svg = render_svg(figure)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")


def test_markdown_report_names_every_experiment(results):
    markdown = render_markdown(results)
    for identifier in EXPERIMENT_ORDER:
        assert f"## {identifier} —" in markdown


def test_run_all_is_deterministic(detections):
    first = run_all(detections, source="fixture")
    second = run_all(detections, source="fixture")
    assert first == second
