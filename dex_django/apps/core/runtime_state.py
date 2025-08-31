# APP: backend
# FILE: backend/app/core/runtime_state.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from fastapi import WebSocket


@dataclass
class PaperMetrics:
    """Minimal paper-trading session metrics snapshot."""
    session_pnl_gbp: float = 0.0
    session_trades: int = 0
    win_rate: float = 0.0
    max_drawdown_gbp: float = 0.0
    last_update: str = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict of metrics."""
        data = asdict(self)
        data["last_update"] = self.last_update
        return data


class RuntimeState:
    """Process-wide runtime state and WebSocket broadcast registry.

    Thread-safe via an asyncio.Lock. Keeps things simple (no broker) while we
    stand up the first Paper Trading controls and streams.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._paper_enabled: bool = False
        self._paper_metrics = PaperMetrics()

        # WebSocket client registries
        self._paper_clients: Set[WebSocket] = set()

    # ---------- Paper mode ----------
    async def set_paper_enabled(self, enabled: bool) -> None:
        """Enable/disable paper trading and broadcast a status frame."""
        async with self._lock:
            self._paper_enabled = enabled
        await self.broadcast_paper({
            "type": "status",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {"paper_enabled": enabled},
        })

    async def get_paper_enabled(self) -> bool:
        """Return current paper trading flag."""
        async with self._lock:
            return self._paper_enabled

    # ---------- Metrics ----------
    async def get_paper_metrics(self) -> Dict[str, Any]:
        """Return current metrics as a dict."""
        async with self._lock:
            return self._paper_metrics.to_dict()

    async def update_paper_metrics(self, **fields: Any) -> None:
        """Set metrics fields and broadcast a metrics frame (best-effort)."""
        async with self._lock:
            for k, v in fields.items():
                if hasattr(self._paper_metrics, k):
                    setattr(self._paper_metrics, k, v)
            self._paper_metrics.last_update = datetime.now(timezone.utc).isoformat()
            payload = self._paper_metrics.to_dict()

        await self.broadcast_paper({
            "type": "paper_metrics",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        })

    # ---------- Thought Log ----------
    async def emit_thought_log(self, payload: Dict[str, Any]) -> None:
        """Broadcast a single AI Thought Log frame to paper clients."""
        frame = {
            "type": "thought_log",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        await self.broadcast_paper(frame)

    # ---------- WS client registry ----------
    async def register_paper_client(self, ws: WebSocket) -> None:
        """Register a paper-channel WebSocket client."""
        async with self._lock:
            self._paper_clients.add(ws)

    async def unregister_paper_client(self, ws: WebSocket) -> None:
        """Unregister a paper-channel WebSocket client."""
        async with self._lock:
            self._paper_clients.discard(ws)

    # ---------- Broadcasters ----------
    async def broadcast_paper(self, frame: Dict[str, Any]) -> None:
        """Broadcast a JSON frame to all paper WS clients."""
        async with self._lock:
            clients: List[WebSocket] = list(self._paper_clients)
        for ws in clients:
            try:
                await ws.send_json(frame)
            except Exception:
                # Drop dead sockets silently; this is a best-effort channel.
                await self.unregister_paper_client(ws)


# Singleton
runtime_state = RuntimeState()
