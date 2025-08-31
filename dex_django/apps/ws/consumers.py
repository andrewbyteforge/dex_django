from __future__ import annotations

import json
from channels.generic.websocket import AsyncWebsocketConsumer


class HealthConsumer(AsyncWebsocketConsumer):
    """Minimal echo/health WebSocket."""

    async def connect(self) -> None:
        await self.accept()
        await self.send_json({"ok": True, "event": "connected", "endpoint": "ws/health"})

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:
        if text_data:
            try:
                payload = json.loads(text_data)
            except json.JSONDecodeError:
                payload = {"raw": text_data}
        else:
            payload = {"bytes": bool(bytes_data)}
        await self.send_json({"ok": True, "event": "echo", "data": payload})

    async def disconnect(self, close_code: int) -> None:
        # No cleanup needed yet
        return

    async def send_json(self, data: dict) -> None:
        await self.send(text_data=json.dumps(data))
