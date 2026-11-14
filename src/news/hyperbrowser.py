"""Hyperbrowser web APIs: search for candidate pages, fetch one as structured JSON.

Two documented endpoints are used, with the ``x-api-key`` header and the key
read from the environment (``HYPERBROWSER_API_KEY``), never hardcoded:

* ``POST /api/web/search`` — query the web, get ``{title, url, description}``.
* ``POST /api/web/fetch`` — render one page and return an extraction. The
  ``json`` output asks Hyperbrowser to extract fields against a JSON Schema,
  so the date/region verdict comes from the page, not from a guessed pattern.

The HTTP transport is injectable (``poster``), which is how the tests exercise
response parsing and error mapping without a key or a network call.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import requests

API_BASE = os.environ.get("HYPERBROWSER_API_BASE", "https://api.hyperbrowser.ai").rstrip("/")
API_KEY_ENV = "HYPERBROWSER_API_KEY"
SEARCH_PATH = "/api/web/search"
FETCH_PATH = "/api/web/fetch"
DEFAULT_TIMEOUT_S = 20.0

_ISO_DATE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")
_SCHEME = re.compile(r"^https?://", re.IGNORECASE)

#: The shape the extractor must return. Every field is present; unknown
#: values are explicitly null rather than omitted, so a missing date cannot
#: be mistaken for a match.
EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_fire_news": {"type": "boolean"},
        "in_region": {"type": "boolean"},
        "headline": {"type": ["string", "null"]},
        "summary": {"type": ["string", "null"]},
        "published_date": {"type": ["string", "null"]},
        "event_date": {"type": ["string", "null"]},
        "source_name": {"type": ["string", "null"]},
        "locations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "is_fire_news",
        "in_region",
        "headline",
        "summary",
        "published_date",
        "event_date",
        "source_name",
        "locations",
    ],
    "additionalProperties": False,
}


class HyperbrowserError(RuntimeError):
    """The upstream API refused the request or answered unusably."""


class HyperbrowserNotConfigured(HyperbrowserError):
    """No Hyperbrowser API key is available, so no search can run."""


@dataclass(frozen=True)
class SearchHit:
    """One search result: enough to decide whether the page is worth a fetch."""

    title: str
    url: str
    description: str = ""


@dataclass(frozen=True)
class ArticleExtract:
    """What one page says about itself, as extracted against the schema."""

    url: str
    headline: str | None
    summary: str | None
    published_date: str | None
    event_date: str | None
    source_name: str | None
    in_region: bool
    is_fire_news: bool
    locations: tuple[str, ...] = field(default_factory=tuple)
    page_title: str | None = None


def normalize_url(url: str) -> str:
    """A clickable absolute URL, adding ``https://`` when the API omits it."""
    value = str(url or "").strip()
    if not value:
        return ""
    if value.startswith("//"):
        return f"https:{value}"
    if not _SCHEME.match(value):
        return f"https://{value}"
    return value


def normalize_date(value: Any) -> str | None:
    """The first ISO date in ``value``, or ``None``.

    The extractor is asked for ``YYYY-MM-DD``; this also accepts a full ISO
    timestamp or a date embedded in a sentence. Anything it cannot read stays
    ``None`` and is rejected by the agent rather than guessed.
    """
    if value is None:
        return None
    match = _ISO_DATE.search(str(value))
    return match.group(1) if match else None


def source_from_url(url: str) -> str:
    """The site name a reader would recognise: the hostname without ``www``."""
    host = re.sub(r"^https?://", "", normalize_url(url)).split("/")[0]
    return host[4:] if host.startswith("www.") else host


def _dotenv_value(name: str) -> str:
    """Read ``.env`` through the acquisition layer's existing reader."""
    try:
        from src.acquire.firms import read_dotenv
    except Exception:  # pragma: no cover - the reader is always importable
        return ""
    return read_dotenv().get(name, "")


def load_api_key(environ: Mapping[str, str] | None = None) -> str:
    """The key from the process environment, then from ``.env``."""
    env = os.environ if environ is None else environ
    key = str(env.get(API_KEY_ENV, "")).strip()
    return key or _dotenv_value(API_KEY_ENV).strip()


def require_api_key(environ: Mapping[str, str] | None = None) -> str:
    """The key, or the exact place to get one."""
    key = load_api_key(environ)
    if not key:
        raise HyperbrowserNotConfigured(
            "HYPERBROWSER_API_KEY is not set. Create a key at "
            "https://www.hyperbrowser.ai and put it in .env (see .env.example)."
        )
    return key


