"""Test A — Auth Foundation

Covers: POST /api/auth/google, GET /api/auth/me, PATCH /api/auth/me,
and get_current_user dependency behaviour.
Google token verification is mocked so no real Google call is made.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.auth import create_access_token, decode_access_token
from app.core.config import settings
from app.models.models import User, UserWatchlist
from tests.conftest import anon_headers, auth_headers

FAKE_GOOGLE_ID = "google-sub-12345"
FAKE_EMAIL = "testuser@gmail.com"
FAKE_ID_INFO = {"sub": FAKE_GOOGLE_ID, "email": FAKE_EMAIL}

# Patch target for google token verification used in api/auth.py
VERIFY_PATCH = "app.api.auth.id_token.verify_oauth2_token"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def google_login(client, session_id: str = "anon-sess-001"):
    with patch(VERIFY_PATCH, return_value=FAKE_ID_INFO), \
         patch.object(settings, "google_client_id", "fake-client-id"):
        resp = await client.post(
            "/api/auth/google",
            json={"credential": "fake-google-token", "session_id": session_id},
        )
    return resp


# ---------------------------------------------------------------------------
# POST /api/auth/google
# ---------------------------------------------------------------------------

async def test_google_login_creates_new_user(client):
    """Fresh Google login with no prior session creates a new authenticated user."""
    resp = await google_login(client, session_id="new-session-999")
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == FAKE_EMAIL
    assert data["user"]["is_anonymous"] is False


async def test_google_login_invalid_token_returns_401(client):
    with patch(VERIFY_PATCH, side_effect=ValueError("bad token")), \
         patch.object(settings, "google_client_id", "fake-client-id"):
        resp = await client.post(
            "/api/auth/google",
            json={"credential": "invalid", "session_id": "sess-x"},
        )
    assert resp.status_code == 401


async def test_google_login_promotes_anon_user(client, db_session):
    """If the anonymous session already has a User row, it gets promoted (google_id set)."""
    # Trigger anon user creation via GET /auth/me
    resp = await client.get("/api/auth/me", headers=anon_headers("promote-sess"))
    assert resp.status_code == 200
    anon_id = resp.json()["id"]

    # Now log in with Google using the same session
    resp = await google_login(client, session_id="promote-sess")
    assert resp.status_code == 200
    data = resp.json()

    # Same user id, now has email
    assert data["user"]["id"] == anon_id
    assert data["user"]["email"] == FAKE_EMAIL
    assert data["user"]["is_anonymous"] is False

    # Confirm in DB: session_id cleared, google_id set
    result = await db_session.execute(select(User).where(User.id == anon_id))
    user = result.scalar_one()
    assert user.google_id == FAKE_GOOGLE_ID
    assert user.session_id is None


async def test_google_login_merges_anon_watchlist(client, db_session):
    """
    If a Google account already exists and the anon user has watchlist entries,
    those entries migrate to the existing Google user.
    """
    # Create anon user + add a ticker to their watchlist
    await client.get("/api/auth/me", headers=anon_headers("merge-sess"))
    result = await db_session.execute(select(User).where(User.session_id == "merge-sess"))
    anon_user = result.scalar_one()
    db_session.add(UserWatchlist(user_id=anon_user.id, symbol="AAPL"))
    await db_session.commit()

    # First login: creates the Google user (promotes anon)
    resp1 = await google_login(client, session_id="merge-sess")
    google_user_id = resp1.json()["user"]["id"]

    # Second login from a NEW anon session — Google user already exists
    await client.get("/api/auth/me", headers=anon_headers("merge-sess-2"))
    result2 = await db_session.execute(select(User).where(User.session_id == "merge-sess-2"))
    anon2 = result2.scalar_one()
    db_session.add(UserWatchlist(user_id=anon2.id, symbol="MSFT"))
    await db_session.commit()

    resp2 = await google_login(client, session_id="merge-sess-2")
    assert resp2.status_code == 200
    assert resp2.json()["user"]["id"] == google_user_id

    # MSFT watchlist row should now belong to google_user
    wl = await db_session.execute(
        select(UserWatchlist).where(
            UserWatchlist.user_id == google_user_id,
            UserWatchlist.symbol == "MSFT",
        )
    )
    assert wl.scalar_one_or_none() is not None

    # Anon user 2 should be deleted
    deleted = await db_session.execute(select(User).where(User.id == anon2.id))
    assert deleted.scalar_one_or_none() is None


async def test_google_login_no_client_id_returns_503(client):
    with patch("app.api.auth.settings") as mock_settings:
        mock_settings.google_client_id = ""
        resp = await client.post(
            "/api/auth/google",
            json={"credential": "x", "session_id": "s"},
        )
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------

async def test_get_me_with_jwt_returns_authenticated_user(client):
    resp = await google_login(client, session_id="me-sess-1")
    token = resp.json()["access_token"]

    me = await client.get("/api/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == FAKE_EMAIL
    assert me.json()["is_anonymous"] is False


async def test_get_me_with_session_id_creates_anon_user(client, db_session):
    resp = await client.get("/api/auth/me", headers=anon_headers("fresh-anon"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_anonymous"] is True
    assert data["email"] is None

    # Called again with the same session_id → same user returned (not duplicated)
    resp2 = await client.get("/api/auth/me", headers=anon_headers("fresh-anon"))
    assert resp2.json()["id"] == data["id"]


async def test_get_me_no_auth_returns_401(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_get_me_expired_jwt_returns_401(client):
    # Forge a token with user_id that doesn't exist
    bad_token = create_access_token(99999)
    # Tamper with it to make it invalid
    resp = await client.get("/api/auth/me", headers=auth_headers(bad_token + "x"))
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /api/auth/me
# ---------------------------------------------------------------------------

async def test_patch_me_updates_display_name(client, db_session):
    resp = await google_login(client, session_id="patch-sess")
    token = resp.json()["access_token"]
    user_id = resp.json()["user"]["id"]

    patch_resp = await client.patch(
        "/api/auth/me",
        json={"display_name": "Alice"},
        headers=auth_headers(token),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["display_name"] == "Alice"

    # Confirm in DB
    result = await db_session.execute(select(User).where(User.id == user_id))
    assert result.scalar_one().display_name == "Alice"


async def test_patch_me_strips_whitespace(client):
    resp = await google_login(client, session_id="strip-sess")
    token = resp.json()["access_token"]

    patch_resp = await client.patch(
        "/api/auth/me",
        json={"display_name": "  Bob  "},
        headers=auth_headers(token),
    )
    assert patch_resp.json()["display_name"] == "Bob"


# ---------------------------------------------------------------------------
# JWT unit tests (no HTTP)
# ---------------------------------------------------------------------------

def test_create_and_decode_token():
    token = create_access_token(42)
    assert decode_access_token(token) == 42


def test_decode_invalid_token_returns_none():
    assert decode_access_token("not.a.jwt") is None


def test_decode_tampered_token_returns_none():
    token = create_access_token(1)
    assert decode_access_token(token[:-4] + "xxxx") is None
