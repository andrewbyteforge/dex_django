# APP: dex_django
# FILE: dex_django/apps/ws/debug_websockets.py
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from dex_django.apps.core.debug_state import debug_state

router = APIRouter()
logger = logging.getLogger("ws.debug")

print(f"DEBUG: Router routes count: {len(router.routes)}")

@router.websocket("/ws/paper")
async def paper_trading_websocket(
    websocket: WebSocket,
    client_id: str = Query(default_factory=lambda: str(uuid4()))
) -> None:
    """
    WebSocket endpoint for paper trading updates.
    
    Streams real-time paper trading events including:
    - Trade executions
    - AI thought log entries  
    - Risk gate decisions
    - Performance metrics
    
    Args:
        websocket: WebSocket connection instance.
        client_id: Unique client identifier for tracking.
    """
    await websocket.accept()
    debug_state.add_paper_client(websocket)
    
    logger.info(f"Paper trading WebSocket connected: {client_id}")
    
    # Send welcome message with current status
    welcome_msg = {
        "type": "connection_established",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "client_id": client_id,
        "payload": {
            "thought_log_active": debug_state.thought_log_active,
            "connected_clients": debug_state.get_paper_client_count(),
            "features_available": {
                "copy_trading": debug_state.copy_trading_system_ready,
                "django_orm": debug_state.django_initialized
            }
        }
    }
    
    try:
        await websocket.send_json(welcome_msg)
        
        # Heartbeat and connection management
        last_ping = datetime.now(timezone.utc)
        ping_interval = 30  # seconds
        
        # Keep connection alive with non-blocking message handling
        while True:
            try:
                # Use asyncio.wait_for with timeout to avoid blocking indefinitely
                try:
                    message = await asyncio.wait_for(
                        websocket.receive_json(), 
                        timeout=1.0  # 1 second timeout
                    )
                    await handle_paper_websocket_message(websocket, client_id, message)
                    
                except asyncio.TimeoutError:
                    # No message received - this is normal, continue with heartbeat
                    pass
                
                # Send periodic ping to keep connection alive
                current_time = datetime.now(timezone.utc)
                if (current_time - last_ping).total_seconds() >= ping_interval:
                    ping_msg = {
                        "type": "ping",
                        "timestamp": current_time.isoformat(),
                        "payload": {"client_id": client_id}
                    }
                    await websocket.send_json(ping_msg)
                    last_ping = current_time
                    
                # Small sleep to prevent busy loop
                await asyncio.sleep(0.1)
                
            except WebSocketDisconnect:
                logger.info(f"Paper trading WebSocket disconnected: {client_id}")
                break
                
            except Exception as e:
                logger.error(f"Error in paper WebSocket loop for {client_id}: {e}")
                # Send error response to client
                try:
                    error_msg = {
                        "type": "error",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": {
                            "error": str(e),
                            "client_id": client_id
                        }
                    }
                    await websocket.send_json(error_msg)
                except:
                    # If we can't send error message, connection is dead
                    break
                
    except WebSocketDisconnect:
        logger.info(f"Paper trading WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Paper trading WebSocket error for {client_id}: {e}")
    finally:
        debug_state.remove_paper_client(websocket)