class HyperbrowserClient:
    """Search and fetch through Hyperbrowser's web API.

    ``poster`` defaults to :func:`requests.post`; tests pass a stub returning
    a small response object. Each call carries its own timeout, so one slow
    page cannot hold the request open indefinitely.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        poster: Callable[..., Any] | None = None,
        base_url: str = API_BASE,
    ) -> None:
        self.api_key = api_key if api_key is not None else require_api_key()
        if not self.api_key:
            raise HyperbrowserNotConfigured("HYPERBROWSER_API_KEY is empty")
        self.timeout_s = float(timeout_s)
        self._post = poster or requests.post
        self.base_url = base_url.rstrip("/")

    # -- transport --------------------------------------------------------

    def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._post(
                f"{self.base_url}{path}",
                json=payload,
                headers={"x-api-key": self.api_key, "Content-Type": "application/json"},
                timeout=self.timeout_s,
            )
        except requests.RequestException as exc:
            raise HyperbrowserError(f"Hyperbrowser {path} request failed: {exc}") from exc

        status = int(getattr(response, "status_code", 0))
        if status != 200:
            text = str(getattr(response, "text", ""))[:240]
            raise HyperbrowserError(f"Hyperbrowser {path} returned HTTP {status}: {text}")
        try:
            body = response.json()
        except ValueError as exc:
            raise HyperbrowserError(f"Hyperbrowser {path} returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise HyperbrowserError(f"Hyperbrowser {path} returned a non-object body")
        state = body.get("status")
        if state not in (None, "completed"):
            raise HyperbrowserError(
                f"Hyperbrowser {path} did not complete (status={state!r}): "
                f"{str(body.get('error') or '')[:160]}"
            )
        return body

    # -- API surface ------------------------------------------------------

    def search(self, query: str, *, page: int = 1) -> list[SearchHit]:
        """Run one web search and return usable results in ranked order."""
        body = self._request(SEARCH_PATH, {"query": query[:500], "page": page})
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        raw_results = data.get("results") if isinstance(data.get("results"), list) else []
        hits: list[SearchHit] = []
        for raw in raw_results:
            if not isinstance(raw, dict):
                continue
            url = normalize_url(str(raw.get("url") or ""))
            title = str(raw.get("title") or "").strip()
            if url and title:
                hits.append(SearchHit(title, url, str(raw.get("description") or "").strip()))
        return hits

    def fetch_article(
        self,
        url: str,
        *,
        date: str,
        region_label: str,
        region_bbox: tuple[float, float, float, float],
    ) -> ArticleExtract:
        """Render one page and extract the fields the filter needs."""
        west, south, east, north = region_bbox
        prompt = (
            "Read this page and decide whether it is news about an actual fire "
            f"(wildfire, forest fire, bushfire, etc.) in {region_label} on {date}. "
            f"The region's bounding box is west={west}, south={south}, "
            f"east={east}, north={north}. Set is_fire_news only when the page "
            "reports a real fire event, not a general explainer, an alert page "
            "with no event, or a different hazard. Set in_region only when the "
            "fire is reported inside that area. Put publication date in "
            "published_date and the fire's date in event_date, both YYYY-MM-DD. "
            "Never invent a date, location, source or summary: use null when the "
            "page does not state it. The summary must be one or two factual "
            "sentences taken from the page."
        )
        body = self._request(
            FETCH_PATH,
            {
                "url": url,
                "outputs": {
                    "formats": [
                        {"type": "json", "prompt": prompt, "schema": EXTRACTION_SCHEMA}
                    ]
                },
            },
        )
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        extraction = data.get("json") or data.get("json_") or {}
        if not isinstance(extraction, dict):
            extraction = {}
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

        def text(key: str) -> str | None:
            value = extraction.get(key)
            if value in (None, ""):
                return None
            cleaned = str(value).strip()
            # A model that writes the word "null" instead of emitting null
            # must not turn it into a headline or a source name.
            return cleaned if cleaned.lower() not in {"null", "none", "n/a"} else None

        locations = extraction.get("locations")
        return ArticleExtract(
            url=normalize_url(str(metadata.get("sourceURL") or url)),
            headline=text("headline") or (str(metadata.get("title") or "").strip() or None),
            summary=text("summary") or (str(metadata.get("description") or "").strip() or None),
            published_date=normalize_date(extraction.get("published_date")),
            event_date=normalize_date(extraction.get("event_date")),
            source_name=text("source_name")
            or (str(metadata.get("siteName") or "").strip() or None),
            in_region=bool(extraction.get("in_region")),
            is_fire_news=bool(extraction.get("is_fire_news")),
            locations=tuple(str(value).strip() for value in locations if str(value).strip())
            if isinstance(locations, list)
            else (),
            page_title=str(metadata.get("title") or "").strip() or None,
        )


__all__ = (
    "API_BASE",
    "API_KEY_ENV",
    "DEFAULT_TIMEOUT_S",
    "EXTRACTION_SCHEMA",
    "ArticleExtract",
    "HyperbrowserClient",
    "HyperbrowserError",
    "HyperbrowserNotConfigured",
    "SearchHit",
    "load_api_key",
    "normalize_date",
    "normalize_url",
    "require_api_key",
    "source_from_url",
)
