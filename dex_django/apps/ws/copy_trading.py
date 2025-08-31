from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ws-copy-trading"])


class CopyTradingMessage(BaseModel):
    """Base message format for copy trading WebSocket."""
    
    type: str
    timestamp: str
    payload: Dict[str, Any]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class CopyTradingHub:
    """
    WebSocket hub for copy trading events.
    Broadcasts trader activity, copy decisions, and execution results.
    """
    
    def __init__(self):
        self._clients: Set[WebSocket] = set()
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._broadcaster_task: Optional[asyncio.Task] = None
        self._is_running = False
    
    async def start(self) -> None:
        """Start the copy trading hub broadcaster."""
        if self._is_running:
            return
        
        self._is_running = True
        self._broadcaster_task = asyncio.create_task(
            self._broadcast_loop(),
            name="copy_trading_broadcaster"
        )
        logger.info("Copy trading WebSocket hub started")
    
    async def stop(self) -> None:
        """Stop the copy trading hub."""
        self._is_running = False
        
        if self._broadcaster_task:
            self._broadcaster_task.cancel()
            try:
                await self._broadcaster_task
            except asyncio.CancelledError:
                pass
        
        # Close all client connections
        disconnected = []
        for client in self._clients.copy():
            try:
                await client.close()
                disconnected.append(client)
            except Exception as e:
                logger.warning("Error closing WebSocket client: %s", e)
        
        for client in disconnected:
            self._clients.discard(client)
        
        logger.info("Copy trading WebSocket hub stopped")
    
    async def register_client(self, websocket: WebSocket) -> None:
        """Register a new WebSocket client."""
        self._clients.add(websocket)
        logger.info("Copy trading client registered. Total: %d", len(self._clients))
        
        # Send welcome message with current status
        await self._send_to_client(websocket, {
            "type": "hello",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "channel": "copy_trading",
                "monitoring_status": await self._get_monitoring_status(),
                "active_traders": await self._get_active_traders_count(),
            }
        })
    
    async def unregister_client(self, websocket: WebSocket) -> None:
        """Unregister a WebSocket client."""
        self._clients.discard(websocket)
        logger.info("Copy trading client unregistered. Total: %d", len(self._clients))
    
    async def broadcast_trader_activity(
        self,
        trader_address: str,
        transaction_data: Dict[str, Any]
    ) -> None:
        """Broadcast detected trader activity."""
        message = {
            "type": "trader_activity",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "trader_address": trader_address,
                "short_address": f"{trader_address[:8]}...{trader_address[-4:]}",
                "transaction": transaction_data,
                "status": "detected"
            }
        }
        await self._queue_message(message)
    
    async def broadcast_copy_evaluation(
        self,
        evaluation_data: Dict[str, Any]
    ) -> None:
        """Broadcast copy trade evaluation result."""
        message = {
            "type": "copy_evaluation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "decision": evaluation_data.get("decision", "unknown"),
                "confidence": evaluation_data.get("confidence", 0.0),
                "trader_address": evaluation_data.get("trader_address", ""),
                "token_symbol": evaluation_data.get("token_symbol", ""),
                "copy_amount_usd": evaluation_data.get("copy_amount_usd", 0.0),
                "risk_score": evaluation_data.get("risk_score", 0.0),
                "rationale": evaluation_data.get("rationale", ""),
                "original_tx_hash": evaluation_data.get("original_tx_hash", "")
            }
        }
        await self._queue_message(message)
    
    async def broadcast_copy_execution(
        self,
        execution_data: Dict[str, Any]
    ) -> None:
        """Broadcast copy trade execution result."""
        message = {
            "type": "copy_execution",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "status": execution_data.get("status", "unknown"),
                "copy_tx_hash": execution_data.get("copy_tx_hash", ""),
                "trader_address": execution_data.get("trader_address", ""),
                "token_symbol": execution_data.get("token_symbol", ""),
                "copy_amount_usd": execution_data.get("copy_amount_usd", 0.0),
                "execution_delay_ms": execution_data.get("execution_delay_ms", 0),
                "realized_slippage_bps": execution_data.get("realized_slippage_bps"),
                "gas_fees_usd": execution_data.get("gas_fees_usd"),
                "error_reason": execution_data.get("error_reason")
            }
        }
        await self._queue_message(message)
    
    async def broadcast_trader_performance_update(
        self,
        trader_address: str,
        performance_data: Dict[str, Any]
    ) -> None:
        """Broadcast trader performance update."""
        message = {
            "type": "trader_performance",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "trader_address": trader_address,
                "short_address": f"{trader_address[:8]}...{trader_address[-4:]}",
                "total_trades": performance_data.get("total_trades", 0),
                "winning_trades": performance_data.get("winning_trades", 0),
                "win_rate_pct": performance_data.get("win_rate", 0.0) * 100,
                "total_pnl_usd": performance_data.get("total_pnl", 0.0),
                "last_trade_timestamp": performance_data.get("last_trade_timestamp")
            }
        }
        await self._queue_message(message)
    
    async def broadcast_copy_trading_status(
        self,
        status_data: Dict[str, Any]
    ) -> None:
        """Broadcast overall copy trading status update."""
        message = {
            "type": "status_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": status_data
        }
        await self._queue_message(message)
    
    async def broadcast_heartbeat(self) -> None:
        """Send heartbeat to maintain connection."""
        message = {
            "type": "heartbeat",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "connected_clients": len(self._clients),
                "uptime_seconds": 3600,  # Mock uptime
                "monitoring_active": True
            }
        }
        await self._queue_message(message)
    
    async def _queue_message(self, message: Dict[str, Any]) -> None:
        """Queue a message for broadcasting."""
        if not self._is_running:
            return
        
        try:
            await self._message_queue.put(message)
        except Exception as e:
            logger.error("Failed to queue copy trading message: %s", e)
    
    async def _broadcast_loop(self) -> None:
        """Main broadcast loop that processes queued messages."""
        logger.info("Starting copy trading broadcast loop")
        
        # Send periodic heartbeat
        heartbeat_interval = 30  # seconds
        last_heartbeat = datetime.now(timezone.utc)
        
        while self._is_running:
            try:
                # Check for heartbeat
                now = datetime.now(timezone.utc)
                if (now - last_heartbeat).total_seconds() >= heartbeat_interval:
                    await self.broadcast_heartbeat()
                    last_heartbeat = now
                
                # Process queued messages with timeout
                try:
                    message = await asyncio.wait_for(
                        self._message_queue.get(),
                        timeout=1.0
                    )
                    await self._broadcast_to_all_clients(message)
                    self._message_queue.task_done()
                except asyncio.TimeoutError:
                    # No messages to process, continue loop
                    continue
                
            except Exception as e:
                logger.error("Error in copy trading broadcast loop: %s", e)
                await asyncio.sleep(1.0)
        
        logger.info("Copy trading broadcast loop stopped")
    
    async def _broadcast_to_all_clients(self, message: Dict[str, Any]) -> None:
        """Broadcast message to all connected clients."""
        if not self._clients:
            return
        
        # Create a copy to avoid modification during iteration
        clients_copy = self._clients.copy()
        disconnected = set()
        
        for client in clients_copy:
            try:
                await self._send_to_client(client, message)
            except Exception as e:
                logger.warning("Failed to send to copy trading client: %s", e)
                disconnected.add(client)
        
        # Remove disconnected clients
        for client in disconnected:
            self._clients.discard(client)
    
    async def _send_to_client(self, client: WebSocket, message: Dict[str, Any]) -> None:
        """Send message to a specific client."""
        await client.send_text(json.dumps(message))
    
    async def _get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status."""
        # Would integrate with actual wallet monitor
        return {
            "is_running": True,
            "followed_wallets": 2,
            "active_tasks": 2
        }
    
    async def _get_active_traders_count(self) -> int:
        """Get number of active traders being followed."""
        # Would query database in production
        return 2


# Global copy trading hub instance
copy_trading_hub = CopyTradingHub()


@router.websocket("/ws/copy-trading")
async def ws_copy_trading(websocket: WebSocket) -> None:
    """
    Copy trading WebSocket endpoint.
    Streams trader activity, copy decisions, and execution results.
    """
    await websocket.accept()
    await copy_trading_hub.register_client(websocket)
    
    try:
        # Start hub if not already running
        if not copy_trading_hub._is_running:
            await copy_trading_hub.start()
        
        # Keep connection alive and handle client messages
        while True:
            try:
                # Receive client messages (for potential client commands)
                message = await websocket.receive_text()
                await _handle_client_message(websocket, message)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error("Error handling copy trading WebSocket message: %s", e)
                break
    
    except WebSocketDisconnect:
        logger.info("Copy trading WebSocket client disconnected")
    except Exception as e:
        logger.error("Copy trading WebSocket error: %s", e)
    finally:
        await copy_trading_hub.unregister_client(websocket)


async def _handle_client_message(websocket: WebSocket, message: str) -> None:
    """Handle incoming messages from WebSocket clients."""
    try:
        data = json.loads(message)
        message_type = data.get("type", "unknown")
        
        if message_type == "ping":
            # Respond to ping
            response = {
                "type": "pong",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {"message": "Copy trading hub is alive"}
            }
            await websocket.send_text(json.dumps(response))
        
        elif message_type == "get_status":
            # Send current status
            status = {
                "type": "status_response",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "monitoring_active": copy_trading_hub._is_running,
                    "connected_clients": len(copy_trading_hub._clients),
                    "active_traders": await copy_trading_hub._get_active_traders_count()
                }
            }
            await websocket.send_text(json.dumps(status))
        
        elif message_type == "test_trader_activity":
            # Test message for development
            await copy_trading_hub.broadcast_trader_activity(
                "0x742d35cc6634c0532925a3b8d186dc8c",
                {
                    "tx_hash": "0xtest123",
                    "action": "buy",
                    "token_symbol": "PEPE",
                    "amount_usd": 1250.0,
                    "chain": "ethereum",
                    "dex": "uniswap_v3"
                }
            )
        
        elif message_type == "test_copy_evaluation":
            # Test copy evaluation message
            await copy_trading_hub.broadcast_copy_evaluation({
                "decision": "copy",
                "confidence": 0.85,
                "trader_address": "0x742d35cc6634c0532925a3b8d186dc8c",
                "token_symbol": "PEPE",
                "copy_amount_usd": 75.0,
                "risk_score": 4.2,
                "rationale": "Good trader performance, low risk token",
                "original_tx_hash": "0xtest123"
            })
        
        elif message_type == "test_copy_execution":
            # Test copy execution message
            await copy_trading_hub.broadcast_copy_execution({
                "status": "executed",
                "copy_tx_hash": "0xexecuted456",
                "trader_address": "0x742d35cc6634c0532925a3b8d186dc8c",
                "token_symbol": "PEPE",
                "copy_amount_usd": 75.0,
                "execution_delay_ms": 12000,
                "realized_slippage_bps": 85,
                "gas_fees_usd": 15.20
            })
        
        else:
            logger.warning("Unknown copy trading WebSocket message type: %s", message_type)
    
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in copy trading WebSocket message")
    except Exception as e:
        logger.error("Error handling copy trading client message: %s", e)


# Utility functions for integration with other modules
async def emit_trader_activity(trader_address: str, tx_data: Dict[str, Any]) -> None:
    """Public function to emit trader activity from wallet monitor."""
    await copy_trading_hub.broadcast_trader_activity(trader_address, tx_data)


async def emit_copy_evaluation(evaluation_data: Dict[str, Any]) -> None:
    """Public function to emit copy evaluation from strategy module."""
    await copy_trading_hub.broadcast_copy_evaluation(evaluation_data)


async def emit_copy_execution(execution_data: Dict[str, Any]) -> None:
    """Public function to emit copy execution from trading module."""
    await copy_trading_hub.broadcast_copy_execution(execution_data)


async def emit_trader_performance(trader_address: str, perf_data: Dict[str, Any]) -> None:
    """Public function to emit trader performance updates."""
    await copy_trading_hub.broadcast_trader_performance_update(trader_address, perf_data)


async def emit_status_update(status_data: Dict[str, Any]) -> None:
    """Public function to emit status updates."""
    await copy_trading_hub.broadcast_copy_trading_status(status_data)