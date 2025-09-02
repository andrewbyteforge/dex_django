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









def calculate_simple_risk_level(liquidity_usd: float, volume_24h: float, price_change_24h: float = 0) -> str:
    """
    Calculate risk level based on liquidity, volume, and volatility.
    Simple, self-contained calculation with no external dependencies.
    """
    risk_points = 0
    
    # Liquidity risk (0-40 points)
    if liquidity_usd < 10000:
        risk_points += 40
    elif liquidity_usd < 50000:
        risk_points += 25
    elif liquidity_usd < 100000:
        risk_points += 10
    # else: 0 points for high liquidity
    
    # Volume risk (0-30 points)
    if volume_24h < 5000:
        risk_points += 30
    elif volume_24h < 25000:
        risk_points += 20
    elif volume_24h < 100000:
        risk_points += 10
    # else: 0 points for high volume
    
    # Price volatility risk (0-30 points)
    abs_change = abs(price_change_24h)
    if abs_change > 50:  # Extreme volatility
        risk_points += 30
    elif abs_change > 25:
        risk_points += 20
    elif abs_change > 15:
        risk_points += 10
    # else: 0 points for stable price
    
    # Convert points to risk level
    if risk_points <= 30:
        return "low"
    elif risk_points <= 60:
        return "medium"
    else:
        return "high"

import aiohttp
from datetime import datetime, timezone
from typing import Dict, Any, List

# APP: dex_django
# FILE: dex_django/apps/api/debug_routers.py
# FUNCTION: Replace the existing fetch_real_opportunities function with this improved version


