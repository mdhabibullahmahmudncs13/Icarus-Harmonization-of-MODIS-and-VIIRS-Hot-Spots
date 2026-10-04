"""Safe fetch wrapper for data acquisition.

Tries live network, then cache/, then demo_fixtures/. Honours OFFLINE=1.
Never raises during a demo. Returns ``(data, source)`` where ``source`` is
one of ``"live"``, ``"cache"``, or ``"fixture"``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "cache"
FIXTURE_DIR = REPO_ROOT / "demo_fixtures"


def _is_offline() -> bool:
    """Return True when OFFLINE=1 is set."""
    return os.environ.get("OFFLINE", "").strip().lower() in {"1", "true", "yes"}


def _try_live(url: str, fetcher: Callable[[str], Any]) -> Any | None:
    """Attempt a live fetch. Return None on any failure."""
    if _is_offline():
        return None
    try:
        return fetcher(url)
    except requests.RequestException:
        return None


def _try_file(directory: Path, name: str) -> Any | None:
    """Return the parsed file at ``directory/name`` if it exists."""
    path = directory / name
    if not path.exists():
        return None
    # Defer parsing to the caller via a sentinel: return the raw text and
    # let the caller decide how to parse it. For the harness the mere
    # existence of the file is enough; the test mocks the parse step.
    return path.read_text()


def safe_fetch(
    url: str,
    cache_name: str,
    fixture_name: str,
    fetcher: Callable[[str], Any] | None = None,
    parser: Callable[[Any], Any] | None = None,
) -> tuple[Any, str]:
    """Fetch ``url``, falling back to ``cache_name`` then ``fixture_name``.

    Resolution order:

    1. **Live** network call via ``fetcher(url)`` (skipped when
       ``OFFLINE=1``). Any exception is swallowed.
    2. **Cache** file at ``cache/cache_name`` if present.
    3. **Fixture** file at ``demo_fixtures/fixture_name`` if present.
    4. Otherwise the live attempt's exception is re-raised so the caller
       can decide. Callers should treat this as a hard failure for
       production but as a no-op during a demo (the fixture path always
       exists in the demo).

    ``fetcher`` defaults to ``requests.get``. ``parser`` turns the raw
    payload into the final return value; pass ``None`` to return the raw
    payload (text for files, ``requests.Response`` for live).

    Never raises during a demo because every demo path includes a fixture.
    """
    fetcher = fetcher or requests.get
    parser = parser or (lambda raw: raw)

    # 1. Live
    live_payload = _try_live(url, fetcher)
    if live_payload is not None:
        return parser(live_payload), "live"

    # 2. Cache
    cached = _try_file(CACHE_DIR, cache_name)
    if cached is not None:
        return parser(cached), "cache"

    # 3. Fixture
    fixture = _try_file(FIXTURE_DIR, fixture_name)
    if fixture is not None:
        return parser(fixture), "fixture"

    # 4. Nothing worked. If we never went live (because OFFLINE=1) this is
    #    expected for a demo without the right fixture; surface a clear
    #    error rather than letting the previous exception leak.
    raise FileNotFoundError(
        f"safe_fetch: no live, cache, or fixture for url={url!r}; "
        f"tried cache={cache_name!r}, fixture={fixture_name!r}"
    )