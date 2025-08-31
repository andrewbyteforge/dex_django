# APP: backend
# FILE: dex_django/apps/ws/consumers.py
from __future__ import annotations

import json
from typing import Any, Dict

from django.core.cache import cache
from django.utils import timezone
from channels.generic.websocket import AsyncWebsocketConsumer


class PaperTradingConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for Paper Trading real-time updates."""
    
    async def connect(self) -> None:
        """Accept WebSocket connection and add to paper trading group."""
        self.group_name = "paper_trading"
        
        # Join the paper trading group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial hello message with current paper trading status
        paper_enabled = cache.get("paper_enabled", False)
        await self.send(text_data=json.dumps({
            "type": "hello",
            "timestamp": timezone.now().isoformat(),
            "payload": {
                "channel": "paper",
                "paper_enabled": paper_enabled,
            },
        }))

    async def disconnect(self, close_code: int) -> None:
        """Remove from paper trading group on disconnect."""
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data: str) -> None:
        """Handle incoming WebSocket messages (ping/pong, etc.)."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type", "")
            
            if message_type == "ping":
                # Respond to ping with pong
                await self.send(text_data=json.dumps({
                    "type": "pong",
                    "timestamp": timezone.now().isoformat(),
                }))
                
        except (json.JSONDecodeError, KeyError):
            # Ignore malformed messages
            pass

    # Group message handlers
    async def paper_status(self, event: Dict[str, Any]) -> None:
        """Handle paper trading status broadcast."""
        message = event["message"]
        await self.send(text_data=json.dumps(message))

    async def thought_log(self, event: Dict[str, Any]) -> None:
        """Handle AI thought log broadcast."""
        message = event["message"]
        await self.send(text_data=json.dumps(message))

    async def paper_metrics(self, event: Dict[str, Any]) -> None:
        """Handle paper metrics broadcast."""
        message = event["message"]
        await self.send(text_data=json.dumps(message))