"""Test I — WebSocket Manager

Covers: ConnectionManager connect, disconnect, broadcast, send_personal,
and the DatetimeEncoder for JSON serialization.
"""

import datetime
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.websocket_manager import ConnectionManager, _DatetimeEncoder


# ---------------------------------------------------------------------------
# _DatetimeEncoder
# ---------------------------------------------------------------------------

class TestDatetimeEncoder:
    def test_encodes_datetime(self):
        dt = datetime.datetime(2025, 6, 15, 12, 30, 0, tzinfo=datetime.timezone.utc)
        result = json.dumps({"ts": dt}, cls=_DatetimeEncoder)
        assert "2025-06-15" in result
        assert "12:30:00" in result

    def test_encodes_date(self):
        d = datetime.date(2025, 6, 15)
        result = json.dumps({"d": d}, cls=_DatetimeEncoder)
        assert "2025-06-15" in result

    def test_raises_for_unknown_type(self):
        with pytest.raises(TypeError):
            json.dumps({"x": set()}, cls=_DatetimeEncoder)


# ---------------------------------------------------------------------------
# ConnectionManager
# ---------------------------------------------------------------------------

class TestConnectionManager:
    def test_initial_state_empty(self):
        manager = ConnectionManager()
        assert manager.active_connections == []

    async def test_connect_adds_to_list(self):
        manager = ConnectionManager()
        ws = AsyncMock()
        await manager.connect(ws)
        assert ws in manager.active_connections
        ws.accept.assert_awaited_once()

    async def test_disconnect_removes_from_list(self):
        manager = ConnectionManager()
        ws = AsyncMock()
        await manager.connect(ws)
        manager.disconnect(ws)
        assert ws not in manager.active_connections

    async def test_broadcast_sends_to_all(self):
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect(ws1)
        await manager.connect(ws2)

        await manager.broadcast("news", {"headline": "Test"})

        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()

        # Verify JSON structure
        sent = json.loads(ws1.send_text.call_args[0][0])
        assert sent["type"] == "news"
        assert sent["data"]["headline"] == "Test"

    async def test_broadcast_removes_disconnected_clients(self):
        manager = ConnectionManager()
        ws_good = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.send_text.side_effect = Exception("Connection closed")

        await manager.connect(ws_good)
        await manager.connect(ws_bad)

        await manager.broadcast("test", {"key": "value"})

        # Bad connection should be removed
        assert ws_bad not in manager.active_connections
        assert ws_good in manager.active_connections

    async def test_broadcast_empty_connections(self):
        manager = ConnectionManager()
        # Should not raise
        await manager.broadcast("test", {"key": "value"})

    async def test_send_personal(self):
        manager = ConnectionManager()
        ws = AsyncMock()
        await manager.connect(ws)

        await manager.send_personal(ws, "pong", {})

        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "pong"
        assert sent["data"] == {}

    async def test_broadcast_with_datetime_data(self):
        """Broadcast should handle datetime objects in data via _DatetimeEncoder."""
        manager = ConnectionManager()
        ws = AsyncMock()
        await manager.connect(ws)

        dt = datetime.datetime(2025, 6, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        await manager.broadcast("alert", {"triggered_at": dt})

        sent = json.loads(ws.send_text.call_args[0][0])
        assert "2025-06-15" in sent["data"]["triggered_at"]

    async def test_multiple_connects_tracked(self):
        manager = ConnectionManager()
        connections = [AsyncMock() for _ in range(5)]
        for ws in connections:
            await manager.connect(ws)
        assert len(manager.active_connections) == 5