@router.websocket("/ws/metrics")
async def metrics_websocket(
    websocket: WebSocket,
    client_id: str = Query(default_factory=lambda: str(uuid4()))
) -> None:
    """
    WebSocket endpoint for system metrics streaming.
    
    Streams real-time system performance metrics including:
    - Trade execution statistics
    - Risk gate hit rates
    - Copy trading performance
    - System resource usage
    
    Args:
        websocket: WebSocket connection instance.
        client_id: Unique client identifier for tracking.
    """
    await websocket.accept()
    debug_state.add_metrics_client(websocket)
    
    logger.info(f"Metrics WebSocket connected: {client_id}")
    
    # Send initial metrics snapshot
    initial_metrics = {
        "type": "metrics_snapshot",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "client_id": client_id,
        "payload": await get_current_metrics()
    }
    
    try:
        await websocket.send_json(initial_metrics)
        
        # Heartbeat and connection management
        last_ping = datetime.now(timezone.utc)
        ping_interval = 30  # seconds
        
        # Keep connection alive with non-blocking message handling
        while True:
            try:
                # Use asyncio.wait_for with timeout to avoid blocking indefinitely
                try:
                    message = await asyncio.wait_for(
                        websocket.receive_json(), 
                        timeout=1.0  # 1 second timeout
                    )
                    await handle_metrics_websocket_message(websocket, client_id, message)
                    
                except asyncio.TimeoutError:
                    # No message received - this is normal, continue with heartbeat
                    pass
                
                # Send periodic ping to keep connection alive
                current_time = datetime.now(timezone.utc)
                if (current_time - last_ping).total_seconds() >= ping_interval:
                    ping_msg = {
                        "type": "ping",
                        "timestamp": current_time.isoformat(),
                        "payload": {"client_id": client_id}
                    }
                    await websocket.send_json(ping_msg)
                    last_ping = current_time
                    
                # Small sleep to prevent busy loop
                await asyncio.sleep(0.1)
                
            except WebSocketDisconnect:
                logger.info(f"Metrics WebSocket disconnected: {client_id}")
                break
                
            except Exception as e:
                logger.error(f"Error in metrics WebSocket loop for {client_id}: {e}")
                # Send error response to client
                try:
                    error_msg = {
                        "type": "error",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": {
                            "error": str(e),
                            "client_id": client_id
                        }
                    }
                    await websocket.send_json(error_msg)
                except:
                    # If we can't send error message, connection is dead
                    break
                
    except WebSocketDisconnect:
        logger.info(f"Metrics WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Metrics WebSocket error for {client_id}: {e}")
    finally:
        debug_state.remove_metrics_client(websocket)





async def handle_paper_websocket_message(
    websocket: WebSocket, 
    client_id: str, 
    message: Dict[str, Any]
) -> None:
    """
    Handle incoming paper trading WebSocket messages.
    
    Args:
        websocket: WebSocket connection.
        client_id: Client identifier.
        message: Parsed JSON message from client.
    """
    message_type = message.get("type")
    logger.debug(f"Paper WebSocket message from {client_id}: {message_type}")
    
    if message_type == "ping":
        # Respond to ping with pong
        pong_msg = {
            "type": "pong",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {"client_id": client_id}
        }
        await websocket.send_json(pong_msg)
        
    elif message_type == "toggle_thought_log":
        # Toggle AI thought log streaming
        enable = message.get("payload", {}).get("enable", False)
        
        if enable:
            debug_state.enable_thought_log()
        else:
            debug_state.disable_thought_log()
            
        response = {
            "type": "thought_log_toggled",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "enabled": debug_state.thought_log_active,
                "client_id": client_id
            }
        }
        await websocket.send_json(response)
        
    elif message_type == "request_status":
        # Send current system status
        status_msg = {
            "type": "system_status",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": debug_state.get_system_status()
        }
        await websocket.send_json(status_msg)
        
    else:
        logger.warning(f"Unknown paper WebSocket message type: {message_type}")


async def handle_metrics_websocket_message(
    websocket: WebSocket,
    client_id: str, 
    message: Dict[str, Any]
) -> None:
    """
    Handle incoming metrics WebSocket messages.
    
    Args:
        websocket: WebSocket connection.
        client_id: Client identifier.
        message: Parsed JSON message from client.
    """
    message_type = message.get("type")
    logger.debug(f"Metrics WebSocket message from {client_id}: {message_type}")
    
    if message_type == "ping":
        pong_msg = {
            "type": "pong", 
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {"client_id": client_id}
        }
        await websocket.send_json(pong_msg)
        
    elif message_type == "request_metrics":
        # Send current metrics
        metrics_msg = {
            "type": "metrics_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": await get_current_metrics()
        }
        await websocket.send_json(metrics_msg)
        
    else:
        logger.warning(f"Unknown metrics WebSocket message type: {message_type}")


