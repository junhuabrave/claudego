"""WebSocket connection manager for real-time push to clients."""

import datetime
import json
import logging

from fastapi import WebSocket


class _DatetimeEncoder(json.JSONEncoder):
    """JSON encoder that serializes datetime objects to ISO 8601 strings."""

    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connected. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info("WebSocket disconnected. Total: %d", len(self.active_connections))

    async def broadcast(self, message_type: str, data: dict):
        """Broadcast a message to all connected clients."""
        payload = json.dumps({"type": message_type, "data": data}, cls=_DatetimeEncoder)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.active_connections.remove(conn)

    async def send_personal(self, websocket: WebSocket, message_type: str, data: dict):
        payload = json.dumps({"type": message_type, "data": data}, cls=_DatetimeEncoder)
        await websocket.send_text(payload)


ws_manager = ConnectionManager()
