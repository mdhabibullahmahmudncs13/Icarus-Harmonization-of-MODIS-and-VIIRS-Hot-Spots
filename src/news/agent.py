"""Find sourced fire news for one date and region, or say plainly that none exists.

The agent is deliberately narrow:

1. Build a few queries from the region's English and local-language terms.
2. Ask Hyperbrowser search for candidate pages.
3. Fetch each candidate and extract its own claims (headline, summary, dates,
   source, region verdict) against a fixed schema.
4. Keep only pages that report a fire, are inside the region, and carry a
   publication date that matches the requested day (or whose event date does).
5. Attach the satellite cross-check: do detections exist in the same box/day?

Anything that cannot be verified is dropped. There is no generated headline,
summary or source, and an empty result is returned as an empty result with a
clear message — never padded with something the search did not produce.

Results are cached per ``(date, region)`` on disk for
``FIRE_NEWS_CACHE_TTL_S`` seconds (default 6 hours), so re-opening a view does
not pay for the same search twice.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src import regions
from src.acquire import safe
from src.news.hyperbrowser import (
    ArticleExtract,
    HyperbrowserClient,
    HyperbrowserError,
    SearchHit,
    normalize_date,
    source_from_url,
)

#: How many candidate pages one request may read. Bounded cost and latency.
MAX_CANDIDATES = 8
#: How many verified articles the payload may carry.
MAX_RESULTS = 8
#: Parallel page fetches; each is an independent browser job upstream.
FETCH_WORKERS = 4
#: Search terms that are already English; they seed the first queries.
ENGLISH_TERMS = frozenset({"wildfire", "forest fire", "bushfire", "brush fire", "scrub fire"})

DEFAULT_CACHE_TTL_S = 6 * 60 * 60.0
DEFAULT_DEADLINE_S = 25.0

CACHE_ENV = "FIRE_NEWS_CACHE_TTL_S"
DEADLINE_ENV = "FIRE_NEWS_TIMEOUT_S"


class FireNewsError(RuntimeError):
    """The search could not produce an honest answer."""


class FireNewsTimeout(FireNewsError):
    """The browsing budget ran out before any usable page was read."""


class FireNewsUnavailable(FireNewsError):
    """The search cannot run now: offline, or no cached answer to serve."""


@dataclass(frozen=True)
class VerifiedArticle:
    """One article that passed every filter, with its satellite verdict."""

    headline: str
    summary: str
    published_date: str
    event_date: str
    source_name: str
    url: str
    satellite_agreement: str


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _iso_timestamp(value: datetime | None = None) -> str:
    stamp = value or datetime.now(UTC)
    return stamp.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_queries(day: date, region: regions.Region) -> list[str]:
    """The day's queries: two English terms plus one local-language term.

    The label is omitted for ``World``, where it would only narrow the search
    to pages that happen to use the word. Terms come from the region registry,
    so local-language coverage changes with the region, not with the code.
    """
    terms = [term.strip() for term in region.search_terms if term.strip()]
    english = [term for term in terms if term.lower() in ENGLISH_TERMS]
    local = [term for term in terms if term.lower() not in ENGLISH_TERMS]
    base = english[:2] or ["wildfire"]
    place = "" if region.id == "WORLD" else f" {region.label}"
    stamp = f'"{day.isoformat()}"'
    queries = [f"{term}{place} {stamp}" for term in base]
    if local:
        queries.append(f"{local[0]}{place} {stamp}")
    else:
        queries.append(f"fire{place} {stamp}")
    return queries[:3]


def _cache_path(region_id: str, day: date, cache_dir: Path | str | None = None) -> Path:
    root = Path(cache_dir) if cache_dir is not None else (safe.CACHE_DIR / "news")
    return root / f"{region_id}_{day.isoformat()}.json"


def _read_cache(
    region_id: str, day: date, cache_dir: Path | str | None, ttl_s: float
) -> dict[str, Any] | None:
    if ttl_s <= 0:
        return None
    path = _cache_path(region_id, day, cache_dir)
    try:
        age = time.time() - path.stat().st_mtime
        if age > ttl_s:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("date") != day.isoformat():
        return None
    if (payload.get("region") or {}).get("id") != region_id:
        return None
    return {**payload, "cached": True}


def _write_cache(
    region_id: str, day: date, payload: dict[str, Any], cache_dir: Path | str | None
) -> None:
    path = _cache_path(region_id, day, cache_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        temporary.replace(path)
    except OSError:
        # A read-only cache is not a reason to fail a successful search.
        return


def _satellite_summary(
    bbox: tuple[float, float, float, float], day: date
) -> dict[str, Any]:
    """Detections inside the box on that day, or an explicit unavailable block."""
    try:
        from src.api.dataset import NoDataError, get_dataset

        frame = get_dataset().detections
        stamp = pd.Timestamp(day)
        todays = frame[frame["acq_date"] == stamp]
        west, south, east, north = bbox
        inside = todays[
            (todays["longitude"] >= west)
            & (todays["longitude"] <= east)
            & (todays["latitude"] >= south)
            & (todays["latitude"] <= north)
        ]
    except (NoDataError, KeyError, ValueError, ImportError):
        return {
            "available": False,
            "detections": 0,
            "active_cells": 0,
            "agrees_with_news": None,
        }
    cells = int(inside["cell_id"].nunique()) if "cell_id" in inside else int(len(inside))
    return {
        "available": True,
        "detections": int(len(inside)),
        "active_cells": cells,
        "agrees_with_news": None,
    }


def _article(
    extract: ArticleExtract,
    hit: SearchHit,
    *,
    day: date,
    satellite_available: bool,
    detections: int,
) -> VerifiedArticle | None:
    """Turn one extraction into a result, or ``None`` when it fails a rule."""
    if not (extract.is_fire_news and extract.in_region):
        return None
    published = normalize_date(extract.published_date)
    if published is None:
        # The card must show a publication date; no date means no honest card.
        return None
    if published != day.isoformat() and extract.event_date != day.isoformat():
        return None
    url = extract.url or hit.url
    headline = (extract.headline or hit.title).strip()
    summary = (extract.summary or hit.description).strip()
    if not url or not headline or not summary:
        return None
    agreement = (
        ("agrees" if detections > 0 else "no_detections")
        if satellite_available
        else "unavailable"
    )
    return VerifiedArticle(
        headline=headline,
        summary=summary if len(summary) <= 360 else f"{summary[:357].rstrip()}…",
        published_date=published,
        event_date=extract.event_date or published,
        source_name=(extract.source_name or source_from_url(url)).strip(),
        url=url,
        satellite_agreement=agreement,
    )


def _empty_payload(
    day: date, region: regions.Region, satellite: dict[str, Any], **extra: Any
) -> dict[str, Any]:
    return {
        "date": day.isoformat(),
        "region": {"id": region.id, "label": region.label, "bbox": list(region.bbox)},
        "generated_at": _iso_timestamp(),
        "cached": False,
        "partial": False,
        "count": 0,
        "results": [],
        "satellite": satellite,
        "message": f"No fire reports found for {region.label} on {day.isoformat()}.",
        **extra,
    }


def search_fire_news(
    day: date,
    region_id: str,
    *,
    client: HyperbrowserClient | None = None,
    cache_dir: Path | str | None = None,
    ttl_s: float | None = None,
    deadline_s: float | None = None,
    force: bool = False,
    offline: bool | None = None,
    hotspotter: Callable[[tuple[float, float, float, float], date], dict[str, Any]] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Search, verify and cache fire news for ``day`` in ``region_id``.

    Raises :class:`KeyError` for an unknown region,
    :class:`~src.news.hyperbrowser.HyperbrowserNotConfigured` when no key is
    available, :class:`FireNewsTimeout` when the budget expires before any
    page can be verified, and :class:`~src.news.hyperbrowser.HyperbrowserError`
    when every search call fails.
    """
    region = regions.get_region(region_id)
    ttl = _env_float(CACHE_ENV, DEFAULT_CACHE_TTL_S) if ttl_s is None else ttl_s
    budget = _env_float(DEADLINE_ENV, DEFAULT_DEADLINE_S) if deadline_s is None else deadline_s
    if not force:
        cached = _read_cache(region.id, day, cache_dir, ttl)
        if cached is not None:
            return cached

    if offline is None:
        offline = safe.is_offline()
    if offline:
        raise FireNewsUnavailable(
            f"news search needs network access; OFFLINE=1 and no cached result "
            f"for {region.id} on {day.isoformat()}"
        )

    satellite = (hotspotter or _satellite_summary)(region.bbox, day)
    deadline = clock() + max(1.0, budget)
    client = client or HyperbrowserClient()
    queries = build_queries(day, region)

    hits: dict[str, SearchHit] = {}
    errors: list[HyperbrowserError] = []
    for query in queries:
        if clock() >= deadline:
            break
        try:
            for hit in client.search(query):
                hits.setdefault(hit.url, hit)
                if len(hits) >= MAX_CANDIDATES:
                    break
        except HyperbrowserError as exc:
            errors.append(exc)
        if len(hits) >= MAX_CANDIDATES:
            break

    if not hits:
        # Every query failing is an outage; one failing while the others
        # return nothing is still an honest (empty) result.
        if errors and len(errors) >= len(queries):
            raise errors[-1]
        return _empty_payload(day, region, satellite)

    candidates = list(hits.values())[:MAX_CANDIDATES]
    pool = ThreadPoolExecutor(max_workers=min(FETCH_WORKERS, len(candidates)))
    partial = False
    extracts: list[tuple[ArticleExtract, SearchHit]] = []
    try:
        futures = {
            pool.submit(
                client.fetch_article,
                hit.url,
                date=day.isoformat(),
                region_label=region.label,
                region_bbox=region.bbox,
            ): hit
            for hit in candidates
        }
        remaining = deadline - clock()
        try:
            for future in as_completed(futures, timeout=max(0.1, remaining)):
                hit = futures[future]
                try:
                    extract = future.result()
                except (HyperbrowserError, ValueError, KeyError):
                    continue
                extracts.append((extract, hit))
        except TimeoutError:
            partial = True
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    if partial and not extracts:
        raise FireNewsTimeout(
            f"the news search for {region.label} on {day.isoformat()} exceeded its "
            f"{budget:g} s budget"
        )

    seen: set[str] = set()
    results: list[VerifiedArticle] = []
    for extract, hit in extracts:
        article = _article(
            extract,
            hit,
            day=day,
            satellite_available=bool(satellite.get("available")),
            detections=int(satellite.get("detections") or 0),
        )
        if article is None or article.url in seen:
            continue
        seen.add(article.url)
        results.append(article)
        if len(results) >= MAX_RESULTS:
            break

    satellite = {
        **satellite,
        "agrees_with_news": (
            None
            if not satellite.get("available") or not results
            else int(satellite.get("detections") or 0) > 0
        ),
    }
    if not results:
        payload = _empty_payload(day, region, satellite, partial=partial)
    else:
        payload = {
            "date": day.isoformat(),
            "region": {"id": region.id, "label": region.label, "bbox": list(region.bbox)},
            "generated_at": _iso_timestamp(),
            "cached": False,
            "partial": partial,
            "count": len(results),
            "results": [
                {
                    "headline": article.headline,
                    "summary": article.summary,
                    "published_date": article.published_date,
                    "event_date": article.event_date,
                    "source_name": article.source_name,
                    "url": article.url,
                    "satellite_agreement": article.satellite_agreement,
                }
                for article in results
            ],
            "satellite": satellite,
            "message": None,
        }
    _write_cache(region.id, day, payload, cache_dir)
    return payload


__all__: Iterable[str] = (
    "CACHE_ENV",
    "DEADLINE_ENV",
    "DEFAULT_CACHE_TTL_S",
    "DEFAULT_DEADLINE_S",
    "FireNewsError",
    "FireNewsTimeout",
    "FireNewsUnavailable",
    "build_queries",
    "search_fire_news",
)
