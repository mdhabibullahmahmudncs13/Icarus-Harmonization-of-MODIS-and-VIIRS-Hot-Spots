"""Fire-news agent: strict filtering, caching, failures and the API contract.

No test touches the network. The agent takes an injected client, so query
building, verification, the cache and the satellite block are exercised
directly; the HTTP client's parsing is exercised with a stub transport.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.news import agent as news_agent
from src.news.hyperbrowser import (
    ArticleExtract,
    HyperbrowserClient,
    HyperbrowserError,
    HyperbrowserNotConfigured,
    SearchHit,
    load_api_key,
    normalize_date,
    normalize_url,
    require_api_key,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((REPO_ROOT / "docs" / "contract.schema.json").read_text())

DAY = date(2024, 6, 15)


def assert_matches(definition: str, payload: dict) -> None:
    defs = CONTRACT["$defs"]
    jsonschema.Draft202012Validator(
        {"$ref": f"#/$defs/{definition}", "$defs": defs}
    ).validate(payload)


def article(
    url: str,
    *,
    published: str | None = "2024-06-15",
    event: str | None = "2024-06-15",
    in_region: bool = True,
    is_fire: bool = True,
    headline: str = "Forest fire forces evacuations",
    summary: str = "A forest fire burned near the district on the day.",
    source: str = "Example News",
) -> ArticleExtract:
    return ArticleExtract(
        url=url,
        headline=headline,
        summary=summary,
        published_date=published,
        event_date=event,
        source_name=source,
        in_region=in_region,
        is_fire_news=is_fire,
    )


class FakeClient:
    """A Hyperbrowser stand-in: fixed hits, fixed extractions, recorded queries."""

    def __init__(
        self,
        hits: list[SearchHit],
        extracts: dict[str, ArticleExtract],
        *,
        fetch_error: Exception | None = None,
        fail_urls: set[str] | None = None,
    ) -> None:
        self.hits = hits
        self.extracts = extracts
        self.fetch_error = fetch_error
        self.fail_urls = fail_urls or set()
        self.queries: list[str] = []

    def search(self, query: str) -> list[SearchHit]:
        self.queries.append(query)
        return self.hits

    def fetch_article(self, url: str, **_kwargs):
        if self.fetch_error is not None:
            raise self.fetch_error
        if url in self.fail_urls:
            raise HyperbrowserError(f"could not read {url}")
        return self.extracts[url]


def hotspots(detections: int = 12, cells: int = 4) -> dict:
    return {
        "available": True,
        "detections": detections,
        "active_cells": cells,
        "agrees_with_news": None,
    }


# --------------------------------------------------------------------------
# Verification and the result shape
# --------------------------------------------------------------------------


def test_finds_only_articles_that_match_the_day_and_region(tmp_path):
    hits = [
        SearchHit("Fire in the south", "https://news.example/fire"),
        SearchHit("Wrong day", "https://news.example/other-day"),
        SearchHit("Elsewhere", "https://news.example/elsewhere"),
    ]
    client = FakeClient(
        hits,
        {
            "https://news.example/fire": article("https://news.example/fire"),
            "https://news.example/other-day": article(
                "https://news.example/other-day", published="2024-06-14", event="2024-06-14"
            ),
            "https://news.example/elsewhere": article(
                "https://news.example/elsewhere", in_region=False
            ),
        },
    )

    payload = news_agent.search_fire_news(
        DAY,
        "SOUTH_ASIA",
        client=client,
        cache_dir=tmp_path,
        offline=False,
        hotspotter=lambda _bbox, _day: hotspots(),
    )

    assert_matches("fireNews", payload)
    assert payload["count"] == 1
    assert payload["cached"] is False
    result = payload["results"][0]
    assert result["headline"]
    assert result["summary"]
    assert result["published_date"] == "2024-06-15"
    assert result["source_name"] == "Example News"
    assert result["url"] == "https://news.example/fire"
    assert result["satellite_agreement"] == "agrees"
    assert payload["satellite"]["agrees_with_news"] is True
    # The queries include the region and the day, and one local-language term.
    assert any("SOUTH_ASIA" not in query and "South Asia" in query for query in client.queries)
    assert any("2024-06-15" in query for query in client.queries)
    assert any(
        term in query
        for query in client.queries
        for term in ("जंगल", "দাবানল", "جنگل")
    )


def test_a_report_whose_event_date_matches_is_kept_with_its_publication_date(tmp_path):
    client = FakeClient(
        [SearchHit("Fire", "https://news.example/fire")],
        {
            "https://news.example/fire": article(
                "https://news.example/fire",
                published="2024-06-16",
                event="2024-06-15",
            )
        },
    )
    payload = news_agent.search_fire_news(
        DAY,
        "SOUTH_ASIA",
        client=client,
        cache_dir=tmp_path,
        offline=False,
        hotspotter=lambda _bbox, _day: hotspots(detections=0, cells=0),
    )
    assert payload["count"] == 1
    assert payload["results"][0]["published_date"] == "2024-06-16"
    assert payload["results"][0]["satellite_agreement"] == "no_detections"
    assert payload["satellite"]["agrees_with_news"] is False


def test_a_page_without_a_publication_date_is_dropped(tmp_path):
    client = FakeClient(
        [SearchHit("Fire", "https://news.example/fire")],
        {"https://news.example/fire": article("https://news.example/fire", published=None)},
    )
    payload = news_agent.search_fire_news(
        DAY,
        "SOUTH_ASIA",
        client=client,
        cache_dir=tmp_path,
        offline=False,
        hotspotter=lambda _bbox, _day: hotspots(),
    )
    assert payload["count"] == 0


def test_a_page_without_a_source_url_or_summary_is_dropped(tmp_path):
    no_summary = article("https://news.example/empty", summary="")
    client = FakeClient(
        [SearchHit("Fire without detail", "https://news.example/empty", description="")],
        {"https://news.example/empty": no_summary},
    )
    payload = news_agent.search_fire_news(
        DAY,
        "SOUTH_ASIA",
        client=client,
        cache_dir=tmp_path,
        offline=False,
        hotspotter=lambda _bbox, _day: hotspots(),
    )
    assert payload["count"] == 0


def test_no_hits_returns_an_honest_empty_state(tmp_path):
    payload = news_agent.search_fire_news(
        DAY,
        "EUROPE",
        client=FakeClient([], {}),
        cache_dir=tmp_path,
        offline=False,
        hotspotter=lambda _bbox, _day: hotspots(detections=3, cells=1),
    )
    assert_matches("fireNews", payload)
    assert payload["count"] == 0
    assert payload["results"] == []
    assert "No fire reports found" in payload["message"]
    # Detections exist but no article does: there is nothing to agree with.
    assert payload["satellite"]["agrees_with_news"] is None


def test_one_unreadable_page_does_not_fail_the_search(tmp_path):
    client = FakeClient(
        [
            SearchHit("Unreadable", "https://news.example/broken"),
            SearchHit("Fire", "https://news.example/fire"),
        ],
        {"https://news.example/fire": article("https://news.example/fire")},
        fail_urls={"https://news.example/broken"},
    )
    payload = news_agent.search_fire_news(
        DAY,
        "SOUTH_ASIA",
        client=client,
        cache_dir=tmp_path,
        offline=False,
        hotspotter=lambda _bbox, _day: hotspots(),
    )
    assert payload["count"] == 1


def test_the_budget_expiring_before_any_page_is_read_is_a_timeout(tmp_path):
    client = FakeClient(
        [SearchHit("Fire", "https://news.example/fire")], {}, fetch_error=TimeoutError("slow")
    )
    with pytest.raises(news_agent.FireNewsTimeout):
        news_agent.search_fire_news(
            DAY,
            "SOUTH_ASIA",
            client=client,
            cache_dir=tmp_path,
            offline=False,
            hotspotter=lambda _bbox, _day: hotspots(),
        )


# --------------------------------------------------------------------------
# Cache: per (date, region), and useful offline
# --------------------------------------------------------------------------


def test_a_second_request_is_served_from_the_cache(tmp_path):
    hits = [SearchHit("Fire", "https://news.example/fire")]
    extracts = {"https://news.example/fire": article("https://news.example/fire")}
    first = news_agent.search_fire_news(
        DAY,
        "SOUTH_ASIA",
        client=FakeClient(hits, extracts),
        cache_dir=tmp_path,
        offline=False,
        hotspotter=lambda _bbox, _day: hotspots(),
    )
    assert first["cached"] is False

    second_client = FakeClient([], {})
    second = news_agent.search_fire_news(
        DAY,
        "SOUTH_ASIA",
        client=second_client,
        cache_dir=tmp_path,
        offline=False,
    )
    assert second["cached"] is True
    assert second["count"] == first["count"]
    assert second_client.queries == []


def test_the_cache_is_scoped_by_region_and_date(tmp_path):
    hits = [SearchHit("Fire", "https://news.example/fire")]
    extracts = {"https://news.example/fire": article("https://news.example/fire")}
    news_agent.search_fire_news(
        DAY,
        "SOUTH_ASIA",
        client=FakeClient(hits, extracts),
        cache_dir=tmp_path,
        offline=False,
        hotspotter=lambda _bbox, _day: hotspots(),
    )
    other = FakeClient([], {})
    payload = news_agent.search_fire_news(
        date(2024, 6, 16),
        "SOUTH_ASIA",
        client=other,
        cache_dir=tmp_path,
        offline=False,
        hotspotter=lambda _bbox, _day: hotspots(),
    )
    assert payload["count"] == 0
    assert other.queries, "a different day must search again"


def test_offline_serves_a_cached_answer_and_refuses_without_one(tmp_path):
    hits = [SearchHit("Fire", "https://news.example/fire")]
    extracts = {"https://news.example/fire": article("https://news.example/fire")}
    news_agent.search_fire_news(
        DAY,
        "SOUTH_ASIA",
        client=FakeClient(hits, extracts),
        cache_dir=tmp_path,
        offline=False,
        hotspotter=lambda _bbox, _day: hotspots(),
    )
    cached = news_agent.search_fire_news(
        DAY, "SOUTH_ASIA", cache_dir=tmp_path, offline=True
    )
    assert cached["cached"] is True

    with pytest.raises(news_agent.FireNewsUnavailable):
        news_agent.search_fire_news(
            date(2024, 6, 17), "SOUTH_ASIA", cache_dir=tmp_path, offline=True
        )


# --------------------------------------------------------------------------
# Hyperbrowser transport (stubbed; no key, no network)
# --------------------------------------------------------------------------


class StubResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload


def test_search_parses_results_and_normalizes_bare_hosts():
    calls: list[dict] = []

    def poster(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return StubResponse(
            {
                "status": "completed",
                "data": {
                    "results": [
                        {"title": "Fire report", "url": "news.example/a", "description": "d"}
                    ]
                },
            }
        )

    client = HyperbrowserClient(api_key="test-key", poster=poster)
    hits = client.search("wildfire South Asia 2024-06-15")
    assert hits == [SearchHit("Fire report", "https://news.example/a", "d")]
    assert calls[0]["url"].endswith("/api/web/search")
    assert calls[0]["headers"]["x-api-key"] == "test-key"


def test_fetch_extracts_the_schema_fields():
    def poster(_url, **_kwargs):
        return StubResponse(
            {
                "status": "completed",
                "data": {
                    "metadata": {
                        "title": "Page title",
                        "siteName": "Daily",
                        "sourceURL": "https://news.example/a",
                    },
                    "json": {
                        "is_fire_news": True,
                        "in_region": True,
                        "headline": "Forest fire",
                        "summary": "A fire burned.",
                        "published_date": "2024-06-15T09:00:00Z",
                        "event_date": "2024-06-15",
                        "source_name": "Daily",
                        "locations": ["Dhaka"],
                    },
                },
            }
        )

    article_out = HyperbrowserClient(api_key="test-key", poster=poster).fetch_article(
        "https://news.example/a",
        date="2024-06-15",
        region_label="South Asia",
        region_bbox=(54.0, 5.5, 102.0, 40.0),
    )
    assert article_out.is_fire_news and article_out.in_region
    assert article_out.published_date == "2024-06-15"
    assert article_out.headline == "Forest fire"
    assert article_out.source_name == "Daily"


def test_upstream_failures_are_reported_as_errors():
    def poster(_url, **_kwargs):
        return StubResponse({"error": "nope"}, status=500)

    with pytest.raises(HyperbrowserError, match="HTTP 500"):
        HyperbrowserClient(api_key="test-key", poster=poster).search("q")


def test_a_missing_key_is_a_configuration_error_not_an_empty_search():
    with pytest.raises(HyperbrowserNotConfigured):
        HyperbrowserClient(api_key="")
    assert load_api_key({"HYPERBROWSER_API_KEY": " abc "}) == "abc"
    assert require_api_key({"HYPERBROWSER_API_KEY": "abc"}) == "abc"


def test_url_and_date_normalization_never_invents_a_value():
    assert normalize_url("news.example/a") == "https://news.example/a"
    assert normalize_date("2024-06-15T09:00:00Z") == "2024-06-15"
    assert normalize_date("last Tuesday") is None
    assert normalize_date(None) is None


# --------------------------------------------------------------------------
# POST /api/fire-news
# --------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


SAMPLE = {
    "date": "2024-06-15",
    "region": {"id": "SOUTH_ASIA", "label": "South Asia", "bbox": [54.0, 5.5, 102.0, 40.0]},
    "generated_at": "2026-11-14T00:00:00Z",
    "cached": False,
    "partial": False,
    "count": 0,
    "results": [],
    "satellite": {
        "available": True,
        "detections": 0,
        "active_cells": 0,
        "agrees_with_news": None,
    },
    "message": "No fire reports found for South Asia on 2024-06-15.",
}


def test_post_fire_news_returns_the_contract_payload(client, monkeypatch):
    monkeypatch.setattr(news_agent, "search_fire_news", lambda *_a, **_k: SAMPLE)
    response = client.post("/api/fire-news", json={"date": "2024-06-15", "region": "SOUTH_ASIA"})
    assert response.status_code == 200, response.text
    assert_matches("fireNews", response.json())


def test_post_fire_news_is_also_on_the_versioned_prefix(client, monkeypatch):
    monkeypatch.setattr(news_agent, "search_fire_news", lambda *_a, **_k: SAMPLE)
    response = client.post(
        "/api/v1/fire-news", json={"date": "2024-06-15", "region": "SOUTH_ASIA"}
    )
    assert response.status_code == 200, response.text


def test_post_fire_news_passes_refresh_through(client, monkeypatch):
    seen: dict = {}

    def fake(day, region, **kwargs):
        seen.update({"day": day, "region": region, **kwargs})
        return SAMPLE

    monkeypatch.setattr(news_agent, "search_fire_news", fake)
    response = client.post(
        "/api/fire-news",
        json={"date": "2024-06-15", "region": "SOUTH_ASIA", "refresh": True},
    )
    assert response.status_code == 200
    assert seen["region"] == "SOUTH_ASIA"
    assert seen["force"] is True


def test_post_fire_news_refuses_an_unknown_region(client):
    response = client.post("/api/fire-news", json={"date": "2024-06-15", "region": "ATLANTIS"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "unknown_region"
    assert body["field"] == "region"
    assert "ATLANTIS" in body["message"]


def test_post_fire_news_requires_a_date(client):
    response = client.post("/api/fire-news", json={"region": "SOUTH_ASIA"})
    assert response.status_code == 422
    assert response.json()["field"] == "date"


@pytest.mark.parametrize(
    "error,status,code",
    [
        (HyperbrowserNotConfigured("no key"), 503, "news_unconfigured"),
        (news_agent.FireNewsUnavailable("offline"), 503, "news_unavailable"),
        (news_agent.FireNewsTimeout("too slow"), 504, "news_timeout"),
        (HyperbrowserError("upstream"), 502, "news_upstream_error"),
    ],
)
def test_post_fire_news_maps_failures_to_contract_errors(client, monkeypatch, error, status, code):
    def fail(*_a, **_k):
        raise error

    monkeypatch.setattr(news_agent, "search_fire_news", fail)
    response = client.post("/api/fire-news", json={"date": "2024-06-15", "region": "SOUTH_ASIA"})
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "message", "field"}
    assert body["code"] == code
