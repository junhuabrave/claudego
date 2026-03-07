"""Test C — Threshold Alerts

Covers: GET/POST/PUT/DELETE /api/alerts user isolation,
check_price_alerts() logic (cooldown, direction, broadcast).
"""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.models import PriceAlert, User
from app.services.scheduler import check_price_alerts
from tests.conftest import anon_headers, auth_headers

ALERT_PAYLOAD = {"symbol": "AAPL", "threshold_pct": 5.0, "direction": "up"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def create_alert(client, headers: dict, payload: dict = None):
    return await client.post("/api/alerts", json=payload or ALERT_PAYLOAD, headers=headers)


# ---------------------------------------------------------------------------
# POST /api/alerts
# ---------------------------------------------------------------------------

async def test_create_alert_stores_user_id(client, db_session):
    # First create anon user
    me = await client.get("/api/auth/me", headers=anon_headers("alert-create-sess"))
    user_id = me.json()["id"]

    resp = await create_alert(client, anon_headers("alert-create-sess"))
    assert resp.status_code == 201
    data = resp.json()
    assert data["symbol"] == "AAPL"
    assert data["threshold_pct"] == 5.0
    assert data["direction"] == "up"

    # Verify user_id in DB
    result = await db_session.execute(select(PriceAlert).where(PriceAlert.id == data["id"]))
    alert = result.scalar_one()
    assert alert.user_id == user_id


async def test_create_alert_invalid_direction_returns_422(client):
    resp = await create_alert(
        client,
        anon_headers("invalid-dir"),
        {"symbol": "AAPL", "threshold_pct": 5.0, "direction": "sideways"},
    )
    assert resp.status_code == 422


async def test_create_alert_zero_threshold_returns_422(client):
    resp = await create_alert(
        client,
        anon_headers("zero-thresh"),
        {"symbol": "AAPL", "threshold_pct": 0, "direction": "both"},
    )
    assert resp.status_code == 422


async def test_create_alert_requires_premium_when_gated(client):
    with patch("app.api.routes.settings") as mock_settings:
        mock_settings.alerts_require_premium = True
        resp = await create_alert(client, anon_headers("premium-gated"))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/alerts
# ---------------------------------------------------------------------------

async def test_list_alerts_returns_only_current_users_alerts(client):
    headers_a = anon_headers("alerts-user-a")
    headers_b = anon_headers("alerts-user-b")

    await create_alert(client, headers_a, {**ALERT_PAYLOAD, "symbol": "AAPL"})
    await create_alert(client, headers_b, {**ALERT_PAYLOAD, "symbol": "MSFT"})

    resp_a = await client.get("/api/alerts", headers=headers_a)
    resp_b = await client.get("/api/alerts", headers=headers_b)

    symbols_a = [a["symbol"] for a in resp_a.json()]
    symbols_b = [a["symbol"] for a in resp_b.json()]

    assert symbols_a == ["AAPL"]
    assert symbols_b == ["MSFT"]


# ---------------------------------------------------------------------------
# PUT /api/alerts/{id}
# ---------------------------------------------------------------------------

async def test_update_alert_changes_threshold(client):
    headers = anon_headers("upd-sess")
    create_resp = await create_alert(client, headers)
    alert_id = create_resp.json()["id"]

    upd = await client.put(
        f"/api/alerts/{alert_id}",
        json={"threshold_pct": 10.0},
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["threshold_pct"] == 10.0


async def test_update_alert_wrong_user_returns_404(client):
    owner = anon_headers("owner-sess")
    other = anon_headers("other-sess")

    create_resp = await create_alert(client, owner)
    alert_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/alerts/{alert_id}",
        json={"threshold_pct": 10.0},
        headers=other,
    )
    assert resp.status_code == 404


async def test_toggle_alert_inactive(client):
    headers = anon_headers("toggle-sess")
    create_resp = await create_alert(client, headers)
    alert_id = create_resp.json()["id"]

    upd = await client.put(
        f"/api/alerts/{alert_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert upd.json()["is_active"] is False


# ---------------------------------------------------------------------------
# DELETE /api/alerts/{id}
# ---------------------------------------------------------------------------

async def test_delete_alert_removes_row(client, db_session):
    headers = anon_headers("del-alert-sess")
    create_resp = await create_alert(client, headers)
    alert_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/alerts/{alert_id}", headers=headers)
    assert resp.status_code == 204

    result = await db_session.execute(select(PriceAlert).where(PriceAlert.id == alert_id))
    assert result.scalar_one_or_none() is None


async def test_delete_alert_wrong_user_returns_404(client):
    owner = anon_headers("del-owner")
    other = anon_headers("del-other")

    create_resp = await create_alert(client, owner)
    alert_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/alerts/{alert_id}", headers=other)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# check_price_alerts() unit tests
# ---------------------------------------------------------------------------

def _make_alert(
    user_id: int = 1,
    symbol: str = "AAPL",
    threshold_pct: float = 5.0,
    direction: str = "up",
    triggered_at: datetime.datetime | None = None,
    is_active: bool = True,
) -> PriceAlert:
    alert = PriceAlert()
    alert.id = 1
    alert.user_id = user_id
    alert.symbol = symbol
    alert.threshold_pct = threshold_pct
    alert.direction = direction
    alert.is_active = is_active
    alert.triggered_at = triggered_at
    return alert


async def test_check_price_alerts_fires_when_up_threshold_crossed():
    alert = _make_alert(direction="up", threshold_pct=5.0)
    quotes = [{"symbol": "AAPL", "change_percent": 6.0, "price": 200.0}]

    broadcasts = []

    async def fake_broadcast(msg_type, data):
        if msg_type == "alert":
            broadcasts.append(data)

    with (
        patch("app.services.scheduler.async_session") as mock_session_ctx,
        patch("app.services.scheduler.ws_manager.broadcast", side_effect=fake_broadcast),
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_ctx.return_value = mock_session

        # First execute() call: return active alerts
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        mock_session.execute = AsyncMock(return_value=mock_result)

        await check_price_alerts(quotes)

    assert len(broadcasts) == 1
    assert broadcasts[0]["symbol"] == "AAPL"
    assert broadcasts[0]["actual_change_pct"] == 6.0


async def test_check_price_alerts_no_fire_when_direction_mismatch():
    alert = _make_alert(direction="down", threshold_pct=5.0)
    quotes = [{"symbol": "AAPL", "change_percent": 6.0, "price": 200.0}]

    broadcasts = []

    async def fake_broadcast(msg_type, data):
        broadcasts.append(data)

    with (
        patch("app.services.scheduler.async_session") as mock_session_ctx,
        patch("app.services.scheduler.ws_manager.broadcast", side_effect=fake_broadcast),
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_ctx.return_value = mock_session

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        mock_session.execute = AsyncMock(return_value=mock_result)

        await check_price_alerts(quotes)

    assert len(broadcasts) == 0


async def test_check_price_alerts_respects_cooldown():
    """Alert fired 10 minutes ago with 60-min cooldown → should NOT fire again."""
    recent = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
    alert = _make_alert(direction="both", threshold_pct=5.0, triggered_at=recent)
    quotes = [{"symbol": "AAPL", "change_percent": 7.0, "price": 200.0}]

    broadcasts = []

    with (
        patch("app.services.scheduler.async_session") as mock_session_ctx,
        patch("app.services.scheduler.ws_manager.broadcast", side_effect=lambda t, d: broadcasts.append(d) if t == "alert" else None),
        patch("app.services.scheduler.settings") as mock_cfg,
    ):
        mock_cfg.alert_cooldown_minutes = 60
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_ctx.return_value = mock_session
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        mock_session.execute = AsyncMock(return_value=mock_result)

        await check_price_alerts(quotes)

    assert len(broadcasts) == 0


async def test_check_price_alerts_fires_after_cooldown_elapsed():
    """Alert fired 90 minutes ago with 60-min cooldown → SHOULD fire."""
    old = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=90)
    alert = _make_alert(direction="both", threshold_pct=5.0, triggered_at=old)
    quotes = [{"symbol": "AAPL", "change_percent": 7.0, "price": 200.0}]

    broadcasts = []

    with (
        patch("app.services.scheduler.async_session") as mock_session_ctx,
        patch("app.services.scheduler.ws_manager.broadcast", side_effect=lambda t, d: broadcasts.append(d) if t == "alert" else None),
        patch("app.services.scheduler.settings") as mock_cfg,
    ):
        mock_cfg.alert_cooldown_minutes = 60
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_ctx.return_value = mock_session
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        mock_session.execute = AsyncMock(return_value=mock_result)

        await check_price_alerts(quotes)

    assert len(broadcasts) == 1


async def test_check_price_alerts_empty_quotes_is_noop():
    """Empty quotes list → no DB query, no broadcast."""
    with patch("app.services.scheduler.async_session") as mock_ctx:
        await check_price_alerts([])
        mock_ctx.assert_not_called()
