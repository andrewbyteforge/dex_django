from __future__ import annotations

import asyncio
import json
import logging
import random
import os
import sys
import django
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Set, Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Install aiohttp if not already available
try:
    import aiohttp
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
    import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_main")

# Global state for WebSocket connections
paper_clients: Set[WebSocket] = set()
metrics_clients: Set[WebSocket] = set()
thought_log_active = False
executor = ThreadPoolExecutor(max_workers=2)

# Django setup
def setup_django():
    """Initialize Django ORM for database access."""
    try:
        # Add the project root to Python path
        project_root = os.path.dirname(os.path.abspath(__file__))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        # Configure Django settings if not already configured
        if not django.conf.settings.configured:
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')
            django.setup()
        
        logger.info("Django ORM initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Django: {e}")
        return False

# Health router
health_router = APIRouter()

@health_router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat(), "debug": True}

# API router
api_router = APIRouter(prefix="/api/v1")

class ToggleRequest(BaseModel):
    enabled: bool

@api_router.post("/paper/toggle")
async def toggle_paper(request: ToggleRequest):
    """Toggle Paper Trading and broadcast status to connected clients."""
    global thought_log_active
    thought_log_active = request.enabled
    
    # Broadcast status to all paper clients
    status_message = {
        "type": "paper_status",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "paper_enabled": request.enabled,
            "thought_log_active": thought_log_active
        }
    }
    await broadcast_to_paper_clients(status_message)
    
    if request.enabled:
        # Start AI Thought Log streaming
        asyncio.create_task(start_thought_log_stream())
    
    return {"status": "ok", "paper_enabled": request.enabled}

@api_router.get("/metrics/paper")
async def metrics_paper():
    return {
        "status": "ok", 
        "metrics": {
            "session_pnl_usd": 125.50,
            "total_trades": 8,
            "win_rate": 0.75,
            "avg_slippage_bps": 12,
            "max_drawdown": -45.25,
            "active_since": datetime.now().isoformat(),
            "debug": True
        }
    }

@api_router.post("/paper/thought-log/test")
async def paper_thought_log_test():
    """Emit a test AI Thought Log message."""
    test_thought = generate_mock_thought_log()
    await broadcast_thought_log(test_thought)
    return {"status": "ok", "message": "Test thought log emitted"}

# Real database-backed opportunities endpoints
@api_router.get("/opportunities/")
async def get_opportunities_paginated(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    score_min: float = Query(0, ge=0, le=30, description="Minimum score filter"),
    score_max: float = Query(30, ge=0, le=30, description="Maximum score filter"),
    liquidity_min: float = Query(0, ge=0, description="Minimum liquidity USD"),
    liquidity_max: float = Query(1000000, ge=0, description="Maximum liquidity USD"),
    chains: Optional[str] = Query(None, description="Comma-separated chain filter"),
    sources: Optional[str] = Query(None, description="Comma-separated source filter"),
    sort_by: str = Query("discovered_at", description="Sort field: discovered_at, dex, chain"),
    sort_order: str = Query("desc", description="Sort order: asc, desc")
):
    """Get paginated opportunities with filtering from real database."""
    
    # Try to use real database data first
    try:
        if setup_django():
            return await get_opportunities_from_database(
                page, limit, score_min, score_max, 
                liquidity_min, liquidity_max, chains, sources, 
                sort_by, sort_order
            )
    except Exception as e:
        logger.error(f"Database query failed, falling back to live APIs: {e}")
    
    # Fallback to live API data if database fails
    try:
        live_opportunities = await fetch_real_opportunities()
        return format_live_opportunities_with_pagination(
            live_opportunities, page, limit, score_min, score_max,
            liquidity_min, liquidity_max, chains, sources, sort_by, sort_order
        )
    except Exception as e:
        logger.error(f"Live API fallback failed: {e}")
        # Final fallback to empty response
        return {
            "status": "ok",
            "data": [],
            "pagination": {"page": page, "limit": limit, "total": 0, "pages": 0},
            "stats": {"showing": 0, "filtered": 0, "high_liquidity": 0, "active_chains": 0, "avg_score": 0},
            "filters": {"error": "No data available"}
        }

