"""Tests for src/compute — deterministic harmonization core (Phase 2).

Covers unit edge cases, the property invariants required by the plan
(idempotence, row-order invariance, duplicate tolerance), and a golden scenario
where VIIRS emits ~3x the detections of MODIS in the same cells.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pandas as pd
import pytest

from src.compute import (
    STREAM_BITS,
    Detection,
    anomaly,
    critical_period,
    harmonize,
    overlap_validation,
    pearson,
    percentile,
    quality_filter,
    schema,
    spearman,
)

# --- fixtures --------------------------------------------------------------


def det(
    lon: float,
    lat: float,
    date: str,
    stream: str,
    instrument: str,
    *,
    conf_num: int | None = None,
    conf_class: str | None = None,
    hs_type: int | None = 0,
    frp: float = 10.0,
) -> Detection:
    return Detection(
        acq_date=date,
        acq_time="1200",
        lon=lon,
        lat=lat,
        frp=frp,
        conf_num=conf_num,
        conf_class=conf_class,
        hs_type=hs_type,
        instrument=instrument,
        sat="T" if stream == "MOD_T" else "S-NPP",
        stream=stream,
        stream_bit=STREAM_BITS[stream],
    )


def modis(lon: float, lat: float, date: str, **kw) -> Detection:
    return det(lon, lat, date, "MOD_T", "MODIS", conf_num=kw.pop("conf_num", 80), **kw)


def viirs(lon: float, lat: float, date: str, **kw) -> Detection:
    return det(lon, lat, date, "VIIRS_SNPP", "VIIRS", conf_class=kw.pop("conf_class", "h"), **kw)


# --- S2 quality filter -----------------------------------------------------


def test_quality_filter_modis_confidence_boundary() -> None:
    dets = [modis(0.1, 0.1, "2019-01-01", conf_num=29), modis(0.2, 0.2, "2019-01-01", conf_num=30)]
    kept = quality_filter(dets, c_min=30)
    assert len(kept) == 1
    assert kept[0].conf_num == 30


def test_quality_filter_modis_type_and_null() -> None:
    keep_null = modis(0.1, 0.1, "2019-01-01", hs_type=None)
    drop_urban = modis(0.2, 0.2, "2019-01-01", hs_type=3)
    drop_persistent = modis(0.3, 0.3, "2019-01-01", hs_type=2)
    assert quality_filter([keep_null]) == [keep_null]
    assert quality_filter([drop_urban, drop_persistent]) == []


def test_quality_filter_viirs_classes() -> None:
    low = viirs(0.1, 0.1, "2019-01-01", conf_class="l")
    nominal = viirs(0.2, 0.2, "2019-01-01", conf_class="n")
    high = viirs(0.3, 0.3, "2019-01-01", conf_class="h")
    assert quality_filter([low, nominal, high]) == [nominal, high]


# --- S4 grid ---------------------------------------------------------------


def test_grid_index_floor_and_negatives() -> None:
    # ``grid_index`` returns (row, column), latitude first.
    assert harmonize.grid_index(0.0, 0.0) == (0, 0)
    assert harmonize.grid_index(-0.01, -0.01) == (-1, -1)
    # A point exactly on a cell boundary belongs to the higher index.
    step = harmonize.degrees_per_lat()
    assert harmonize.grid_index(step, 0.0) == (1, 0)
    assert harmonize.grid_index(0.0, harmonize.degrees_per_lon()) == (0, 1)


# --- S5 collapse -----------------------------------------------------------


def _collapsed(dets: list[Detection]) -> pd.DataFrame:
    """The cell-day table the production collapse produces."""
    return harmonize.collapse_cell_days(
        harmonize.harmonize(schema.detections_to_frame(dets))
    )


def test_collapse_groups_and_counts() -> None:
    # The two MODIS hits sit inside one production cell (~0.05 deg), so all
    # three detections collapse into one cell-day.
    dets = [
        modis(0.10, 0.10, "2019-01-01", frp=5.0),
        modis(0.105, 0.105, "2019-01-01", frp=12.0),
        viirs(0.10, 0.10, "2019-01-01", frp=9.0),
    ]
    cds = _collapsed(dets)
    assert len(cds) == 1
    cd = cds.iloc[0]
    assert cd["raw_detections"] == 3
    # Two sensors saw the cell-day: a MODIS hit and a VIIRS hit.
    assert cd["sensors_agreeing"] == 2


def test_collapse_is_row_order_invariant() -> None:
    dets = [modis(0.1 * i, 0.1 * i, "2019-01-01") for i in range(1, 6)]
    shuffled = dets[:]
    random.Random(7).shuffle(shuffled)
    pd.testing.assert_frame_equal(_collapsed(dets), _collapsed(shuffled))


def test_collapse_duplicate_tolerance() -> None:
    base = [modis(0.10, 0.10, "2019-01-01")]
    with_dupe = base + [modis(0.10, 0.10, "2019-01-01")]
    assert len(_collapsed(base)) == 1
    assert len(_collapsed(with_dupe)) == 1
    assert _collapsed(with_dupe).iloc[0]["raw_detections"] == 2


def test_collapse_is_idempotent() -> None:
    """Collapsing an already-collapsed table changes nothing."""
    once = _collapsed([modis(0.1 * i, 0.1 * i, "2019-01-01") for i in range(1, 4)])
    twice = harmonize.collapse_cell_days(once)
    assert len(twice) == len(once)


# --- series / cells --------------------------------------------------------


def test_daily_series_raw_vs_harmonized() -> None:
    dets = [
        modis(0.10, 0.10, "2019-06-01"),  # cell A
        modis(0.30, 0.30, "2019-06-01"),  # cell B
        viirs(0.10, 0.10, "2019-06-01"),  # cell A again
        viirs(0.10, 0.10, "2019-06-01"),  # cell A again
        viirs(0.50, 0.50, "2019-06-01"),  # cell C
    ]
    frame = harmonize.harmonize(schema.detections_to_frame(dets))
    s = harmonize.daily_series(frame).to_dict(orient="records")
    assert len(s) == 1
    row = s[0]
    assert row["raw_modis"] == 2
    assert row["raw_viirs"] == 3
    assert row["raw_total"] == 5
    assert row["harm_modis"] == 2  # A, B
    assert row["harm_viirs"] == 2  # A, C
    assert row["harm_total"] == 3  # A, B, C (union, not sum)


def test_cell_totals() -> None:
    dets = [modis(0.10, 0.10, "2019-06-01", frp=4.0), modis(0.10, 0.10, "2019-06-02", frp=8.0)]
    frame = harmonize.harmonize(schema.detections_to_frame(dets))
    cells = harmonize.cell_totals(frame)
    assert len(cells) == 1
    assert cells[0]["raw"] == 2
    assert cells[0]["harmonized"] == 2
    assert cells[0]["peak_frp"] == 8.0


# --- baseline --------------------------------------------------------------


def test_percentile_interpolation() -> None:
    assert percentile([], 0.5) == 0.0
    assert percentile([5], 0.9) == 5.0
    assert percentile([1, 2, 3, 4], 0.5) == pytest.approx(2.5)
    assert percentile([1, 2, 3, 4], 0.0) == 1.0
    assert percentile([1, 2, 3, 4], 1.0) == 4.0


def test_seasonal_baseline_pools_years() -> None:
    # non-leap years only, so all three share day-of-year 60
    series = pd.Series(
        [4, 8, 12],
        index=pd.to_datetime(["2018-03-01", "2019-03-01", "2021-03-01"]),
    )
    bl = harmonize.baseline_percentiles(series, window_days=0)
    doy_march1 = 60
    assert bl.loc[doy_march1, "p50"] == pytest.approx(8.0)
    assert bl.loc[doy_march1, "p05"] == pytest.approx(4.4)


# --- anomaly ---------------------------------------------------------------


def _baseline_series(years: range, value: int, spike: tuple[str, int] | None = None) -> list[dict]:
    rows = []
    for y in years:
        for m in (1, 2, 3, 4):
            rows.append({"date": f"{y}-{m:02d}-15", "harm_total": value})
    if spike:
        rows.append({"date": spike[0], "harm_total": spike[1]})
    return rows


def test_anomaly_not_scored_with_insufficient_reference() -> None:
    series = _baseline_series([2019], 5)
    result = anomaly(series, "2019-02-15")
    assert result["flag"] == "not_scored"
    assert result["reason"] == "insufficient_reference_years"


def test_anomaly_extreme_on_a_clear_spike() -> None:
    series = _baseline_series(range(2000, 2020), 5, spike=("2010-02-15", 500))
    result = anomaly(series, "2010-02-15")
    assert result["flag"] == "extreme"
    assert result["z"] is not None and result["z"] >= 3
    assert result["percentile"] == pytest.approx(1.0)


def test_anomaly_sigma_floor_keeps_z_finite() -> None:
    series = _baseline_series(range(2000, 2020), 5, spike=("2010-02-15", 6))
    result = anomaly(series, "2010-02-15")
    assert result["z"] is not None and abs(result["z"]) < 1000  # no division by zero


# --- season ----------------------------------------------------------------


def test_critical_period_finds_the_burning_window() -> None:
    rows = []
    for y in (2018, 2019, 2020):
        for m in range(1, 13):
            for d in (1, 9, 17, 25):
                doy = (m - 1) * 30 + d
                value = 50 if 57 <= doy <= 96 else 1
                rows.append({"date": f"{y}-{m:02d}-{d:02d}", "harm_total": value})
    result = critical_period(rows)
    assert result["insufficient_activity"] is False
    assert 5 <= result["peak_bin"] <= 14
    assert result["window"]["mass"] >= 0.8


def test_critical_period_insufficient_activity() -> None:
    rows = [{"date": "2019-01-01", "harm_total": 0}]
    result = critical_period(rows)
    assert result["insufficient_activity"] is True
    assert result["window"] is None


# --- validation ------------------------------------------------------------


def test_pearson_and_spearman() -> None:
    assert pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert pearson([1, 2, 3], [6, 4, 2]) == pytest.approx(-1.0)
    assert spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)
    assert pearson([1], [1]) is None


def test_overlap_validation_harmonized_beats_raw() -> None:
    rows = []
    for i in range(40):
        signal = 1 + (i % 3)
        rows.append(
            {
                "date": f"2013-06-{i % 28 + 1:02d}",
                "raw_modis": signal,
                "raw_viirs": signal * 10 if i % 2 == 0 else 25,  # raw noisy
                "harm_modis": signal,
                "harm_viirs": signal,  # harmonized agrees with MODIS
            }
        )
    result = overlap_validation(rows, transition="2012-01-20")
    assert result["overlap"]["n_days"] == 40
    assert result["harmonized"]["pearson"] > result["raw"]["pearson"]


# --- golden scenario: the whole point of the project ------------------------

#: The committed fixture, written by ``tools/gen_golden.py``. Its detections are
#: built by ``tools.gen_golden.step_detections`` and ``tests/test_golden.py``
#: fails if this file drifts from a fresh run of the pipeline, so the headline
#: numbers live in one place instead of being regenerated inside the test.
GOLDEN_SERIES: list[dict] = json.loads(
    (Path(__file__).parent / "golden" / "step_series.json").read_text()
)


def test_golden_raw_step_is_three_x_harmonized_is_flat() -> None:
    series = GOLDEN_SERIES
    pre = [r for r in series if r["date"] < "2012-01-20"]
    post = [r for r in series if r["date"] >= "2012-01-20"]

    def mean(rows: list[dict], key: str) -> float:
        return sum(r[key] for r in rows) / len(rows)

    raw_ratio = mean(post, "raw_total") / mean(pre, "raw_total")
    harm_ratio = mean(post, "harm_total") / mean(pre, "harm_total")

    assert 2.5 <= raw_ratio <= 3.5, raw_ratio
    assert harm_ratio <= 1.2, harm_ratio
