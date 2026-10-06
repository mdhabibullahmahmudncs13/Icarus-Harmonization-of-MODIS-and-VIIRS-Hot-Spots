"""Tests for src/acquire/firms.py.

Everything here is offline: the network is replaced by a fake fetcher, so
the suite exercises the chunking, URL, resume and parquet logic without a
MAP_KEY or an internet connection.
"""

from __future__ import annotations

from datetime import date, timedelta
from itertools import pairwise

import pandas as pd
import pytest

from src.acquire import firms
from src.acquire.firms import (
    DOWNLOAD_ORDER,
    MAX_DAY_RANGE,
    PRODUCTS,
    Chunk,
    FirmsProduct,
    TransactionLimiter,
    area_url,
    bbox_param,
    chunk_paths,
    chunk_windows,
    download,
    download_chunk,
    download_product,
    load_map_key,
    main,
    merged_path,
    parse_firms_csv,
    product_window,
    read_dotenv,
    require_map_key,
)


class _Resp:
    """Minimal ``requests.Response`` stand-in carrying CSV text."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.status_code = 200

    def raise_for_status(self) -> None:  # pragma: no cover - always 200 here
        return None


_CSV_HEADER = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,"
    "satellite,instrument,confidence,version,bright_ti5,frp,daynight,type"
)
# One VIIRS detection per request, dated by the chunk it came from.
_ONE_ROW = "23.1,90.1,330.1,0.4,0.4,{day},0120,N20,VIIRS,n,2.0NRT,290.0,1.2,D,0"


def _csv_for_day(day: str) -> str:
    return f"{_CSV_HEADER}\n{_ONE_ROW.format(day=day)}\n"


def _day_from_url(url: str) -> str:
    """The Area API date is the last path segment: .../{DAYS}/{DATE}."""
    return url.rsplit("/", 1)[-1]


def _dated_fetcher(fail: bool = False):
    """Return a fake fetcher producing one row dated to the requested chunk."""
    calls: list[str] = []

    def fetch(url: str):
        if fail:
            raise AssertionError("network must not be called")
        calls.append(url)
        return _Resp(_csv_for_day(_day_from_url(url)))

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


def _sample_product() -> FirmsProduct:
    return FirmsProduct(
        "TEST_SP", "VIIRS", "Test-Sat", "SP", date(2000, 1, 1), date(2100, 1, 1)
    )


# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------


def test_chunk_windows_cover_the_range_without_gaps_or_overlaps():
    start, end = date(2026, 1, 1), date(2026, 1, 17)
    chunks = chunk_windows(start, end)
    assert chunks[0].start == start
    assert chunks[-1].end == end
    for previous, current in pairwise(chunks):
        assert current.start == previous.end + timedelta(days=1)


def test_chunk_windows_respect_the_area_api_ceiling():
    chunks = chunk_windows(date(2026, 1, 1), date(2026, 1, 17))
    assert all(1 <= c.days <= MAX_DAY_RANGE for c in chunks)
    # 17 days at 5 per request -> 5, 5, 5, 2
    assert [c.days for c in chunks] == [5, 5, 5, 2]


def test_chunk_windows_single_day_and_reversed_ranges():
    assert chunk_windows(date(2026, 1, 1), date(2026, 1, 1)) == [Chunk(date(2026, 1, 1), 1)]
    assert chunk_windows(date(2026, 1, 2), date(2026, 1, 1)) == []


def test_chunk_windows_rejects_a_bad_day_range():
    with pytest.raises(ValueError):
        chunk_windows(date(2026, 1, 1), date(2026, 1, 5), day_range=0)


# --------------------------------------------------------------------------
# URLs
# --------------------------------------------------------------------------


def test_bbox_param_formats_without_trailing_zeros():
    assert bbox_param((88.0, 20.0, 93.0, 27.0)) == "88,20,93,27"
    assert bbox_param((88.5, 20.25, 93.0, 27.0)) == "88.5,20.25,93,27"


def test_bbox_param_rejects_a_degenerate_box():
    with pytest.raises(ValueError):
        bbox_param((93.0, 20.0, 88.0, 27.0))


def test_area_url_matches_the_documented_shape():
    url = area_url("KEY", "VIIRS_SNPP_SP", (88.0, 20.0, 93.0, 27.0), 5, date(2012, 1, 1))
    assert url == (
        "https://firms.modaps.eosdis.nasa.gov/api/area/csv/KEY/VIIRS_SNPP_SP/"
        "88,20,93,27/5/2012-01-01"
    )


def test_area_url_without_a_date_asks_for_the_most_recent_data():
    url = area_url("KEY", "MODIS_SP", (88.0, 20.0, 93.0, 27.0), 1)
    assert url.endswith("/MODIS_SP/88,20,93,27/1")


def test_area_url_guards_its_inputs():
    with pytest.raises(ValueError):
        area_url("", "MODIS_SP", (88.0, 20.0, 93.0, 27.0), 1)
    with pytest.raises(ValueError):
        area_url("KEY", "MODIS_SP", (88.0, 20.0, 93.0, 27.0), 6)
    with pytest.raises(ValueError):
        area_url("KEY", "NOT_A_PRODUCT", (88.0, 20.0, 93.0, 27.0), 1)


# --------------------------------------------------------------------------
# Product table
# --------------------------------------------------------------------------


def test_suomi_npp_is_downloaded_first_and_every_product_is_standard_processing():
    assert DOWNLOAD_ORDER[0] == "VIIRS_SNPP_SP"
    assert all(PRODUCTS[source].processing == "SP" for source in DOWNLOAD_ORDER)


def test_suomi_npp_window_carries_the_hard_deadline():
    npp = PRODUCTS["VIIRS_SNPP_SP"]
    assert npp.family == "VIIRS"
    assert npp.end == date(2026, 11, 1)
    assert npp.start == date(2012, 1, 1)


def test_product_window_intersects_the_requested_range():
    npp = PRODUCTS["VIIRS_SNPP_SP"]
    assert product_window(npp, date(2003, 1, 1), date(2026, 9, 30)) == (
        date(2012, 1, 1),
        date(2026, 9, 30),
    )
    assert product_window(npp, date(2003, 1, 1), date(2011, 1, 1)) is None


# --------------------------------------------------------------------------
# Keys
# --------------------------------------------------------------------------


def test_require_map_key_explains_where_to_get_one(monkeypatch, tmp_path):
    monkeypatch.setattr(firms, "REPO_ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="map_key"):
        require_map_key({})


def test_load_map_key_prefers_the_environment_then_dotenv(monkeypatch, tmp_path):
    monkeypatch.setattr(firms, "REPO_ROOT", tmp_path)
    (tmp_path / ".env").write_text("# comment\nFIRMS_MAP_KEY=from_file\n")
    assert read_dotenv() == {"FIRMS_MAP_KEY": "from_file"}
    assert load_map_key({}) == "from_file"
    assert load_map_key({"FIRMS_MAP_KEY": "from_env"}) == "from_env"


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


def test_transaction_limiter_only_sleeps_once_the_window_is_full():
    now = [0.0]
    slept: list[float] = []
    limiter = TransactionLimiter(
        max_transactions=2,
        window_seconds=10.0,
        clock=lambda: now[0],
        sleep=slept.append,
    )
    limiter.acquire()
    limiter.acquire()
    assert slept == []
    limiter.acquire()  # third transaction in the window must wait
    assert slept == [10.0]


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def test_parse_firms_csv_tags_provenance_columns():
    frame = parse_firms_csv(_csv_for_day("2026-01-01"), PRODUCTS["VIIRS_SNPP_SP"])
    assert len(frame) == 1
    assert frame.loc[0, "source_product"] == "VIIRS_SNPP_SP"
    assert frame.loc[0, "sensor_family"] == "VIIRS"
    assert frame.loc[0, "confidence"] == "n"


def test_parse_firms_csv_returns_an_empty_frame_for_an_empty_payload():
    empty = parse_firms_csv("", PRODUCTS["MODIS_SP"])
    assert empty.empty
    assert "source_product" in empty.columns


def test_parse_firms_csv_rejects_a_payload_that_is_not_fire_data():
    with pytest.raises(ValueError, match="missing columns"):
        parse_firms_csv("Invalid MAP_KEY\n", PRODUCTS["MODIS_SP"])


# --------------------------------------------------------------------------
# Downloading
# --------------------------------------------------------------------------


def _window() -> tuple[date, date]:
    return date(2026, 1, 1), date(2026, 1, 7)


def test_download_chunk_writes_csv_and_parquet(tmp_path):
    start, end = _window()
    chunk = chunk_windows(start, end)[0]
    fetcher = _dated_fetcher()
    result = download_chunk(
        PRODUCTS["VIIRS_SNPP_SP"],
        chunk,
        firms.BANGLADESH_BBOX,
        "KEY",
        cache_dir=tmp_path,
        fetcher=fetcher,
        offline=False,
    )
    assert result.status == "fetched"
    assert result.rows == 1
    csv_path, parquet_path = chunk_paths("VIIRS_SNPP_SP", chunk, tmp_path)
    assert csv_path.exists() and parquet_path.exists()
    assert pd.read_parquet(parquet_path).loc[0, "source_product"] == "VIIRS_SNPP_SP"


def test_download_chunk_resumes_and_does_not_refetch(tmp_path):
    start, end = _window()
    chunk = chunk_windows(start, end)[0]
    download_chunk(
        PRODUCTS["VIIRS_SNPP_SP"],
        chunk,
        firms.BANGLADESH_BBOX,
        "KEY",
        cache_dir=tmp_path,
        fetcher=_dated_fetcher(),
        offline=False,
    )
    # Second run: the parquet exists, so the network must not be touched.
    result = download_chunk(
        PRODUCTS["VIIRS_SNPP_SP"],
        chunk,
        firms.BANGLADESH_BBOX,
        "KEY",
        cache_dir=tmp_path,
        fetcher=_dated_fetcher(fail=True),
        offline=False,
    )
    assert result.status == "skipped"


def test_download_chunk_offline_without_cache_is_missing_not_fatal(tmp_path):
    chunk = chunk_windows(*_window())[0]
    result = download_chunk(
        PRODUCTS["VIIRS_SNPP_SP"],
        chunk,
        firms.BANGLADESH_BBOX,
        "",
        cache_dir=tmp_path,
        fetcher=_dated_fetcher(fail=True),
        offline=True,
    )
    assert result.status == "missing"


def test_download_chunk_never_caches_an_error_page(tmp_path):
    """A throttle page ("invalid map_key.") must not become the CSV cache.

    It used to be written before parsing, so one transient NASA error poisoned
    the chunk: every later run took the "cached CSV" path and raised instead
    of re-fetching, and no download could ever resume.
    """
    chunk = chunk_windows(*_window())[0]
    csv_path, parquet_path = chunk_paths("VIIRS_SNPP_SP", chunk, tmp_path)

    def throttle(url: str):
        return _Resp("invalid map_key.")

    with pytest.raises(ValueError, match="missing columns"):
        download_chunk(
            PRODUCTS["VIIRS_SNPP_SP"],
            chunk,
            firms.BANGLADESH_BBOX,
            "KEY",
            cache_dir=tmp_path,
            fetcher=throttle,
            offline=False,
        )
    assert not csv_path.exists()
    assert not parquet_path.exists()


def test_a_poisoned_csv_cache_falls_through_to_the_live_fetch(tmp_path):
    """An error page left by an older run is re-fetched, not raised forever."""
    chunk = chunk_windows(*_window())[0]
    csv_path, parquet_path = chunk_paths("VIIRS_SNPP_SP", chunk, tmp_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text("invalid map_key.")

    result = download_chunk(
        PRODUCTS["VIIRS_SNPP_SP"],
        chunk,
        firms.BANGLADESH_BBOX,
        "KEY",
        cache_dir=tmp_path,
        fetcher=_dated_fetcher(),
        offline=False,
    )
    assert result.status == "fetched"
    assert parquet_path.exists()
    assert "invalid map_key" not in csv_path.read_text(), "the poison must be overwritten"


def test_download_product_writes_one_merged_parquet_covering_every_chunk(tmp_path):
    start, end = _window()
    fetcher = _dated_fetcher()
    report = download_product(
        "VIIRS_SNPP_SP",
        firms.BANGLADESH_BBOX,
        start,
        end,
        cache_dir=tmp_path,
        map_key="KEY",
        fetcher=fetcher,
        offline=False,
    )
    chunks = chunk_windows(start, end)
    assert report.window == (start, end)
    assert report.rows == len(chunks)
    assert report.merged == merged_path("VIIRS_SNPP_SP", tmp_path)
    merged = pd.read_parquet(report.merged)
    assert len(merged) == len(chunks)
    assert set(merged["acq_date"]) == {"2026-01-01", "2026-01-06"}


def test_download_reports_a_product_with_no_overlap_without_fetching(tmp_path):
    report = download_product(
        "VIIRS_NOAA21_SP",
        firms.BANGLADESH_BBOX,
        date(2003, 1, 1),
        date(2010, 1, 1),
        cache_dir=tmp_path,
        fetcher=_dated_fetcher(fail=True),
        offline=False,
    )
    assert report.window is None
    assert report.results == []
    assert "no overlap" in report.summary()


def test_offline_dry_run_writes_nothing_to_disk(tmp_path):
    report = download_product(
        "VIIRS_SNPP_SP",
        firms.BANGLADESH_BBOX,
        *_window(),
        cache_dir=tmp_path,
        fetcher=_dated_fetcher(fail=True),
        offline=True,
    )
    assert report.missing == len(report.results)
    assert list(tmp_path.rglob("*")) == []


def test_download_defaults_to_suomi_npp_first(tmp_path):
    reports = download(
        ("VIIRS_SNPP_SP",),
        firms.BANGLADESH_BBOX,
        date(2026, 1, 1),
        date(2026, 1, 3),
        cache_dir=tmp_path,
        map_key="KEY",
        fetcher=_dated_fetcher(),
        offline=False,
    )
    assert [r.product.source for r in reports] == ["VIIRS_SNPP_SP"]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def test_cli_offline_reads_cache_and_reports_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("OFFLINE", "1")
    code = main(
        [
            "--products",
            "VIIRS_SNPP_SP",
            "--start",
            "2026-01-01",
            "--end",
            "2026-01-03",
            "--cache-dir",
            str(tmp_path),
        ]
    )
    out = capsys.readouterr()
    assert code == 0
    assert "VIIRS_SNPP_SP" in out.out
    assert "missing" in out.err


def test_cli_refuses_unknown_products(capsys):
    assert main(["--products", "NOPE"]) == 2
    assert "unknown products" in capsys.readouterr().err