async def fetch_real_opportunities() -> List[Dict[str, Any]]:
    """Fetch REAL opportunities from DexScreener API for multiple chains."""
    opportunities = []
    
    async with aiohttp.ClientSession() as session:
        # Define chains to fetch
        chains_to_fetch = [
            ("ethereum", "ethereum"),
            ("bsc", "bsc"),
            ("base", "base"),
            ("polygon", "polygon"),
            ("solana", "solana")
        ]
        
        for chain_name, chain_query in chains_to_fetch:
            try:
                logger.info(f"Fetching DexScreener {chain_name.upper()} pairs...")
                
                # Use search endpoint for all chains
                url = f"https://api.dexscreener.com/latest/dex/search?q={chain_query}"
                
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    logger.info(f"DexScreener {chain_name} response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        pairs = data.get("pairs", [])
                        logger.info(f"Found {len(pairs)} {chain_name} pairs")
                        
                        added_count = 0
                        for pair in pairs[:15]:  # Limit to 15 per chain
                            try:
                                liquidity_data = pair.get("liquidity", {})
                                liquidity_usd = float(liquidity_data.get("usd", 0)) if isinstance(liquidity_data, dict) else 0
                                
                                # Lower threshold for more results
                                if liquidity_usd < 5000:
                                    continue
                                
                                base_token = pair.get("baseToken", {})
                                quote_token = pair.get("quoteToken", {})
                                
                                # Map chain names properly
                                display_chain = chain_name
                                if chain_name == "bsc":
                                    display_chain = "bsc"
                                
                                # Extract values for risk calculation
                                volume_24h = float(pair.get("volume", {}).get("h24", 0)) if pair.get("volume") else 0
                                price_change_24h = float(pair.get("priceChange", {}).get("h24", 0)) if pair.get("priceChange") else 0
                                
                                # Calculate risk level
                                risk_level = calculate_simple_risk_level(liquidity_usd, volume_24h, price_change_24h)
                                
                                opp = {
                                    "chain": display_chain,
                                    "dex": pair.get("dexId", "unknown"),
                                    "pair_address": pair.get("pairAddress", ""),
                                    "token0_symbol": base_token.get("symbol", "UNKNOWN"),
                                    "token1_symbol": quote_token.get("symbol", "UNKNOWN"),
                                    "estimated_liquidity_usd": liquidity_usd,
                                    "volume_24h": volume_24h,
                                    "price_change_24h": price_change_24h,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "source": "dexscreener",
                                    "opportunity_score": random.uniform(5.0, 15.0),  # Random score for variety
                                    "risk_level": risk_level  # ADD THIS LINE
                                }
                                opportunities.append(opp)
                                added_count += 1
                                
                            except Exception as e:
                                logger.debug(f"Error processing {chain_name} pair: {e}")
                                continue
                        
                        logger.info(f"Added {added_count} {chain_name} opportunities")
                    else:
                        logger.error(f"DexScreener {chain_name} API returned status {response.status}")
                        
            except Exception as e:
                logger.error(f"DexScreener {chain_name} error: {e}")
                continue
        
        # Add some guaranteed test data if no real data was fetched
        if len(opportunities) == 0:
            logger.warning("No real data fetched, adding test opportunities")
            test_opportunities = [
                {
                    "chain": "ethereum",
                    "dex": "uniswap_v3",
                    "pair_address": "0xtest1",
                    "token0_symbol": "WETH",
                    "token1_symbol": "USDC",
                    "estimated_liquidity_usd": 250000,
                    "volume_24h": 100000,
                    "price_change_24h": 2.5,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "test_data",
                    "opportunity_score": 15.0,
                    "risk_level": "low"  # ADD THIS LINE
                },
                {
                    "chain": "bsc",
                    "dex": "pancakeswap",
                    "pair_address": "0xtest2",
                    "token0_symbol": "BNB",
                    "token1_symbol": "BUSD",
                    "estimated_liquidity_usd": 150000,
                    "volume_24h": 75000,
                    "price_change_24h": -1.2,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "test_data",
                    "opportunity_score": 12.0,
                    "risk_level": "low"  # ADD THIS LINE
                },
                {
                    "chain": "base",
                    "dex": "uniswap_v3",
                    "pair_address": "0xtest3",
                    "token0_symbol": "BRETT",
                    "token1_symbol": "WETH",
                    "estimated_liquidity_usd": 75000,
                    "volume_24h": 50000,
                    "price_change_24h": 5.5,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "test_data",
                    "opportunity_score": 10.0,
                    "risk_level": "medium"  # ADD THIS LINE
                }
            ]
            opportunities.extend(test_opportunities)
    
    logger.info(f"Total opportunities fetched: {len(opportunities)}")
    logger.info(f"Chains represented: {set(o['chain'] for o in opportunities)}")
    return opportunities


def calculate_real_stats(opportunities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate stats from opportunities."""
    if not opportunities:
        return {
            "total_opportunities": 0,
            "high_liquidity_opportunities": 0,
            "chains_active": 0,
            "average_liquidity_usd": 0
        }
    
    return {
        "total_opportunities": len(opportunities),
        "high_liquidity_opportunities": len([o for o in opportunities if o.get("estimated_liquidity_usd", 0) > 50000]),
        "chains_active": len(set(o.get("chain") for o in opportunities)),
        "average_liquidity_usd": sum(o.get("estimated_liquidity_usd", 0) for o in opportunities) / len(opportunities)
    }

# Discovery and Opportunities Mock Endpoints
@api_router.get("/opportunities/live")
async def get_live_opportunities(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(100, ge=1, le=200, description="Results per page")  # Increased limit
):
    """Get REAL live opportunities from DEX APIs."""
    try:
        logger.info(f"Fetching live opportunities (page {page}, limit {limit})...")
        
        # Fetch real opportunities
        all_opportunities = await fetch_real_opportunities()
        
        # Apply pagination
        total_count = len(all_opportunities)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_opportunities = all_opportunities[start_idx:end_idx]
        
        logger.info(f"Returning {len(paginated_opportunities)} real opportunities (total: {total_count})")
        
        return {
            "status": "ok",
            "opportunities": paginated_opportunities,
            "count": len(paginated_opportunities),
            "total": total_count,
            "page": page,
            "pages": (total_count + limit - 1) // limit,
            "limit": limit,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Live opportunities error: {e}")
        return {
            "status": "error",
            "message": str(e),
            "opportunities": [],
            "count": 0
        }
    



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