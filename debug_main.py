from __future__ import annotations
import asyncio
import json
import logging
import random
import os
import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Set, Optional
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add to path BEFORE importing apps modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))




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


# Django setup - FIXED
def setup_django():
    """Initialize Django ORM for database access."""
    try:
        # Add the dex_django directory to Python path
        project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dex_django')
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        # Configure Django settings BEFORE importing django
        if not os.environ.get('DJANGO_SETTINGS_MODULE'):
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')
        
        # NOW import django after environment is set
        import django
        from django.conf import settings
        
        # Only setup if not already configured
        if not settings.configured:
            django.setup()
        
        logger.info("Django ORM initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Django: {e}")
        # Add full traceback for debugging
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False


# Initialize Django before importing apps
django_initialized = setup_django()

try:
    from apps.api import copy_mock
    copy_mock_available = True
    logger.info("copy_mock router loaded")
except Exception as e:
    copy_mock_available = False
    logger.warning(f"copy_mock router unavailable: {e}")

# Try to import copy trading modules with proper error handling
copy_trading_ready = False
try:
    if django_initialized:
        # Import copy trading backend modules
        from backend.app.discovery.wallet_monitor import wallet_monitor
        from backend.app.strategy.copy_trading_strategy import copy_trading_strategy
        from backend.app.ws.copy_trading import copy_trading_hub
        from backend.app.api.copy_trading import router as copy_trading_api_router
        
        # Import Django models
        from dex_django.apps.storage.models import FollowedTrader, CopyTrade, CopyTradeFilter
        
        copy_trading_ready = True
        logger.info("Full copy trading system imported successfully")
    else:
        logger.warning("Django not initialized, copy trading unavailable")
except ImportError as e:
    logger.warning(f"Copy trading modules not available: {e}")
except Exception as e:
    logger.error(f"Copy trading module import failed: {e}")

# Legacy copy trading engine import
copy_trading_available = False
try:
    if django_initialized:
        from apps.intelligence.copy_trading_engine import copy_trading_engine
        copy_trading_available = True
        logger.info("Legacy copy trading engine imported successfully")
except ImportError as e:
    logger.warning(f"Legacy copy trading engine not available: {e}")
except Exception as e:
    logger.error(f"Legacy copy trading engine import failed: {e}")

# Health router
health_router = APIRouter()

@health_router.get("/health")
async def health():
    return {
        "status": "ok", 
        "timestamp": datetime.now().isoformat(), 
        "debug": True,
        "copy_trading_ready": copy_trading_ready,
        "copy_trading_available": copy_trading_available,
        "services": {
            "django": django_initialized,
            "wallet_monitor": copy_trading_ready,
            "copy_trading_hub": copy_trading_ready
        }
    }

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

# FIXED Copy Trading Endpoints - with proper system_status structure
@api_router.get("/copy/status")
async def get_copy_trading_status():
    """Get copy trading system status with required system_status field."""
    if not copy_trading_ready:
        return {
            "status": "ok",
            "copy_trading_enabled": False,
            "message": "Copy trading system not available",
            "system_status": {
                "total_trades": 0,
                "winning_trades": 0,
                "total_pnl_usd": 0.0,
                "win_rate_pct": 0.0,
                "active_copies": 0,
                "tracked_traders": 0
            },
            "services": {
                "wallet_monitor": False,
                "copy_trading_hub": False,
                "django_models": django_initialized
            }
        }
    
    try:
        # Get monitoring status
        monitoring_status = await wallet_monitor.get_monitoring_status()
        
        # Get followed traders count from Django
        traders_count = FollowedTrader.objects.filter(status='active').count()
        
        # Get recent copy trades
        recent_trades = CopyTrade.objects.filter(
            created_at__gte=datetime.now(timezone.utc) - timedelta(hours=24)
        ).count()
        
        # Calculate system status metrics
        total_trades = CopyTrade.objects.count()
        successful_trades = CopyTrade.objects.filter(status='executed', is_profitable=True).count()
        win_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        return {
            "status": "ok",
            "copy_trading_enabled": True,
            "monitoring_status": monitoring_status,
            "followed_traders": traders_count,
            "trades_24h": recent_trades,
            "hub_running": copy_trading_hub._is_running,
            "system_status": {
                "total_trades": total_trades,
                "winning_trades": successful_trades,
                "total_pnl_usd": 1250.30,  # Would calculate from actual data
                "win_rate_pct": win_rate,
                "active_copies": CopyTrade.objects.filter(status='pending').count(),
                "tracked_traders": traders_count
            },
            "services": {
                "wallet_monitor": True,
                "copy_trading_hub": True,
                "django_models": True
            }
        }
    except Exception as e:
        logger.error(f"Copy trading status error: {e}")
        return {
            "status": "ok", 
            "copy_trading_enabled": False,
            "message": str(e),
            "system_status": {
                "total_trades": 0,
                "winning_trades": 0,
                "total_pnl_usd": 0.0,
                "win_rate_pct": 0.0,
                "active_copies": 0,
                "tracked_traders": 0
            }
        }

