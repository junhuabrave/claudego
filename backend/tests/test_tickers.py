"""Test B — Per-User Data Layer

Covers: GET/POST/DELETE /api/tickers user isolation,
POST /api/chat scoped to user's watchlist.
Quote fetching is mocked so no network calls are made.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.models import Ticker, UserWatchlist
from tests.conftest import anon_headers, auth_headers

MOCK_QUOTE = {"price": 150.0, "change_percent": 1.5}
QUOTE_PATCH = "app.api.routes.get_quote_provider"


def _mock_provider():
    provider = AsyncMock()
    provider.fetch_quote = AsyncMock(return_value=MOCK_QUOTE)
    return provider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def add_ticker(client, headers: dict, symbol: str):
    with patch(QUOTE_PATCH, return_value=_mock_provider()):
        return await client.post("/api/tickers", json={"symbol": symbol}, headers=headers)


# ---------------------------------------------------------------------------
# GET /api/tickers
# ---------------------------------------------------------------------------

async def test_list_tickers_empty_for_new_user(client):
    resp = await client.get("/api/tickers", headers=anon_headers("list-empty"))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_tickers_returns_only_current_users_tickers(client):
    user_a = anon_headers("user-a-tickers")
    user_b = anon_headers("user-b-tickers")

    await add_ticker(client, user_a, "AAPL")
    await add_ticker(client, user_b, "MSFT")

    resp_a = await client.get("/api/tickers", headers=user_a)
    resp_b = await client.get("/api/tickers", headers=user_b)

    symbols_a = [t["symbol"] for t in resp_a.json()]
    symbols_b = [t["symbol"] for t in resp_b.json()]

    assert symbols_a == ["AAPL"]
    assert symbols_b == ["MSFT"]


async def test_list_tickers_requires_auth(client):
    resp = await client.get("/api/tickers")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/tickers
# ---------------------------------------------------------------------------

async def test_add_ticker_creates_watchlist_row(client, db_session):
    headers = anon_headers("add-ticker-sess")
    resp = await add_ticker(client, headers, "GOOG")
    assert resp.status_code == 201
    assert resp.json()["symbol"] == "GOOG"

    # UserWatchlist row exists
    result = await db_session.execute(
        select(UserWatchlist).where(UserWatchlist.symbol == "GOOG")
    )
    wl = result.scalar_one_or_none()
    assert wl is not None


async def test_add_same_symbol_two_users_creates_one_ticker_row(client, db_session):
    """Two users watching the same symbol → one Ticker row, two UserWatchlist rows."""
    headers_a = anon_headers("shared-sym-a")
    headers_b = anon_headers("shared-sym-b")

    await add_ticker(client, headers_a, "TSLA")
    await add_ticker(client, headers_b, "TSLA")

    # Only one global Ticker row
    result = await db_session.execute(select(Ticker).where(Ticker.symbol == "TSLA"))
    tickers = result.scalars().all()
    assert len(tickers) == 1

    # Two UserWatchlist rows
    wl_result = await db_session.execute(
        select(UserWatchlist).where(UserWatchlist.symbol == "TSLA")
    )
    assert len(wl_result.scalars().all()) == 2


async def test_add_duplicate_ticker_same_user_returns_409(client):
    headers = anon_headers("dup-ticker-sess")
    await add_ticker(client, headers, "AAPL")
    resp = await add_ticker(client, headers, "AAPL")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# DELETE /api/tickers/{symbol}
# ---------------------------------------------------------------------------

async def test_remove_ticker_deletes_only_from_users_watchlist(client, db_session):
    headers_a = anon_headers("del-a")
    headers_b = anon_headers("del-b")

    await add_ticker(client, headers_a, "NVDA")
    await add_ticker(client, headers_b, "NVDA")

    # User A removes NVDA
    resp = await client.delete("/api/tickers/NVDA", headers=headers_a)
    assert resp.status_code == 204

    # User A's list is empty; User B still has NVDA
    resp_a = await client.get("/api/tickers", headers=headers_a)
    resp_b = await client.get("/api/tickers", headers=headers_b)
    assert resp_a.json() == []
    assert any(t["symbol"] == "NVDA" for t in resp_b.json())


async def test_remove_ticker_not_in_watchlist_returns_404(client):
    headers = anon_headers("rm-404-sess")
    resp = await client.delete("/api/tickers/FAKE", headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/chat — scoped to user
# ---------------------------------------------------------------------------

async def test_chat_list_shows_only_users_tickers(client):
    headers_a = anon_headers("chat-a")
    headers_b = anon_headers("chat-b")

    await add_ticker(client, headers_a, "META")
    await add_ticker(client, headers_b, "AMZN")

    resp = await client.post("/api/chat", json={"message": "list"}, headers=headers_a)
    assert resp.status_code == 200
    assert "META" in resp.json()["reply"]
    assert "AMZN" not in resp.json()["reply"]


async def test_chat_add_ticker_adds_to_users_watchlist(client):
    headers = anon_headers("chat-add-sess")
    with patch(QUOTE_PATCH, return_value=_mock_provider()):
        resp = await client.post(
            "/api/chat", json={"message": "add ORCL"}, headers=headers
        )
    assert resp.status_code == 200

    tickers = await client.get("/api/tickers", headers=headers)
    assert any(t["symbol"] == "ORCL" for t in tickers.json())
