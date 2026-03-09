"""Test E — IPO Calendar Endpoints

Covers: GET /api/ipos date filtering (2-week window),
POST/GET/DELETE /api/reminders for IPO event reminders.
"""

import datetime

import pytest
from sqlalchemy import select

from app.models.models import IPOEvent, Reminder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ipo(
    external_id: str,
    company_name: str = "TestCo",
    symbol: str = "TEST",
    expected_date: datetime.date | None = None,
) -> IPOEvent:
    return IPOEvent(
        external_id=external_id,
        company_name=company_name,
        symbol=symbol,
        exchange="NASDAQ",
        price_range="10-15",
        shares_offered="1000000",
        expected_date=expected_date or datetime.date.today() + datetime.timedelta(days=3),
        status="expected",
    )


# ---------------------------------------------------------------------------
# GET /api/ipos
# ---------------------------------------------------------------------------

async def test_list_ipos_returns_empty_when_no_events(client):
    resp = await client.get("/api/ipos")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_ipos_returns_events_within_two_weeks(client, db_session):
    today = datetime.date.today()
    ipo_in_range = _make_ipo("ipo-1", expected_date=today + datetime.timedelta(days=5))
    db_session.add(ipo_in_range)
    await db_session.commit()

    resp = await client.get("/api/ipos")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["company_name"] == "TestCo"


async def test_list_ipos_excludes_events_beyond_two_weeks(client, db_session):
    today = datetime.date.today()
    ipo_far = _make_ipo("ipo-far", expected_date=today + datetime.timedelta(days=30))
    db_session.add(ipo_far)
    await db_session.commit()

    resp = await client.get("/api/ipos")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_ipos_excludes_past_events(client, db_session):
    today = datetime.date.today()
    ipo_past = _make_ipo("ipo-past", expected_date=today - datetime.timedelta(days=2))
    db_session.add(ipo_past)
    await db_session.commit()

    resp = await client.get("/api/ipos")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_ipos_ordered_by_date(client, db_session):
    today = datetime.date.today()
    ipo_later = _make_ipo("ipo-later", expected_date=today + datetime.timedelta(days=10))
    ipo_sooner = _make_ipo("ipo-sooner", expected_date=today + datetime.timedelta(days=2))
    db_session.add_all([ipo_later, ipo_sooner])
    await db_session.commit()

    resp = await client.get("/api/ipos")
    data = resp.json()
    assert len(data) == 2
    # Ordered by expected_date ascending: sooner first
    dates = [item["expected_date"] for item in data]
    assert dates == sorted(dates)


async def test_list_ipos_includes_today(client, db_session):
    today = datetime.date.today()
    ipo_today = _make_ipo("ipo-today", expected_date=today)
    db_session.add(ipo_today)
    await db_session.commit()

    resp = await client.get("/api/ipos")
    assert len(resp.json()) == 1


async def test_list_ipos_response_schema(client, db_session):
    ipo = _make_ipo("ipo-schema")
    db_session.add(ipo)
    await db_session.commit()

    resp = await client.get("/api/ipos")
    item = resp.json()[0]
    expected_fields = {
        "id", "company_name", "symbol", "exchange",
        "price_range", "shares_offered", "expected_date",
        "status", "created_at",
    }
    assert expected_fields.issubset(set(item.keys()))


async def test_list_ipos_does_not_require_auth(client):
    """IPO endpoint is public — no auth headers needed."""
    resp = await client.get("/api/ipos")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/reminders
# ---------------------------------------------------------------------------

async def test_create_reminder_for_existing_ipo(client, db_session, google_auth_headers):
    ipo = _make_ipo("ipo-rem-1")
    db_session.add(ipo)
    await db_session.commit()
    await db_session.refresh(ipo)

    resp = await client.post(
        "/api/reminders",
        json={
            "ipo_event_id": ipo.id,
            "notify_via": "email",
            "notify_address": "test@example.com",
            "remind_before_hours": 24,
        },
        headers=google_auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["ipo_event_id"] == ipo.id
    assert data["notify_via"] == "email"
    assert data["sent"] is False


async def test_create_reminder_missing_ipo_returns_404(client, google_auth_headers):
    resp = await client.post(
        "/api/reminders",
        json={
            "ipo_event_id": 9999,
            "notify_via": "email",
            "notify_address": "test@example.com",
        },
        headers=google_auth_headers,
    )
    assert resp.status_code == 404


async def test_create_reminder_invalid_notify_via_returns_400(client, db_session, google_auth_headers):
    ipo = _make_ipo("ipo-rem-bad")
    db_session.add(ipo)
    await db_session.commit()
    await db_session.refresh(ipo)

    resp = await client.post(
        "/api/reminders",
        json={
            "ipo_event_id": ipo.id,
            "notify_via": "sms",
            "notify_address": "+1234567890",
        },
        headers=google_auth_headers,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/reminders
# ---------------------------------------------------------------------------

async def test_list_reminders_returns_all(client, db_session, google_auth_headers):
    ipo = _make_ipo("ipo-rem-list")
    db_session.add(ipo)
    await db_session.commit()
    await db_session.refresh(ipo)

    await client.post(
        "/api/reminders",
        json={"ipo_event_id": ipo.id, "notify_via": "email", "notify_address": "a@b.com"},
        headers=google_auth_headers,
    )
    await client.post(
        "/api/reminders",
        json={"ipo_event_id": ipo.id, "notify_via": "pagerduty", "notify_address": "pd-key"},
        headers=google_auth_headers,
    )

    resp = await client.get("/api/reminders", headers=google_auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# DELETE /api/reminders/{id}
# ---------------------------------------------------------------------------

async def test_delete_reminder_removes_row(client, db_session, google_auth_headers):
    ipo = _make_ipo("ipo-rem-del")
    db_session.add(ipo)
    await db_session.commit()
    await db_session.refresh(ipo)

    create_resp = await client.post(
        "/api/reminders",
        json={"ipo_event_id": ipo.id, "notify_via": "email", "notify_address": "a@b.com"},
        headers=google_auth_headers,
    )
    reminder_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/reminders/{reminder_id}", headers=google_auth_headers)
    assert resp.status_code == 204

    result = await db_session.execute(select(Reminder).where(Reminder.id == reminder_id))
    assert result.scalar_one_or_none() is None


async def test_delete_reminder_nonexistent_returns_404(client, google_auth_headers):
    resp = await client.delete("/api/reminders/9999", headers=google_auth_headers)
    assert resp.status_code == 404


async def test_reminders_require_google_auth_anonymous_rejected(client):
    """Tier 2 guard: anonymous sessions must get 403, not 200."""
    resp = await client.post(
        "/api/reminders",
        json={"ipo_event_id": 1, "notify_via": "email", "notify_address": "x@y.com"},
        headers={"X-Session-ID": "anon-session-id"},
    )
    assert resp.status_code == 403


async def test_reminders_require_google_auth_no_headers_rejected(client):
    """Tier 2 guard: no credentials at all must get 401."""
    resp = await client.get("/api/reminders")
    assert resp.status_code == 401