async def broadcast_thought_log(thought_data: Dict[str, Any]) -> None:
    """
    Broadcast AI thought log entry to all connected paper trading clients.
    
    Args:
        thought_data: Thought log data to broadcast.
    """
    if not debug_state.has_paper_clients():
        return
        
    message = {
        "type": "thought_log",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": thought_data
    }
    
    await broadcast_to_paper_clients(message)


async def broadcast_paper_trade(trade_data: Dict[str, Any]) -> None:
    """
    Broadcast paper trade execution to all connected clients.
    
    Args:
        trade_data: Trade execution data to broadcast.
    """
    if not debug_state.has_paper_clients():
        return
        
    message = {
        "type": "paper_trade",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": trade_data
    }
    
    await broadcast_to_paper_clients(message)


async def broadcast_risk_gate_decision(risk_data: Dict[str, Any]) -> None:
    """
    Broadcast risk gate decision to all connected clients.
    
    Args:
        risk_data: Risk gate decision data to broadcast.
    """
    if not debug_state.has_paper_clients():
        return
        
    message = {
        "type": "risk_gate",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": risk_data
    }
    
    await broadcast_to_paper_clients(message)


async def broadcast_to_paper_clients(message: Dict[str, Any]) -> None:
    """
    Broadcast message to all paper trading WebSocket clients.
    
    Args:
        message: Message to broadcast to all clients.
    """
    if not debug_state.has_paper_clients():
        return
    
    # Track disconnected clients for cleanup
    disconnected = set()
    successful_sends = 0
    
    for client in debug_state.paper_clients.copy():
        try:
            await client.send_json(message)
            successful_sends += 1
        except Exception as e:
            logger.warning(f"Failed to send to paper client: {e}")
            disconnected.add(client)
    
    # Clean up disconnected clients
    for client in disconnected:
        debug_state.remove_paper_client(client)
    
    if successful_sends > 0:
        logger.debug(f"Broadcasted message to {successful_sends} paper clients")


async def broadcast_to_metrics_clients(message: Dict[str, Any]) -> None:
    """
    Broadcast message to all metrics WebSocket clients.
    
    Args:
        message: Message to broadcast to all clients.
    """
    if not debug_state.has_metrics_clients():
        return
    
    # Track disconnected clients for cleanup
    disconnected = set()
    successful_sends = 0
    
    for client in debug_state.metrics_clients.copy():
        try:
            await client.send_json(message)
            successful_sends += 1
        except Exception as e:
            logger.warning(f"Failed to send to metrics client: {e}")
            disconnected.add(client)
    
    # Clean up disconnected clients
    for client in disconnected:
        debug_state.remove_metrics_client(client)
    
    if successful_sends > 0:
        logger.debug(f"Broadcasted message to {successful_sends} metrics clients")


async def get_current_metrics() -> Dict[str, Any]:
    """
    Get current system metrics for broadcasting.
    
    Returns:
        Dict containing current system metrics.
    """
    return {
        "system_status": debug_state.get_system_status(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "paper_trading": {
            "active": True,
            "trades_today": 0,
            "pnl_usd": "0.00",
            "win_rate": 0.0
        },
        "copy_trading": {
            "enabled": debug_state.copy_trading_system_ready,
            "followed_traders": 0,
            "active_copies": 0
        },
        "risk_gates": {
            "liquidity_blocks": 0,
            "slippage_blocks": 0,
            "blacklist_blocks": 0
        }
    }


# Scheduled task to broadcast periodic metrics updates
async def periodic_metrics_broadcast() -> None:
    """Broadcast metrics updates to all connected metrics clients."""
    if debug_state.has_metrics_clients():
        metrics = await get_current_metrics()
        message = {
            "type": "periodic_metrics",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": metrics
        }
        await broadcast_to_metrics_clients(message)