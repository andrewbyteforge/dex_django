from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket) -> None:
    """
    Metrics WebSocket: real-time trading metrics, session stats, and performance data.
    """
    await websocket.accept()
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "hello",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "channel": "metrics",
                "current_metrics": {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "total_pnl_usd": 0.0,
                    "win_rate_pct": 0.0,
                    "session_start": datetime.now(timezone.utc).isoformat()
                }
            }
        })
        
        # Handle messages
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message) if message else {}
                
                if data.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                elif data.get("type") == "request_metrics":
                    await websocket.send_json({
                        "type": "metrics_snapshot",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": {
                            "total_trades": 0,
                            "winning_trades": 0,
                            "total_pnl_usd": 0.0,
                            "win_rate_pct": 0.0
                        }
                    })
                
            except Exception as e:
                logger.warning("Error processing metrics WebSocket message: %s", e)
                break
                
    except WebSocketDisconnect:
        logger.info("Metrics WebSocket client disconnected")
    except Exception as e:
        logger.error("Metrics WebSocket error: %s", e)