# APP: dex_django
# FILE: dex_django/apps/api/debug_routers.py
from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from dex_django.apps.core.debug_state import debug_state
from dex_django.apps.ws.debug_websockets import broadcast_thought_log, broadcast_paper_trade

logger = logging.getLogger("api.debug_routers")

# Create routers for different debug functionalities
health_router = APIRouter(prefix="/health", tags=["health"])
api_router = APIRouter(prefix="/api/v1", tags=["debug-api"])


# Request/Response Models
class PaperToggleRequest(BaseModel):
    """Request model for paper trading toggle."""
    enabled: bool
    thought_log: bool = True


class PaperToggleResponse(BaseModel):
    """Response model for paper trading toggle."""
    status: str
    paper_enabled: bool
    thought_log_enabled: bool
    timestamp: str


class MockTradeRequest(BaseModel):
    """Request model for mock trade execution."""
    symbol: str
    side: str  # "buy" or "sell"
    amount_usd: Decimal
    slippage_bps: Optional[int] = 50


class MockOpportunity(BaseModel):
    """Mock opportunity data model."""
    id: str
    symbol: str
    chain: str
    dex: str
    price_usd: Decimal
    liquidity_usd: Decimal
    volume_24h_usd: Decimal
    score: float
    risk_level: str
    timestamp: str


# Health Endpoints
@health_router.get("/")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.
    
    Returns system status and availability of core components.
    """
    system_status = debug_state.get_system_status()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.4.0-debug",
        "components": {
            "django_orm": "ok" if debug_state.django_initialized else "unavailable",
            "copy_trading": "ok" if debug_state.copy_trading_system_ready else "unavailable",
            "websockets": "ok" if system_status["connections"]["total_clients"] >= 0 else "error"
        },
        "connections": system_status["connections"],
        "uptime_seconds": 0  # TODO: Track actual uptime
    }


@health_router.get("/live")
async def liveness_probe() -> Dict[str, str]:
    """
    Kubernetes liveness probe endpoint.
    
    Returns 200 if the application is running and can serve requests.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@health_router.get("/ready")
