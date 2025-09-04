# APP: backend
# FILE: backend/app/ws/paper.py
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dex_django.core.runtime_state import runtime_state

router = APIRouter(tags=["ws-paper"])


@router.websocket("/ws/paper")
async def ws_paper(websocket: WebSocket) -> None:
    """Paper-trading WebSocket: status frames, thought logs, paper metrics."""
    await websocket.accept()
    await runtime_state.register_paper_client(websocket)
    try:
        await websocket.send_json(
            {
                "type": "hello",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "channel": "paper",
                    "paper_enabled": await runtime_state.get_paper_enabled(),
                },
            }
        )
        # Passive hub: producers broadcast via runtime_state.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await runtime_state.unregister_paper_client(websocket)
    except Exception:
        await runtime_state.unregister_paper_client(websocket)
