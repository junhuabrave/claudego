"""Test D — News Feed Endpoints

Covers: GET /api/news with limit, category filtering, empty state,
and ordering by published_at descending.
"""

import datetime

import pytest
from sqlalchemy import select

from app.models.models import NewsArticle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_article(
    external_id: str,
    headline: str = "Test headline",
    category: str = "general",
    published_at: datetime.datetime | None = None,
) -> NewsArticle:
    return NewsArticle(
        external_id=external_id,
        headline=headline,
        summary="Test summary",
        source="test-source",
        url="https://example.com",
        image_url="",
        category=category,
        related_tickers="AAPL",
        sentiment="neutral",
        published_at=published_at or datetime.datetime.now(datetime.timezone.utc),
    )


async def _seed_articles(db_session, count: int = 5, category: str = "general"):
    """Insert multiple news articles into the test DB."""
    base_time = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
    articles = []
    for i in range(count):
        article = _make_article(
            external_id=f"test-{category}-{i}",
            headline=f"Headline {i}",
            category=category,
            published_at=base_time + datetime.timedelta(hours=i),
        )
        db_session.add(article)
        articles.append(article)
    await db_session.commit()
    return articles


# ---------------------------------------------------------------------------
# GET /api/news
# ---------------------------------------------------------------------------

async def test_list_news_returns_empty_when_no_articles(client):
    resp = await client.get("/api/news")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_news_returns_articles(client, db_session):
    await _seed_articles(db_session, count=3)
    resp = await client.get("/api/news")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


async def test_list_news_ordered_by_published_at_descending(client, db_session):
    """Most recent article should appear first."""
    await _seed_articles(db_session, count=5)
    resp = await client.get("/api/news")
    data = resp.json()
    dates = [item["published_at"] for item in data]
    assert dates == sorted(dates, reverse=True)


async def test_list_news_respects_limit(client, db_session):
    await _seed_articles(db_session, count=10)
    resp = await client.get("/api/news", params={"limit": 3})
    assert resp.status_code == 200
    assert len(resp.json()) == 3


async def test_list_news_default_limit_is_50(client, db_session):
    """Default limit is 50 — with 5 articles, all are returned."""
    await _seed_articles(db_session, count=5)
    resp = await client.get("/api/news")
    assert len(resp.json()) == 5


async def test_list_news_filters_by_category(client, db_session):
    await _seed_articles(db_session, count=3, category="general")
    await _seed_articles(db_session, count=2, category="technology")

    resp = await client.get("/api/news", params={"category": "technology"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(article["category"] == "technology" for article in data)


async def test_list_news_category_filter_no_match(client, db_session):
    await _seed_articles(db_session, count=3, category="general")
    resp = await client.get("/api/news", params={"category": "crypto"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_news_response_schema(client, db_session):
    """Verify response includes all expected fields from NewsArticleResponse."""
    await _seed_articles(db_session, count=1)
    resp = await client.get("/api/news")
    article = resp.json()[0]
    expected_fields = {
        "id", "external_id", "headline", "summary", "source",
        "url", "image_url", "category", "related_tickers",
        "sentiment", "published_at", "created_at",
    }
    assert expected_fields.issubset(set(article.keys()))


async def test_list_news_does_not_require_auth(client):
    """News endpoint is public — no auth headers needed."""
    resp = await client.get("/api/news")
    assert resp.status_code == 200