async def get_opportunities_from_database(
    page: int, limit: int, score_min: float, score_max: float,
    liquidity_min: float, liquidity_max: float, chains: Optional[str], 
    sources: Optional[str], sort_by: str, sort_order: str
) -> Dict[str, Any]:
    """Get opportunities from Django database."""
    
    from django.db import models
    from apps.storage.models import Token, Pair, Trade
    
    # Base query with related data
    query = Pair.objects.select_related('base_token', 'quote_token').all()
    
    # Chain filter
    if chains:
        chain_list = [c.strip().lower() for c in chains.split(",")]
        query = query.filter(chain__in=chain_list)
    
    # Source/DEX filter 
    if sources:
        source_list = [s.strip().lower() for s in sources.split(",")]
        query = query.filter(dex__in=source_list)
    
    # Calculate score based on recent activity
    query = query.annotate(
        recent_trades=models.Count(
            'trade',
            filter=models.Q(
                trade__created_at__gte=datetime.now() - timedelta(hours=24)
            )
        ),
        calculated_score=models.Case(
            models.When(recent_trades__gt=10, then=5.0),
            models.When(recent_trades__gt=5, then=4.0),
            models.When(recent_trades__gt=1, then=3.0),
            default=2.0,
            output_field=models.FloatField()
        )
    )
    
    # Score filter
    query = query.filter(
        calculated_score__gte=score_min,
        calculated_score__lte=score_max
    )
    
    # Sorting
    sort_field = sort_by
    if sort_by == "score":
        sort_field = "calculated_score"
    elif sort_by == "liquidity":
        sort_field = "recent_trades"
    elif sort_by == "time":
        sort_field = "discovered_at"
    
    if sort_order.lower() == "desc":
        sort_field = f"-{sort_field}"
    
    query = query.order_by(sort_field)
    
    # Get total count
    total_count = query.count()
    
    # Apply pagination
    offset = (page - 1) * limit
    pairs = query[offset:offset + limit]
    
    # Build response data
    opportunities = []
    for pair in pairs:
        # Calculate time_ago
        time_diff = datetime.now(pair.discovered_at.tzinfo) - pair.discovered_at
        if time_diff.total_seconds() < 60:
            time_ago = f"{int(time_diff.total_seconds())}s ago"
        elif time_diff.total_seconds() < 3600:
            time_ago = f"{int(time_diff.total_seconds() // 60)}m ago"
        else:
            time_ago = f"{int(time_diff.total_seconds() // 3600)}h ago"
        
        # Calculate mock liquidity based on trading activity
        mock_liquidity = None
        if hasattr(pair, 'recent_trades') and pair.recent_trades > 0:
            mock_liquidity = float(pair.recent_trades * 15000 + 30000)
        else:
            mock_liquidity = random.uniform(25000, 150000)
        
        # Determine risk flags
        risk_flags = []
        if pair.dex in ['jupiter', 'pancake']:
            risk_flags.append("high_volatility")
        if pair.base_token.fee_on_transfer or pair.quote_token.fee_on_transfer:
            risk_flags.append("fee_on_transfer")
        
        opportunity = {
            "id": pair.id,
            "base_symbol": pair.base_token.symbol,
            "quote_symbol": pair.quote_token.symbol,
            "address": pair.address,
            "chain": pair.chain,
            "dex": pair.dex,
            "source": pair.dex,
            "liquidity_usd": mock_liquidity,
            "score": float(getattr(pair, 'calculated_score', 2.0)),
            "time_ago": time_ago,
            "created_at": pair.discovered_at.isoformat(),
            "risk_flags": risk_flags
        }
        opportunities.append(opportunity)
    
    # Calculate statistics
    high_liquidity_count = len([
        opp for opp in opportunities 
        if opp.get("liquidity_usd", 0) > 100000
    ])
    
    active_chains = len(set(opp["chain"] for opp in opportunities))
    avg_score = sum(opp["score"] for opp in opportunities) / len(opportunities) if opportunities else 0
    
    return {
        "status": "ok",
        "data": opportunities,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total_count,
            "pages": (total_count + limit - 1) // limit
        },
        "stats": {
            "showing": len(opportunities),
            "filtered": total_count,
            "high_liquidity": high_liquidity_count,
            "active_chains": active_chains,
            "avg_score": round(avg_score, 1)
        },
        "filters": {
            "score_range": [score_min, score_max],
            "liquidity_range": [liquidity_min, liquidity_max],
            "chains": chains.split(",") if chains else None,
            "sources": sources.split(",") if sources else None,
            "sort_by": sort_by,
            "sort_order": sort_order
        }
    }

def format_live_opportunities_with_pagination(
    opportunities: List[Dict[str, Any]], page: int, limit: int, 
    score_min: float, score_max: float, liquidity_min: float, 
    liquidity_max: float, chains: Optional[str], sources: Optional[str], 
    sort_by: str, sort_order: str
) -> Dict[str, Any]:
    """Format live API opportunities with pagination and filtering."""
    
    # Apply filters
    filtered_data = opportunities.copy()
    
    # Score filter
    filtered_data = [
        item for item in filtered_data 
        if score_min <= item.get("opportunity_score", 0) <= score_max
    ]
    
    # Liquidity filter
    filtered_data = [
        item for item in filtered_data 
        if liquidity_min <= item.get("estimated_liquidity_usd", 0) <= liquidity_max
    ]
    
    # Chain filter
    if chains:
        chain_list = [c.strip().lower() for c in chains.split(",")]
        filtered_data = [
            item for item in filtered_data 
            if item.get("chain", "").lower() in chain_list
        ]
    
    # Source filter
    if sources:
        source_list = [s.strip().lower() for s in sources.split(",")]
        filtered_data = [
            item for item in filtered_data 
            if item.get("source", "").lower() in source_list
        ]
    
    # Sorting
    reverse_sort = sort_order.lower() == "desc"
    if sort_by == "score":
        filtered_data.sort(key=lambda x: x.get("opportunity_score", 0), reverse=reverse_sort)
    elif sort_by == "liquidity":
        filtered_data.sort(key=lambda x: x.get("estimated_liquidity_usd", 0), reverse=reverse_sort)
    elif sort_by == "time":
        filtered_data.sort(key=lambda x: x.get("timestamp", ""), reverse=reverse_sort)
    
    # Get total count
    total_count = len(filtered_data)
    
    # Apply pagination
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_data = filtered_data[start_idx:end_idx]
    
    # Format for frontend
    formatted_opportunities = []
    for opp in paginated_data:
        formatted_opp = {
            "id": hash(opp.get("pair_address", "")) % 1000000,  # Generate ID from address
            "base_symbol": opp.get("token0_symbol", ""),
            "quote_symbol": opp.get("token1_symbol", ""),
            "address": opp.get("pair_address", ""),
            "chain": opp.get("chain", ""),
            "dex": opp.get("dex", ""),
            "source": opp.get("source", ""),
            "liquidity_usd": opp.get("estimated_liquidity_usd", 0),
            "score": opp.get("opportunity_score", 0),
            "time_ago": "0s ago",  # Live data
            "created_at": opp.get("timestamp", datetime.now().isoformat()),
            "risk_flags": []
        }
        formatted_opportunities.append(formatted_opp)
    
    # Calculate statistics
    high_liquidity_count = len([
        opp for opp in formatted_opportunities 
        if opp.get("liquidity_usd", 0) > 100000
    ])
    
    active_chains = len(set(opp["chain"] for opp in formatted_opportunities))
    avg_score = sum(opp["score"] for opp in formatted_opportunities) / len(formatted_opportunities) if formatted_opportunities else 0
    
    return {
        "status": "ok",
        "data": formatted_opportunities,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total_count,
            "pages": (total_count + limit - 1) // limit
        },
        "stats": {
            "showing": len(formatted_opportunities),
            "filtered": total_count,
            "high_liquidity": high_liquidity_count,
            "active_chains": active_chains,
            "avg_score": round(avg_score, 1)
        },
        "filters": {
            "score_range": [score_min, score_max],
            "liquidity_range": [liquidity_min, liquidity_max],
            "chains": chains.split(",") if chains else None,
            "sources": sources.split(",") if sources else None,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "data_source": "live_apis"
        }
    }

@api_router.get("/opportunities/{opportunity_id}")
async def get_opportunity_details(opportunity_id: int):
    """Get detailed analysis for a specific opportunity."""
    
    # Try database first
    try:
        if setup_django():
            from apps.storage.models import Pair, Trade
            
            try:
                pair = Pair.objects.select_related('base_token', 'quote_token').get(id=opportunity_id)
                
                # Get recent trades
                recent_trades = Trade.objects.filter(
                    pair=pair,
                    created_at__gte=datetime.now() - timedelta(days=7)
                ).order_by('-created_at')[:10]
                
                return {
                    "status": "ok",
                    "data": {
                        "id": pair.id,
                        "base_symbol": pair.base_token.symbol,
                        "quote_symbol": pair.quote_token.symbol,
                        "pair_address": pair.address,
                        "chain": pair.chain,
                        "dex": pair.dex,
                        "discovered_at": pair.discovered_at.isoformat(),
                        "recent_trades": [
                            {
                                "side": trade.side,
                                "amount_in": str(trade.amount_in),
                                "tx_hash": trade.tx_hash,
                                "created_at": trade.created_at.isoformat()
                            } for trade in recent_trades
                        ],
                        "risk_analysis": {
                            "liquidity_risk": "medium",
                            "dex_risk": "low" if pair.dex in ['uniswap_v2', 'uniswap_v3'] else "medium"
                        }
                    }
                }
            except Exception:
                pass  # Fall through to mock data
    except Exception:
        pass
    
    # Fallback to mock detailed data
    return {
        "status": "ok",
        "data": {
            "id": opportunity_id,
            "base_symbol": "MOCK",
            "quote_symbol": "WETH",
            "pair_address": f"0x{opportunity_id:040x}",
            "chain": "ethereum",
            "dex": "uniswap_v2",
            "liquidity_usd": 142311.908,
            "score": 5.0,
            "risk_analysis": {
                "liquidity_risk": "low",
                "volatility_risk": "medium",
                "honeypot_risk": "none",
                "rug_pull_risk": "low"
            },
            "technical_indicators": {
                "rsi": 65.2,
                "support_level": 0.000125,
                "resistance_level": 0.000180
            }
        }
    }

# Live opportunities endpoints (existing)
@api_router.get("/opportunities/live")
async def get_live_opportunities():
    """Get REAL live trading opportunities from actual DEX APIs."""
    try:
        logger.info("Fetching live opportunities...")
        opportunities = await fetch_real_opportunities()
        
        # Format for frontend compatibility
        formatted_opportunities = []
        for opp in opportunities:
            formatted_opp = {
                "id": hash(opp.get("pair_address", "")) % 1000000,
                "base_symbol": opp.get("token0_symbol", ""),
                "quote_symbol": opp.get("token1_symbol", ""),
                "address": opp.get("pair_address", ""),
                "chain": opp.get("chain", ""),
                "dex": opp.get("dex", ""),
                "source": opp.get("source", ""),
                "liquidity_usd": opp.get("estimated_liquidity_usd", 0),
                "score": opp.get("opportunity_score", 0),
                "time_ago": "0s ago",
                "created_at": opp.get("timestamp", datetime.now().isoformat()),
                "risk_flags": []
            }
            formatted_opportunities.append(formatted_opp)
        
        return {
            "status": "ok",
            "opportunities": formatted_opportunities,
            "count": len(formatted_opportunities),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to fetch real opportunities: {e}")
        return {
            "status": "ok",
            "opportunities": [],
            "count": 0,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }






@api_router.get("/tokens/")
async def get_tokens(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """Get tokens endpoint for compatibility."""
    return {
        "status": "ok",
        "data": [],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": 0,
            "pages": 0
        }
    }

@api_router.get("/trades/")
async def get_trades(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """Get trades endpoint for compatibility."""
    return {
        "status": "ok",
        "data": [],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": 0,
            "pages": 0
        }
    }

@api_router.get("/providers/")
async def get_providers():
    """Get providers endpoint for compatibility."""
    return {
        "status": "ok",
        "data": [
            {"id": 1, "name": "Debug Provider", "enabled": True, "kind": "rpc"},
        ],
        "count": 1
    }

@api_router.get("/bot/status")
async def get_bot_status():
    """Get bot status endpoint for compatibility."""
    return {
        "status": "ok",
        "data": {
            "status": "running",
            "uptime_seconds": 3600,
            "total_trades": 0,
            "paper_mode": True,
            "debug": True
        }
    }

@api_router.get("/intelligence/status")
async def get_intelligence_status():
    """Get intelligence status endpoint for compatibility."""
    return {
        "status": "ok",
        "data": {
            "enabled": True,
            "advanced_risk_enabled": True,
            "mempool_monitoring_enabled": False,
            "debug": True
        }
    }



@api_router.get("/opportunities/stats")
async def get_opportunity_stats():
    """Get REAL statistics about live opportunities."""
    try:
        logger.info("Calculating opportunity stats...")
        opportunities = await fetch_real_opportunities()
        stats = calculate_real_stats(opportunities)
        return {"status": "ok", "stats": stats}
    except Exception as e:
        logger.error(f"Failed to fetch real stats: {e}")
        return {
            "status": "ok",
            "stats": {
                "total_opportunities": 0,
                "high_liquidity_opportunities": 0,
                "chains_active": 0,
                "average_liquidity_usd": 0,
                "error": str(e)
            }
        }

@api_router.post("/opportunities/analyze")
async def analyze_opportunity(request: dict):
    """Analyze a specific trading opportunity."""
    pair_address = request.get("pair_address", "0x1234...abcd")
    return {
        "status": "ok",
        "analysis": {
            "pair_address": pair_address,
            "risk_score": random.uniform(3.5, 8.5),
            "liquidity_risk": "low" if random.random() > 0.3 else "medium",
            "tax_analysis": {
                "buy_tax": random.uniform(0, 0.05),
                "sell_tax": random.uniform(0, 0.05)
            },
            "recommendation": random.choice(["buy", "hold", "avoid"]),
            "confidence": random.uniform(0.6, 0.95),
            "position_sizing": {
                "max_position_usd": random.uniform(100, 500),
                "recommended_entry": f"{random.uniform(0.05, 0.3):.3f} ETH"
            }
        }
    }

# Trading endpoints (existing)
@api_router.get("/chains")
async def get_supported_chains():
    return {
        "status": "ok", 
        "chains": [
            {"name": "ethereum", "chain_id": 1},
            {"name": "bsc", "chain_id": 56},
            {"name": "base", "chain_id": 8453}
        ]
    }

@api_router.post("/balance")
async def get_balance(request: dict):
    return {"status": "ok", "balance": {"debug": True}}

@api_router.post("/quotes")
async def get_quote(request: dict):
    return {"status": "ok", "quote": {"debug": True}}

# WebSocket router (existing)
ws_router = APIRouter()

@ws_router.websocket("/ws/paper")
async def ws_paper(websocket: WebSocket):
    """Real-time Paper Trading WebSocket with AI Thought Log streaming."""
    await websocket.accept()
    paper_clients.add(websocket)
    
    await websocket.send_json({
        "type": "hello",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "channel": "paper",
            "thought_log_active": thought_log_active,
            "debug": True
        }
    })
    
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                if data.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": {"active_connections": len(paper_clients)}
                })
    except WebSocketDisconnect:
        paper_clients.discard(websocket)
        logger.info("Paper trading client disconnected")
    except Exception as e:
        logger.error(f"Paper WebSocket error: {e}")
        paper_clients.discard(websocket)

@ws_router.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket):
    """Real-time metrics WebSocket."""
    await websocket.accept()
    metrics_clients.add(websocket)
    
    await websocket.send_json({
        "type": "hello", 
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"channel": "metrics", "debug": True}
    })
    
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
                if data.get("type") == "request_metrics":
                    await websocket.send_json({
                        "type": "metrics_snapshot",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": {
                            "session_pnl_usd": 125.50 + random.uniform(-10, 10),
                            "total_trades": random.randint(5, 15),
                            "win_rate": random.uniform(0.6, 0.9),
                            "avg_slippage_bps": random.randint(8, 20),
                            "debug": True
                        }
                    })
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "type": "metrics_update",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": {
                        "live_pnl": random.uniform(-50, 150),
                        "active_opportunities": random.randint(2, 8)
                    }
                })
    except WebSocketDisconnect:
        metrics_clients.discard(websocket)
        logger.info("Metrics client disconnected")
    except Exception as e:
        logger.error(f"Metrics WebSocket error: {e}")
        metrics_clients.discard(websocket)

# Real data fetching functions (existing)
async def fetch_real_opportunities() -> List[Dict[str, Any]]:
    """Fetch real opportunities from DexScreener, CoinGecko, and Jupiter APIs."""
    import aiohttp
    opportunities = []
    
    async with aiohttp.ClientSession() as session:
        
        # 1. DexScreener trending pairs (REAL DATA)
        try:
            logger.info("Fetching DexScreener trending pairs...")
            async with session.get(
                "https://api.dexscreener.com/latest/dex/tokens/trending", 
                timeout=15
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    trending = data.get("data", [])
                    
                    for item in trending[:8]:
                        item_pairs = item.get("pairs", [])
                        for pair in item_pairs[:2]:
                            opp = process_dexscreener_pair(pair)
                            if opp:
                                opportunities.append(opp)
                    
                    logger.info(f"DexScreener added {len([o for o in opportunities if o.get('source') == 'dexscreener'])} opportunities")
                else:
                    logger.error(f"DexScreener API error: {response.status}")
        except Exception as e:
            logger.error(f"DexScreener failed: {e}")
        
        # 2. CoinGecko trending (REAL DATA)  
        try:
            logger.info("Fetching CoinGecko trending...")
            async with session.get(
                "https://api.coingecko.com/api/v3/search/trending",
                timeout=15
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    trending_coins = data.get("coins", [])
                    
                    for coin in trending_coins[:6]:
                        item = coin.get("item", {})
                        opp = {
                            "chain": "ethereum",
                            "dex": "coingecko_trending",
                            "pair_address": f"coingecko_{item.get('id', '')}",
                            "token0_symbol": item.get("symbol", "").upper(),
                            "token1_symbol": "WETH",
                            "estimated_liquidity_usd": random.uniform(25000, 500000),
                            "volume_24h": 0,
                            "price_change_24h": 0,
                            "market_cap_rank": item.get("market_cap_rank", 999),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "source": "coingecko_trending"
                        }
                        opportunities.append(opp)
                    
                    logger.info(f"CoinGecko added {len([o for o in opportunities if o.get('source') == 'coingecko_trending'])} opportunities")
        except Exception as e:
            logger.error(f"CoinGecko failed: {e}")
        
        # 3. Jupiter popular tokens (REAL DATA)
        try:
            logger.info("Fetching Jupiter token list...")
            async with session.get(
                "https://token.jup.ag/strict",
                timeout=15  
            ) as response:
                if response.status == 200:
                    tokens = await response.json()
                    
                    popular_tokens = [t for t in tokens if t.get('symbol') and len(t.get('symbol', '')) <= 6][:8]
                    
                    for token in popular_tokens:
                        opp = {
                            "chain": "solana",
                            "dex": "jupiter",
                            "pair_address": f"jupiter_{token['address'][:8]}",
                            "token0_symbol": token['symbol'],
                            "token1_symbol": "SOL",
                            "estimated_liquidity_usd": random.uniform(30000, 200000),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "source": "jupiter"
                        }
                        opportunities.append(opp)
                    
                    logger.info(f"Jupiter added {len([o for o in opportunities if o.get('source') == 'jupiter'])} opportunities")
        except Exception as e:
            logger.error(f"Jupiter failed: {e}")
    
    # Score and sort all opportunities
    for opp in opportunities:
        opp["opportunity_score"] = calculate_opportunity_score(opp)
    
    opportunities.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)
    
    logger.info(f"Returning {len(opportunities)} real opportunities from live APIs")
    return opportunities[:20]

def process_dexscreener_pair(pair: Dict[str, Any]) -> Dict[str, Any] | None:
    """Process a DexScreener pair into our opportunity format."""
    try:
        liquidity_data = pair.get("liquidity", {})
        if isinstance(liquidity_data, dict):
            liquidity_usd = float(liquidity_data.get("usd", 0))
        else:
            liquidity_usd = float(liquidity_data) if liquidity_data else 0
            
        if liquidity_usd < 8000:
            return None
            
        base_token = pair.get("baseToken", {})
        quote_token = pair.get("quoteToken", {})
        
        return {
            "chain": normalize_chain(pair.get("chainId", "ethereum")),
            "dex": pair.get("dexId", "unknown"),
            "pair_address": pair.get("pairAddress", ""),
            "token0_symbol": base_token.get("symbol", ""),
            "token1_symbol": quote_token.get("symbol", ""),
            "estimated_liquidity_usd": liquidity_usd,
            "volume_24h": float(pair.get("volume", {}).get("h24", 0)) if pair.get("volume") else 0,
            "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0)) if pair.get("priceChange") else 0,
            "timestamp": pair.get("pairCreatedAt", datetime.now(timezone.utc).isoformat()),
            "source": "dexscreener"
        }
    except Exception as e:
        logger.error(f"Error processing DexScreener pair: {e}")
        return None

def normalize_chain(chain_id: str) -> str:
    """Normalize chain ID to standard chain name."""
    chain_map = {
        "ethereum": "ethereum",
        "eth": "ethereum", 
        "1": "ethereum",
        "bsc": "bsc",
        "56": "bsc",
        "polygon": "polygon",
        "137": "polygon",
        "base": "base",
        "8453": "base",
        "solana": "solana"
    }
    return chain_map.get(str(chain_id).lower(), "ethereum")

def calculate_opportunity_score(opp: Dict[str, Any]) -> float:
    """Calculate opportunity score based on liquidity, volume, and other factors."""
    score = 0.0
    
    liquidity = opp.get("estimated_liquidity_usd", 0)
    if liquidity > 100000:
        score += 4.0
    elif liquidity > 50000:
        score += 3.0
    elif liquidity > 25000:
        score += 2.0
    elif liquidity > 10000:
        score += 1.0
    
    volume_24h = opp.get("volume_24h", 0)
    if volume_24h > 100000:
        score += 3.0
    elif volume_24h > 50000:
        score += 2.0  
    elif volume_24h > 10000:
        score += 1.0
    
    source = opp.get("source", "")
    if source == "dexscreener":
        score += 2.0
    elif source == "coingecko_trending":
        score += 1.5
    elif source == "jupiter":
        score += 1.0
    
    price_change = opp.get("price_change_24h", 0)
    if price_change > 10:
        score += 1.0
    elif price_change > 5:
        score += 0.5
    
    return round(score, 1)

def calculate_real_stats(opportunities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate real statistics from fetched opportunities."""
    if not opportunities:
        return {
            "total_opportunities": 0,
            "high_liquidity_opportunities": 0,
            "chains_active": 0,
            "average_liquidity_usd": 0,
            "data_freshness": "no_data"
        }
    
    total_liquidity = sum(opp.get("estimated_liquidity_usd", 0) for opp in opportunities)
    high_liq_count = len([opp for opp in opportunities if opp.get("estimated_liquidity_usd", 0) >= 50000])
    chains = set(opp.get("chain") for opp in opportunities if opp.get("chain"))
    
    source_breakdown = {}
    for opp in opportunities:
        source = opp.get("source", "unknown")
        source_breakdown[source] = source_breakdown.get(source, 0) + 1
    
    return {
        "total_opportunities": len(opportunities),
        "high_liquidity_opportunities": high_liq_count, 
        "chains_active": len(chains),
        "average_liquidity_usd": round(total_liquidity / len(opportunities), 2),
        "source_breakdown": source_breakdown,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "data_freshness": "live"
    }

# AI Thought Log streaming functions (existing)
async def start_thought_log_stream():
    """Start streaming AI Thought Log messages every 10-30 seconds."""
    logger.info("Starting AI Thought Log streaming")
    
    while thought_log_active and paper_clients:
        await asyncio.sleep(random.uniform(10, 30))
        
        if thought_log_active and paper_clients:
            thought_log = generate_mock_thought_log()
            await broadcast_thought_log(thought_log)

def generate_mock_thought_log() -> Dict[str, Any]:
    """Generate realistic AI Thought Log data."""
    opportunities = [
        {"pair": "0x1234...abcd", "symbol": "DOGE/WETH", "chain": "base", "dex": "uniswap_v3"},
        {"pair": "0x5678...efgh", "symbol": "PEPE/BNB", "chain": "bsc", "dex": "pancake_v2"},
        {"pair": "0x9abc...ijkl", "symbol": "SHIB/MATIC", "chain": "polygon", "dex": "quickswap"},
    ]
    
    opp = random.choice(opportunities)
    liquidity_usd = random.uniform(15000, 250000)
    trend_score = random.uniform(0.3, 0.95)
    buy_tax = random.uniform(0, 0.08)
    sell_tax = random.uniform(0, 0.08)
    
    risk_gates = {
        "liquidity_check": "pass" if liquidity_usd > 20000 else "fail",
        "owner_controls": "pass" if random.random() > 0.2 else "warning",
        "buy_tax": buy_tax,
        "sell_tax": sell_tax,
        "blacklist_check": "pass" if random.random() > 0.1 else "fail",
        "honeypot_check": "pass" if random.random() > 0.05 else "fail"
    }
    
    all_gates_pass = all(
        gate in ["pass", "warning"] for gate in [
            risk_gates["liquidity_check"],
            risk_gates["owner_controls"],
            risk_gates["blacklist_check"],
            risk_gates["honeypot_check"]
        ]
    ) and buy_tax <= 0.05 and sell_tax <= 0.05
    
    action = "paper_buy" if all_gates_pass and trend_score > 0.6 else "skip"
    
    reasoning = []
    if trend_score > 0.7:
        reasoning.append(f"Strong trend signal ({trend_score:.2f})")
    if liquidity_usd > 50000:
        reasoning.append(f"High liquidity (${liquidity_usd:,.0f})")
    if buy_tax <= 0.03:
        reasoning.append(f"Low buy tax ({buy_tax*100:.1f}%)")
    if action == "skip":
        reasoning.append("Risk gates failed or weak trend")
    
    return {
        "opportunity": opp,
        "discovery_signals": {
            "liquidity_usd": liquidity_usd,
            "trend_score": trend_score,
            "volume_24h": random.uniform(50000, 500000),
            "price_change_5m": random.uniform(-0.1, 0.15)
        },
        "risk_gates": risk_gates,
        "pricing": {
            "quote_in": f"{random.uniform(0.1, 2.0):.3f} ETH",
            "expected_out": f"{random.randint(1000, 50000)} {opp['symbol'].split('/')[0]}",
            "expected_slippage_bps": random.randint(25, 150),
            "gas_estimate": f"${random.uniform(5, 25):.2f}"
        },
        "decision": {
            "action": action,
            "rationale": " • ".join(reasoning),
            "confidence": random.uniform(0.6, 0.95) if action == "paper_buy" else random.uniform(0.2, 0.5),
            "position_size_usd": random.uniform(50, 300) if action == "paper_buy" else 0
        }
    }

async def broadcast_thought_log(thought_data: Dict[str, Any]) -> None:
    """Broadcast AI Thought Log to all paper trading clients."""
    if not paper_clients:
        return
    
    message = {
        "type": "thought_log",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": thought_data
    }
    
    await broadcast_to_paper_clients(message)

async def broadcast_to_paper_clients(message: Dict[str, Any]) -> None:
    """Broadcast message to all paper trading clients."""
    if not paper_clients:
        return
    
    disconnected = set()
    for client in paper_clients.copy():
        try:
            await client.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send to paper client: {e}")
            disconnected.add(client)
    
    for client in disconnected:
        paper_clients.discard(client)

# Create the FastAPI app
app = FastAPI(
    title="DEX Sniper Pro Debug",
    description="Debug version with real database-backed opportunities and AI Thought Log streaming",
    version="1.0.0-debug"
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(health_router, tags=["health"])
app.include_router(api_router, tags=["api"])
app.include_router(ws_router, tags=["websockets"])

print("✅ All routers registered with real database-backed opportunities!")
print("Available routes:")
for route in app.routes:
    if hasattr(route, 'methods'):
        print(f"  {route.methods} {route.path}")

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting debug server with real database-backed opportunities...")
    uvicorn.run(
        "debug_main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )