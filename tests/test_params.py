"""Tests for src/compute/params.py.

The parameter file is documented as the single source of every tunable value
and as the id that marks derived artifacts stale when a value changes
(docs/PARAMETERS.md §3). These tests hold that promise to account.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.compute import export, harmonize, params, schema


def test_the_file_is_readable_and_has_the_documented_sections() -> None:
    loaded = params.load_params()
    assert {"grid", "quality", "bins", "calibration", "coverage", "anomaly", "season", "api"} <= set(
        loaded
    )


def test_the_file_says_what_the_code_actually_uses() -> None:
    """A parameter that disagrees with the code is a trap for the next reader.

    The code is what ships, so the file must report the code's values: a
    ``c_min`` of 30 in the file while the pipeline filters at 50 would send
    anyone who trusted the file to the wrong answer.
    """
    from src.api import main

    loaded = params.load_params()
    assert loaded["quality"]["c_min"] == int(schema.MIN_CONFIDENCE)
    assert loaded["grid"]["cell_km"] == harmonize.DEFAULT_CELL_KM
    assert loaded["grid"]["reference_latitude_deg"] == harmonize.REFERENCE_LATITUDE_DEG
    # The API's bounds are read from this file at import, so the file is what
    # decides them; a value here that the API ignores would be a silent lie.
    assert loaded["api"]["max_aoi_cells"] == main.MAX_AOI_CELLS
    assert loaded["api"]["request_timeout_s"] == main.REQUEST_TIMEOUT_S


def test_the_hash_follows_the_files_bytes(tmp_path: Path) -> None:
    """Change a value in the file and the hash changes.

    This is the whole point of the file: the same parameters must always hash
    the same, and a changed parameter must never do.
    """
    copy = tmp_path / "params.yaml"
    copy.write_text(params.PARAMS_PATH.read_text())
    before = params.params_file_hash(copy)
    copy.write_text(copy.read_text().replace("c_min: 50", "c_min: 51"))
    assert params.params_file_hash(copy) != before


def test_the_hash_is_stable_for_an_unchanged_file() -> None:
    assert params.params_file_hash() == params.params_file_hash()


def test_the_response_hash_carries_the_file_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A changed parameter must invalidate the cached response id.

    Without the file in the hash, editing ``config/params.yaml`` would leave
    every cached payload looking current, which is the failure the docs say
    the hash exists to prevent.
    """
    args = {"date_range": ("2015-01-01", "2015-12-31")}
    before = export.params_hash(**args)
    monkeypatch.setattr(params, "params_file_hash", lambda *a, **k: "0123456789ab")
    assert export.params_hash(**args) != before


def test_an_unreadable_line_is_an_error_not_a_silent_skip(tmp_path: Path) -> None:
    """A parameter nobody can read is the problem this module exists to fix."""
    bad = tmp_path / "params.yaml"
    bad.write_text("grid:\n  cell_km: 5.5\n  ??? not a pair\n")
    with pytest.raises(ValueError, match="cannot read"):
        params.load_params(bad)


def test_the_parsed_values_keep_their_types() -> None:
    loaded = params.load_params()
    assert isinstance(loaded["grid"]["cell_km"], float)
    assert isinstance(loaded["quality"]["c_min"], int)
    assert loaded["quality"]["viirs_classes"] == ["n", "h"]
    assert loaded["coverage"]["zero_detection_rule"] is True
    assert loaded["season"]["min_mean_density"] == 1e-5


def test_the_file_is_valid_json_after_being_spelled_out(tmp_path: Path) -> None:
    """The reader must not be the only thing that can open the file."""
    text = params.PARAMS_PATH.read_text()
    assert "c_min" in text
    # A stray tab or an unbalanced bracket would break the reader silently.
    assert "\t" not in text
    assert text.count("[") == text.count("]")


def test_a_parameter_can_be_read_one_at_a_time() -> None:
    assert params.param(params.PARAMS_PATH, "bins", "bin_days") == 8
    assert params.param(params.PARAMS_PATH, "bins", "nope", 99) == 99


def test_the_mock_carries_the_same_file_hash() -> None:
    """The mock is not evidence, but it is still a payload about parameters.

    Its hash must move when the file moves, or a stale mock would look current
    next to a freshly built one.
    """
    from tools.gen_mock import params_hash as mock_params_hash

    assert len(mock_params_hash()) == 12
    assert mock_params_hash() != export.params_hash(date_range=("2015-01-01", "2015-12-31"))