async def readiness_probe() -> Dict[str, Any]:
    """
    Kubernetes readiness probe endpoint.
    
    Returns 200 if the application is ready to serve traffic.
    """
    ready = True
    issues = []
    
    # Check critical components
    if not debug_state.django_initialized:
        ready = False
        issues.append("django_orm_not_initialized")
    
    if ready:
        return {
            "status": "ready",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "issues": issues,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


# Paper Trading API Endpoints
@api_router.post("/paper/toggle")
async def toggle_paper_trading(request: PaperToggleRequest) -> PaperToggleResponse:
    """
    Toggle paper trading mode and thought log streaming.
    
    Args:
        request: Paper trading toggle configuration.
        
    Returns:
        Current paper trading status and configuration.
    """
    logger.info(f"Paper trading toggle request: enabled={request.enabled}, thought_log={request.thought_log}")
    
    # Update thought log state
    if request.thought_log:
        debug_state.enable_thought_log()
    else:
        debug_state.disable_thought_log()
    
    # Broadcast status change to connected clients
    if debug_state.has_paper_clients():
        thought_data = {
            "type": "system_event",
            "message": f"Paper trading {'enabled' if request.enabled else 'disabled'}",
            "details": {
                "paper_enabled": request.enabled,
                "thought_log_enabled": request.thought_log,
                "connected_clients": debug_state.get_paper_client_count()
            }
        }
        await broadcast_thought_log(thought_data)
    
    return PaperToggleResponse(
        status="success",
        paper_enabled=request.enabled,
        thought_log_enabled=debug_state.thought_log_active,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@api_router.get("/paper/status")
async def get_paper_status() -> Dict[str, Any]:
    """
    Get current paper trading system status.
    
    Returns:
        Complete paper trading system status and metrics.
    """
    system_status = debug_state.get_system_status()
    
    return {
        "status": "active",
        "paper_trading": {
            "enabled": True,  # Always enabled in debug mode
            "thought_log_active": debug_state.thought_log_active,
            "connected_clients": debug_state.get_paper_client_count()
        },
        "mock_data": {
            "trades_today": random.randint(0, 50),
            "pnl_usd": f"{random.uniform(-500, 1500):.2f}",
            "win_rate_pct": random.uniform(45, 75),
            "avg_hold_time_minutes": random.randint(15, 480)
        },
        "system": system_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@api_router.post("/paper/mock-trade")
async def execute_mock_trade(request: MockTradeRequest) -> Dict[str, Any]:
    """
    Execute a mock paper trade for testing WebSocket broadcasting.
    
    Args:
        request: Mock trade execution parameters.
        
    Returns:
        Mock trade execution result.
    """
    trade_id = f"mock_{random.randint(10000, 99999)}"
    execution_price = Decimal(str(random.uniform(0.001, 10.0)))
    
    # Simulate trade execution result
    trade_data = {
        "trade_id": trade_id,
        "symbol": request.symbol,
        "side": request.side,
        "amount_usd": str(request.amount_usd),
        "execution_price": str(execution_price),
        "slippage_bps": request.slippage_bps or random.randint(10, 100),
        "gas_fee_usd": str(Decimal(str(random.uniform(1, 20)))),
        "status": "executed",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Broadcast to WebSocket clients
    await broadcast_paper_trade(trade_data)
    
    # Also send thought log about the trade
    thought_data = {
        "type": "trade_execution",
        "message": f"Executed mock {request.side} order for {request.symbol}",
        "details": {
            "reasoning": f"Simulated {request.side} signal detected",
            "risk_assessment": "Low risk - paper trading mode",
            "expected_outcome": "Testing WebSocket broadcasting"
        }
    }
    await broadcast_thought_log(thought_data)
    
    return {
        "status": "success",
        "trade": trade_data,
        "broadcasted_to_clients": debug_state.get_paper_client_count(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# Discovery and Opportunities Mock Endpoints
@api_router.get("/opportunities/live")
async def get_live_opportunities(
    limit: int = Query(default=20, ge=1, le=100),
    chain: Optional[str] = Query(default=None),
    min_score: float = Query(default=0.0, ge=0.0, le=10.0)
) -> Dict[str, Any]:
    """
    Get mock live trading opportunities.
    
    Args:
        limit: Maximum number of opportunities to return.
        chain: Optional chain filter.
        min_score: Minimum opportunity score filter.
        
    Returns:
        List of mock trading opportunities.
    """
    logger.info(f"Opportunities request: limit={limit}, chain={chain}, min_score={min_score}")
    
    chains = ["ethereum", "bsc", "base", "polygon", "solana"]
    dexes = ["uniswap_v3", "pancakeswap", "quickswap", "jupiter", "1inch"]
    symbols = ["PEPE/WETH", "DOGE/USDC", "SHIB/USDT", "WIF/SOL", "BONK/USDC"]
    
    opportunities = []
    
    for i in range(limit):
        selected_chain = chain if chain else random.choice(chains)
        score = random.uniform(min_score, 10.0)
        
        opportunity = MockOpportunity(
            id=f"opp_{random.randint(100000, 999999)}",
            symbol=random.choice(symbols),
            chain=selected_chain,
            dex=random.choice(dexes),
            price_usd=Decimal(str(random.uniform(0.0001, 5.0))),
            liquidity_usd=Decimal(str(random.uniform(10000, 500000))),
            volume_24h_usd=Decimal(str(random.uniform(50000, 2000000))),
            score=score,
            risk_level="low" if score > 7 else "medium" if score > 4 else "high",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        opportunities.append(opportunity.dict())
    
    result = {
        "status": "success",
        "opportunities": opportunities,
        "total_count": len(opportunities),
        "filters_applied": {
            "chain": chain,
            "min_score": min_score,
            "limit": limit
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    logger.info(f"Returning {len(opportunities)} opportunities")
    return result


@api_router.get("/opportunities/stats")
async def get_opportunity_stats() -> Dict[str, Any]:
    """
    Get mock opportunity statistics.
    
    Returns:
        Mock statistics about current market opportunities.
    """
    return {
        "status": "success",
        "stats": {
            "total_opportunities": random.randint(150, 500),
            "high_score_opportunities": random.randint(10, 50),
            "chains": {
                "ethereum": random.randint(30, 100),
                "bsc": random.randint(40, 120),
                "base": random.randint(20, 80),
                "polygon": random.randint(15, 60),
                "solana": random.randint(25, 90)
            },
            "avg_score": random.uniform(3.0, 7.0),
            "avg_liquidity_usd": random.uniform(50000, 200000),
            "last_updated": datetime.now(timezone.utc).isoformat()
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# Copy Trading Mock Endpoints
@api_router.get("/copy/status")
async def get_copy_trading_status() -> Dict[str, Any]:
    """
    Get mock copy trading system status.
    
    Returns:
        Mock copy trading system status and metrics.
    """
    return {
        "status": "success",
        "copy_trading": {
            "enabled": debug_state.copy_trading_system_ready,
            "monitoring_active": random.choice([True, False]),
            "followed_traders": random.randint(0, 10),
            "active_copies_today": random.randint(0, 25),
            "total_copies": random.randint(0, 500),
            "win_rate_pct": random.uniform(45, 80),
            "total_pnl_usd": f"{random.uniform(-1000, 5000):.2f}"
        },
        "recent_activity": [
            {
                "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 60))).isoformat(),
                "action": random.choice(["copy_buy", "copy_sell", "trader_added", "risk_block"]),
                "trader": f"0x{random.randint(1000000, 9999999):07x}...{random.randint(1000, 9999):04x}",
                "symbol": random.choice(["PEPE/WETH", "DOGE/USDC", "SHIB/USDT"]),
                "amount_usd": f"{random.uniform(50, 1000):.2f}"
            }
            for _ in range(5)
        ],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@api_router.get("/copy/traders")
async def get_followed_traders() -> Dict[str, Any]:
    """
    Get list of mock followed traders.
    
    Returns:
        List of mock followed traders with their performance metrics.
    """
    traders = []
    
    for i in range(random.randint(2, 8)):
        trader = {
            "id": f"trader_{i+1}",
            "wallet_address": f"0x{random.randint(1000000000, 9999999999):010x}{random.randint(100000000, 999999999):09x}",
            "name": f"Top Trader #{i+1}",
            "chain": random.choice(["ethereum", "bsc", "base"]),
            "copy_settings": {
                "copy_percentage": random.uniform(2.0, 10.0),
                "max_position_usd": random.uniform(500, 2000),
                "enabled": random.choice([True, False])
            },
            "performance": {
                "win_rate_pct": random.uniform(50, 90),
                "total_trades": random.randint(10, 200),
                "pnl_30d_usd": f"{random.uniform(-500, 2000):.2f}",
                "avg_hold_time_hours": random.uniform(2, 48)
            },
            "last_trade": (datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 24))).isoformat()
        }
        traders.append(trader)
    
    return {
        "status": "success",
        "traders": traders,
        "total_count": len(traders),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# System Debug Endpoints
@api_router.get("/debug/system")
async def get_debug_system_info() -> Dict[str, Any]:
    """Get comprehensive system debug information."""
    system_status = debug_state.get_system_status()
    
    return {
        "status": "success",
        "debug_info": {
            "application": {
                "name": "DEX Sniper Pro Debug",
                "version": "1.4.0-debug",
                "mode": "development"
            },
            "modules": {
                "django_initialized": debug_state.django_initialized,
                "copy_mock_available": debug_state.copy_mock_available,
                "copy_trading_ready": debug_state.copy_trading_system_ready
            },
            "websockets": {
                "paper_clients": debug_state.get_paper_client_count(),
                "metrics_clients": debug_state.get_metrics_client_count(),
                "thought_log_active": debug_state.thought_log_active
            },
            "system_status": system_status
        },
        "available_endpoints": [
            "/health",
            "/health/live", 
            "/health/ready",
            "/api/v1/paper/toggle",
            "/api/v1/paper/status",
            "/api/v1/paper/mock-trade",
            "/api/v1/opportunities/live",
            "/api/v1/opportunities/stats",
            "/api/v1/copy/status",
            "/api/v1/copy/traders",
            "/ws/paper",
            "/ws/metrics"
        ],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# Missing endpoints that frontend expects
@api_router.get("/intelligence/status")
async def get_intelligence_status() -> Dict[str, Any]:
    """Get intelligence system status."""
    return {
        "status": "success",
        "intelligence": {
            "enabled": False,
            "advanced_risk": False,
            "mempool_monitoring": False,
            "social_analysis": False
        },
        "system_health": "healthy",  # Add missing field
        "analysis_queue": {
            "pending": 0,
            "processing": 0,
            "completed_today": 0
        },
        "resources": {
            "cpu_usage": 15.2,
            "memory_usage": 45.8,
            "api_calls_remaining": 10000
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@api_router.get("/metrics/paper")
async def get_paper_metrics() -> Dict[str, Any]:
    """Get paper trading metrics."""
    return {
        "status": "success",
        "metrics": {
            "trades_today": random.randint(0, 20),
            "pnl_usd": f"{random.uniform(-100, 500):.2f}",
            "win_rate": random.uniform(40, 80),
            "total_volume": f"{random.uniform(1000, 10000):.2f}"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@api_router.get("/copy/trades")
async def get_copy_trades(limit: int = Query(default=50)) -> Dict[str, Any]:
    """Get copy trading history."""
    trades = []
    for i in range(min(limit, 10)):
        trades.append({
            "id": f"trade_{i+1}",
            "trader_address": f"0x{random.randint(1000000, 9999999):07x}...{random.randint(1000, 9999):04x}",
            "symbol": random.choice(["PEPE/WETH", "DOGE/USDC", "SHIB/USDT"]),
            "side": random.choice(["buy", "sell"]),
            "amount_usd": f"{random.uniform(50, 1000):.2f}",
            "status": random.choice(["completed", "pending", "failed"]),
            "timestamp": (datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 24))).isoformat()
        })
    
    return {
        "status": "success",
        "data": trades,
        "count": len(trades),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@api_router.get("/copy/discovery/status")
async def get_discovery_status() -> Dict[str, Any]:
    """Get copy trading discovery status."""
    return {
        "status": "success",
        "discovery": {
            "enabled": False,
            "scanning": False,
            "candidates_found": 0
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@api_router.get("/trades/")
async def get_trades() -> Dict[str, Any]:
    """Get trading history."""
    return {
        "status": "success", 
        "data": [],
        "count": 0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@api_router.get("/tokens/")
async def get_tokens() -> Dict[str, Any]:
    """Get token list."""
    return {
        "status": "success",
        "data": [],
        "count": 0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@api_router.get("/providers/")
async def get_providers() -> Dict[str, Any]:
    """Get provider list."""
    return {
        "status": "success",
        "data": [],
        "count": 0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@api_router.get("/bot/status")
async def get_bot_status() -> Dict[str, Any]:
    """Get bot status."""
    return {
        "status": "success",
        "bot": {
            "active": False,
            "mode": "paper",
            "uptime": "0s"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# Cleanup task for disconnected WebSocket clients
async def cleanup_disconnected_clients() -> Dict[str, int]:
    """
    Clean up disconnected WebSocket clients.
    
    Returns:
        Count of clients removed.
    """
    removed_count = debug_state.cleanup_disconnected_clients()
    
    if removed_count > 0:
        logger.info(f"Cleanup task removed {removed_count} disconnected clients")
    
    return {
        "removed_clients": removed_count,
        "current_paper_clients": debug_state.get_paper_client_count(),
        "current_metrics_clients": debug_state.get_metrics_client_count()
    }