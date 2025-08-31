from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class RuntimeState:
    """
    Manages in-memory runtime state for DEX Sniper Pro.
    Handles WebSocket client registries and shared state.
    """
    
    def __init__(self):
        # WebSocket client registries
        self._paper_clients: Set[WebSocket] = set()
        self._metrics_clients: Set[WebSocket] = set()
        
        # Runtime flags
        self._paper_enabled: bool = True
        self._autotrade_enabled: bool = False
        
        # Paper trading metrics
        self._paper_metrics = {
            "total_trades": 0,
            "winning_trades": 0,
            "total_pnl_usd": 0.0,
            "win_rate_pct": 0.0,
            "session_start": datetime.now(timezone.utc).isoformat(),
        }
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    # WebSocket client management
    async def register_paper_client(self, websocket: WebSocket) -> None:
        """Register a new paper trading WebSocket client."""
        self._paper_clients.add(websocket)
        logger.info("Paper client registered. Total: %d", len(self._paper_clients))
    
    async def unregister_paper_client(self, websocket: WebSocket) -> None:
        """Unregister a paper trading WebSocket client."""
        self._paper_clients.discard(websocket)
        logger.info("Paper client unregistered. Total: %d", len(self._paper_clients))
    
    async def register_metrics_client(self, websocket: WebSocket) -> None:
        """Register a new metrics WebSocket client."""
        self._metrics_clients.add(websocket)
        logger.info("Metrics client registered. Total: %d", len(self._metrics_clients))
    
    async def unregister_metrics_client(self, websocket: WebSocket) -> None:
        """Unregister a metrics WebSocket client."""
        self._metrics_clients.discard(websocket)
        logger.info("Metrics client unregistered. Total: %d", len(self._metrics_clients))
    
    # Paper trading state management
    async def get_paper_enabled(self) -> bool:
        """Get current paper trading enabled status."""
        return self._paper_enabled
    
    async def set_paper_enabled(self, enabled: bool) -> None:
        """Set paper trading enabled status and broadcast to clients."""
        async with self._lock:
            self._paper_enabled = enabled
            await self._broadcast_paper_status()
    
    async def get_paper_metrics(self) -> Dict[str, Any]:
        """Get current paper trading metrics."""
        return self._paper_metrics.copy()
    
    async def update_paper_metrics(self, **updates) -> None:
        """Update paper trading metrics and broadcast to clients."""
        async with self._lock:
            self._paper_metrics.update(updates)
            await self._broadcast_metrics()
    
    # Broadcasting methods
    async def _broadcast_paper_status(self) -> None:
        """Broadcast paper trading status to all paper clients."""
        if not self._paper_clients:
            return
        
        message = {
            "type": "status",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "paper_enabled": self._paper_enabled,
                "autotrade_enabled": self._autotrade_enabled,
            }
        }
        
        await self._broadcast_to_clients(self._paper_clients, message)
    
    async def _broadcast_metrics(self) -> None:
        """Broadcast metrics to all metrics clients."""
        if not self._metrics_clients:
            return
        
        message = {
            "type": "metrics_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": self._paper_metrics
        }
        
        await self._broadcast_to_clients(self._metrics_clients, message)
    
    async def emit_thought_log(self, thought_data: Dict[str, Any]) -> None:
        """Emit AI thought log to paper trading clients."""
        if not self._paper_clients:
            return
        
        message = {
            "type": "thought_log",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": thought_data
        }
        
        await self._broadcast_to_clients(self._paper_clients, message)
    
    async def _broadcast_to_clients(self, clients: Set[WebSocket], message: Dict[str, Any]) -> None:
        """Broadcast message to a set of WebSocket clients."""
        if not clients:
            return
        
        # Create a copy to avoid modification during iteration
        clients_copy = clients.copy()
        disconnected = set()
        
        for client in clients_copy:
            try:
                await client.send_text(json.dumps(message))
            except Exception as e:
                logger.warning("Failed to send message to client: %s", e)
                disconnected.add(client)
        
        # Remove disconnected clients
        for client in disconnected:
            clients.discard(client)


# Global runtime state instance
runtime_state = RuntimeState()