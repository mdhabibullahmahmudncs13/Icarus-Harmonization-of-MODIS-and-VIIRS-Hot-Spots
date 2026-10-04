"""Tests for src/acquire/safe.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.acquire.safe import safe_fetch


def _make_response(text: str):
    """Build a minimal stand-in for ``requests.Response``."""

    class _Resp:
        def __init__(self, text: str) -> None:
            self.text = text
            self.status_code = 200

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

    return _Resp(text)


def test_live_path_returns_live(monkeypatch, tmp_path):
    """When the network works, safe_fetch returns the live payload."""
    monkeypatch.delenv("OFFLINE", raising=False)
    fetcher_calls: list[str] = []

    def fake_fetcher(url: str):
        fetcher_calls.append(url)
        return _make_response("LIVE")

    data, source = safe_fetch(
        url="https://example.test/live.csv",
        cache_name="missing.csv",
        fixture_name="missing.csv",
        fetcher=fake_fetcher,
    )

    assert source == "live"
    # Live path returns the fetcher's raw payload (a Response-like object).
    assert getattr(data, "text", data) == "LIVE"
    assert fetcher_calls == ["https://example.test/live.csv"]


def test_cache_path_when_live_fails(monkeypatch, tmp_path):
    """When the network fails the function falls back to cache/."""
    monkeypatch.delenv("OFFLINE", raising=False)

    cache_file = tmp_path / "cache.csv"
    cache_file.write_text("CACHED")

    def fake_fetcher(_url: str):
        import requests

        raise requests.ConnectionError("nope")

    with patch("src.acquire.safe.CACHE_DIR", tmp_path):
        data, source = safe_fetch(
            url="https://example.test/x.csv",
            cache_name="cache.csv",
            fixture_name="missing.csv",
            fetcher=fake_fetcher,
        )

    assert source == "cache"
    assert data == "CACHED"


def test_fixture_path_when_live_and_cache_fail(monkeypatch, tmp_path):
    """When both live and cache fail, fall back to demo_fixtures/."""
    monkeypatch.delenv("OFFLINE", raising=False)

    fixture_file = tmp_path / "fixture.csv"
    fixture_file.write_text("FIXTURE")

    def fake_fetcher(_url: str):
        import requests

        raise requests.ConnectionError("nope")

    with (
        patch("src.acquire.safe.CACHE_DIR", tmp_path / "empty"),
        patch("src.acquire.safe.FIXTURE_DIR", tmp_path),
    ):
        data, source = safe_fetch(
            url="https://example.test/x.csv",
            cache_name="cache.csv",
            fixture_name="fixture.csv",
            fetcher=fake_fetcher,
        )

    assert source == "fixture"
    assert data == "FIXTURE"


def test_offline_flag_skips_live(monkeypatch, tmp_path):
    """With OFFLINE=1 the network is never contacted."""
    monkeypatch.setenv("OFFLINE", "1")

    fixture_file = tmp_path / "fixture.csv"
    fixture_file.write_text("FIXTURE")

    def fake_fetcher(url: str):  # pragma: no cover - must not be called
        raise AssertionError(f"fetcher called with {url!r} while OFFLINE=1")

    with (
        patch("src.acquire.safe.CACHE_DIR", tmp_path / "empty"),
        patch("src.acquire.safe.FIXTURE_DIR", tmp_path),
    ):
        data, source = safe_fetch(
            url="https://example.test/x.csv",
            cache_name="cache.csv",
            fixture_name="fixture.csv",
            fetcher=fake_fetcher,
        )

    assert source == "fixture"
    assert data == "FIXTURE"


def test_demo_never_raises(monkeypatch, tmp_path):
    """When the demo fixture exists, even a busted network is fine."""
    monkeypatch.setenv("OFFLINE", "1")

    fixture_file = tmp_path / "fixture.csv"
    fixture_file.write_text("FIXTURE")

    def fake_fetcher(_url: str):
        import requests

        raise requests.ConnectionError("nope")

    with (
        patch("src.acquire.safe.CACHE_DIR", tmp_path / "empty"),
        patch("src.acquire.safe.FIXTURE_DIR", tmp_path),
    ):
        # If this raises, the demo would crash. safe_fetch must not.
        data, source = safe_fetch(
            url="https://example.test/x.csv",
            cache_name="cache.csv",
            fixture_name="fixture.csv",
            fetcher=fake_fetcher,
        )

    assert source == "fixture"
    assert data == "FIXTURE"


def test_nothing_found_raises(monkeypatch, tmp_path):
    """Without live, cache, or fixture the function raises clearly."""
    monkeypatch.setenv("OFFLINE", "1")

    def fake_fetcher(_url: str):
        import requests

        raise requests.ConnectionError("nope")

    with (
        patch("src.acquire.safe.CACHE_DIR", tmp_path / "empty"),
        patch("src.acquire.safe.FIXTURE_DIR", tmp_path / "empty"),
        pytest.raises(FileNotFoundError),
    ):
        safe_fetch(
            url="https://example.test/x.csv",
            cache_name="cache.csv",
            fixture_name="fixture.csv",
            fetcher=fake_fetcher,
        )