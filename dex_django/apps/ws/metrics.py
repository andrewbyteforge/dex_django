# APP: backend
# FILE: app/ws/metrics.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core.runtime_state import runtime_state

router = APIRouter(tags=["ws-metrics"])


async def _hello() -> Dict[str, Any]:
    return {"type": "hello", "timestamp": datetime.now(timezone.utc).isoformat(), "payload": {"channel": "metrics"}}


@router.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket) -> None:
    """Stream session/rolling KPIs for dashboard cards."""
    await websocket.accept()
    await runtime_state.register_metrics_client(websocket)
    try:
        await websocket.send_json(await _hello())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await runtime_state.unregister_metrics_client(websocket)
    except Exception:
        await runtime_state.unregister_metrics_client(websocket)