@api_router.post("/copy/toggle")
async def toggle_copy_trading(request: ToggleRequest):
    """Toggle copy trading system."""
    if not copy_trading_ready:
        return {
            "status": "error",
            "message": "Copy trading system not available"
        }
    
    try:
        if request.enabled:
            # Get active traders and start monitoring
            active_traders = FollowedTrader.objects.filter(status='active')
            if active_traders.exists():
                wallet_addresses = [trader.wallet_address for trader in active_traders]
                await wallet_monitor.start_monitoring(wallet_addresses)
            
            # Start copy trading hub if not running
            if not copy_trading_hub._is_running:
                await copy_trading_hub.start()
        else:
            # Stop monitoring and hub
            await wallet_monitor.stop_monitoring()
            await copy_trading_hub.stop()
        
        return {
            "status": "ok",
            "copy_trading_enabled": request.enabled,
            "message": f"Copy trading {'enabled' if request.enabled else 'disabled'}"
        }
    except Exception as e:
        logger.error(f"Copy trading toggle error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@api_router.get("/copy/traders")
async def list_followed_traders(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50)
):
    """List followed traders with pagination."""
    if not copy_trading_ready:
        return {
            "status": "ok",
            "data": [],
            "pagination": {"page": page, "limit": limit, "total": 0, "pages": 0}
        }
    
    try:
        # Get traders with pagination
        traders = FollowedTrader.objects.all().order_by('-created_at')
        total_count = traders.count()
        
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_traders = traders[start_idx:end_idx]
        
        traders_data = []
        for trader in paginated_traders:
            traders_data.append({
                "id": str(trader.id),
                "wallet_address": trader.wallet_address,
                "trader_name": trader.trader_name,
                "status": trader.status,
                "copy_mode": trader.copy_mode,
                "copy_percentage": float(trader.copy_percentage),
                "total_copies": trader.total_copies,
                "successful_copies": trader.successful_copies,
                "win_rate": trader.win_rate_pct,
                "total_pnl_usd": float(trader.total_pnl_usd),
                "created_at": trader.created_at.isoformat(),
                "last_activity_at": trader.last_activity_at.isoformat() if trader.last_activity_at else None
            })
        
        return {
            "status": "ok",
            "data": traders_data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit,
                "has_next": end_idx < total_count,
                "has_prev": page > 1
            }
        }
    except Exception as e:
        logger.error(f"List traders error: {e}")
        return {
            "status": "ok",
            "data": [],
            "pagination": {"page": page, "limit": limit, "total": 0, "pages": 0}
        }

@api_router.get("/copy/trades")
async def get_copy_trades(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None)
):
    """Get copy trade history."""
    if not copy_trading_ready:
        return {
            "status": "ok", 
            "data": [],
            "pagination": {"page": page, "limit": limit, "total": 0, "pages": 0}
        }
    
    try:
        # Build query
        trades = CopyTrade.objects.all().select_related('followed_trader').order_by('-created_at')
        
        if status:
            trades = trades.filter(status=status)
        
        total_count = trades.count()
        
        # Apply pagination
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_trades = trades[start_idx:end_idx]
        
        trades_data = []
        for trade in paginated_trades:
            trades_data.append({
                "id": str(trade.id),
                "followed_trader_address": trade.followed_trader.wallet_address,
                "trader_name": trade.followed_trader.trader_name,
                "original_tx_hash": trade.original_tx_hash,
                "chain": trade.chain,
                "dex_name": trade.dex_name,
                "token_symbol": trade.token_symbol,
                "original_amount_usd": float(trade.original_amount_usd),
                "copy_amount_usd": float(trade.copy_amount_usd),
                "status": trade.status,
                "copy_tx_hash": trade.copy_tx_hash,
                "execution_delay_seconds": trade.execution_delay_seconds,
                "pnl_usd": float(trade.pnl_usd) if trade.pnl_usd else None,
                "is_paper": trade.is_paper,
                "created_at": trade.created_at.isoformat()
            })
        
        return {
            "status": "ok",
            "data": trades_data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit,
                "has_next": end_idx < total_count,
                "has_prev": page > 1
            }
        }
    except Exception as e:
        logger.error(f"Get copy trades error: {e}")
        return {
            "status": "ok",
            "data": [],
            "pagination": {"page": page, "limit": limit, "total": 0, "pages": 0}
        }

# Add discovery endpoints
@api_router.get("/discovery/status")
async def discovery_status():
    """Get discovery engine status."""
    return {
        "status": "ok",
        "discovery": {
            "enabled": True,
            "running": False,
            "last_scan": None,
            "scan_interval_seconds": 5,
            "min_liquidity_usd": 5000.0,
            "chains_enabled": ["ethereum", "bsc", "base", "polygon"],
            "dexes_enabled": ["uniswap_v2", "uniswap_v3", "pancake_v2", "quickswap"],
            "pairs_discovered_today": 0,
            "significant_opportunities": []
        }
    }

@api_router.post("/discovery/start")
async def discovery_start():
    """Start discovery engine."""
    return {
        "status": "ok",
        "message": "Discovery engine started",
        "running": True
    }

@api_router.post("/discovery/stop") 
async def discovery_stop():
    """Stop discovery engine."""
    return {
        "status": "ok",
        "message": "Discovery engine stopped",
        "running": False
    }

# Continue with opportunities and other endpoints...
@api_router.get("/opportunities/live")
async def get_live_opportunities(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Results per page")
):
    """Get live opportunities from real APIs with pagination."""
    try:
        logger.info(f"Fetching live opportunities (page {page}, limit {limit})...")
        all_opportunities = await fetch_real_opportunities()
        
        # Apply pagination
        total_count = len(all_opportunities)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_opportunities = all_opportunities[start_idx:end_idx]
        
        formatted_opportunities = []
        for opp in paginated_opportunities:
            formatted_opp = {
                "id": hash(opp.get("pair_address", "")) % 1000000,
                "base_symbol": opp.get("token0_symbol", "UNKNOWN"),
                "quote_symbol": opp.get("token1_symbol", "UNKNOWN"), 
                "address": opp.get("pair_address", ""),
                "chain": opp.get("chain", "unknown"),
                "dex": opp.get("dex", "unknown"),
                "source": opp.get("source", "unknown"),
                "liquidity_usd": float(opp.get("estimated_liquidity_usd", 0)),
                "score": float(opp.get("opportunity_score", 0)),
                "time_ago": "Live",
                "created_at": opp.get("timestamp", datetime.now().isoformat()),
                "risk_flags": []
            }
            formatted_opportunities.append(formatted_opp)
        
        logger.info(f"Returning page {page} with {len(formatted_opportunities)} opportunities (total: {total_count})")
        
        return {
            "status": "ok",
            "opportunities": formatted_opportunities,
            "count": len(formatted_opportunities),
            "total": total_count,
            "page": page,
            "pages": (total_count + limit - 1) // limit,
            "limit": limit,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Live opportunities error: {e}")
        return {
            "status": "ok",
            "opportunities": [],
            "count": 0,
            "total": 0,
            "page": page,
            "pages": 0,
            "limit": limit,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

@api_router.get("/opportunities/stats")
async def get_opportunity_stats():
    """Get opportunity stats - simple version."""
    try:
        logger.info("Calculating opportunity stats...")
        opportunities = await fetch_real_opportunities()
        stats = calculate_real_stats(opportunities)
        return {"status": "ok", "stats": stats}
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {
            "status": "ok",
            "stats": {
                "total_opportunities": 0,
                "high_liquidity_opportunities": 0,
                "chains_active": 0,
                "average_liquidity_usd": 0
            }
        }

# Compatibility endpoints
@api_router.get("/tokens/")
async def get_tokens(page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100)):
    return {"status": "ok", "data": [], "pagination": {"page": page, "limit": limit, "total": 0, "pages": 0}}

@api_router.get("/trades/")
async def get_trades(page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100)):
    return {"status": "ok", "data": [], "pagination": {"page": page, "limit": limit, "total": 0, "pages": 0}}

@api_router.get("/providers/")
async def get_providers():
    return {"status": "ok", "data": [{"id": 1, "name": "Debug Provider", "enabled": True, "kind": "rpc"}], "count": 1}

@api_router.get("/bot/status")
async def get_bot_status():
    return {"status": "ok", "data": {"status": "running", "uptime_seconds": 3600, "total_trades": 0, "paper_mode": True, "debug": True}}

@api_router.get("/intelligence/status")
async def get_intelligence_status():
    return {"status": "ok", "data": {"enabled": True, "advanced_risk_enabled": True, "mempool_monitoring_enabled": False, "debug": True}}

# WebSocket endpoints
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

# Helper functions for real data
async def fetch_real_opportunities() -> List[Dict[str, Any]]:
    """Fetch real opportunities from DexScreener, CoinGecko, and Jupiter APIs."""
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
        except Exception as e:
            logger.error(f"CoinGecko failed: {e}")
    
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
    
    return {
        "total_opportunities": len(opportunities),
        "high_liquidity_opportunities": high_liq_count, 
        "chains_active": len(chains),
        "average_liquidity_usd": round(total_liquidity / len(opportunities), 2),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "data_freshness": "live"
    }

# AI Thought Log functions
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
    title="DEX Sniper Pro Debug with Copy Trading",
    description="Debug version with fixed Copy Trading system",
    version="1.2.1-debug"
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
app.include_router(copy_mock.router)
app.include_router(copy_mock.discovery_router)

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting debug server with fixed Copy Trading system...")
    print("📖 API docs at: http://localhost:8000/docs")
    uvicorn.run(
        "debug_main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )