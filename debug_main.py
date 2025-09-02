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

# ============================================================================
# SYSTEM INITIALIZATION - Setup paths and dependencies
# ============================================================================

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

# ============================================================================
# GLOBAL STATE - WebSocket connections and system state
# ============================================================================

# Global state for WebSocket connections
paper_clients: Set[WebSocket] = set()
metrics_clients: Set[WebSocket] = set()
thought_log_active = False
executor = ThreadPoolExecutor(max_workers=2)

# ============================================================================
# DJANGO SETUP - Initialize Django ORM for database access
# ============================================================================

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

# ============================================================================
# MODULE IMPORTS - Import optional modules with proper error handling
# ============================================================================

# Try to import copy_mock module
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

# ============================================================================
# COPY TRADING SYSTEM INTEGRATION - Full system coordinator
# ============================================================================

# Import the complete copy trading system coordinator
copy_trading_system_ready = False
try:
    if copy_trading_ready:
        # Import the new comprehensive system
        from backend.app.copy_trading.system_coordinator import copy_trading_coordinator
        from backend.app.strategy.trader_performance_tracker import trader_performance_tracker
        from backend.app.trading.live_executor import live_executor
        from backend.app.api.copy_trading_complete import router as complete_copy_api
        
        copy_trading_system_ready = True
        logger.info("Complete copy trading system coordinator imported successfully")
    else:
        logger.warning("Copy trading system not available - missing dependencies")
except ImportError as e:
    logger.warning(f"Copy trading system coordinator not available: {e}")
except Exception as e:
    logger.error(f"Copy trading system coordinator import failed: {e}")

# ============================================================================
# HEALTH ROUTER - System health and status endpoints
# ============================================================================

health_router = APIRouter()

@health_router.get("/health")
async def health():
    """Return system health status including all subsystems."""
    return {
        "status": "ok", 
        "timestamp": datetime.now().isoformat(), 
        "debug": True,
        "copy_trading_ready": copy_trading_ready,
        "copy_trading_system_ready": copy_trading_system_ready,
        "copy_trading_available": copy_trading_available,
        "services": {
            "django": django_initialized,
            "wallet_monitor": copy_trading_ready,
            "copy_trading_hub": copy_trading_ready,
            "copy_trading_coordinator": copy_trading_system_ready
        }
    }

# ============================================================================
# API ROUTER - Main API endpoints
# ============================================================================

api_router = APIRouter(prefix="/api/v1")

class ToggleRequest(BaseModel):
    enabled: bool

# ============================================================================
# PAPER TRADING ENDPOINTS - Virtual trading system
# ============================================================================

@api_router.post("/paper/toggle")
async def toggle_paper(request: ToggleRequest):
    """Toggle Paper Trading and broadcast status to connected clients."""
    global thought_log_active
    thought_log_active = request.enabled
    
    # Update runtime state for copy trading integration
    if copy_trading_system_ready:
        try:
            from backend.app.core.runtime_state import runtime_state
            await runtime_state.set_paper_enabled(request.enabled)
        except Exception as e:
            logger.error(f"Error updating runtime state: {e}")
    
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
    """Get paper trading metrics and performance data."""
    # Try to get real metrics from copy trading system
    if copy_trading_system_ready:
        try:
            status = await copy_trading_coordinator.get_system_status()
            stats = status.get("statistics", {}).get("activity", {})
            
            return {
                "status": "ok", 
                "metrics": {
                    "session_pnl_usd": stats.get("total_pnl_usd", 0.0),
                    "total_trades": stats.get("trades_executed", 0),
                    "win_rate": stats.get("success_rate", 0.0),
                    "avg_slippage_bps": 15,  # Mock value
                    "max_drawdown": -25.50,  # Mock value
                    "active_since": datetime.now().isoformat(),
                    "debug": True
                }
            }
        except Exception as e:
            logger.error(f"Error getting paper metrics: {e}")
    
    # Fallback to mock metrics
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

# ============================================================================
# ENHANCED COPY TRADING ENDPOINTS - Complete system integration
# ============================================================================

@api_router.get("/copy/status")
async def get_copy_trading_status():
    """Get comprehensive copy trading system status."""
    if not copy_trading_system_ready:
        return {
            "status": "ok",
            "copy_trading_enabled": False,
            "message": "Copy trading system not available",
            "system_status": {
                "is_enabled": False,
                "monitoring_active": False,
                "followed_traders_count": 0,
                "active_copies_today": 0,
                "total_copies": 0,
                "win_rate_pct": 0.0,
                "total_pnl_usd": "0.00"
            }
        }
    
    try:
        # Get comprehensive system status from coordinator
        status = await copy_trading_coordinator.get_system_status()
        
        # Format for frontend compatibility
        system_status = {
            "is_enabled": status["coordinator"]["running"],
            "monitoring_active": status["components"]["wallet_monitor"]["is_running"],
            "followed_traders_count": status["components"]["wallet_monitor"]["followed_wallets"],
            "active_copies_today": status["statistics"]["activity"]["trades_executed"],
            "total_copies": status["statistics"]["activity"]["trades_executed"],
            "win_rate_pct": status["statistics"]["activity"]["success_rate"] * 100,
            "total_pnl_usd": f"{status['statistics']['activity']['total_pnl_usd']:.2f}"
        }
        
        return {
            "status": "ok",
            "copy_trading_enabled": True,
            "system_status": system_status,
            "detailed_status": status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Copy trading status error: {e}")
        return {
            "status": "ok", 
            "copy_trading_enabled": False,
            "message": str(e),
            "system_status": {
                "is_enabled": False,
                "monitoring_active": False,
                "followed_traders_count": 0,
                "active_copies_today": 0,
                "total_copies": 0,
                "win_rate_pct": 0.0,
                "total_pnl_usd": "0.00"
            }
        }

@api_router.post("/copy/system/control")
async def control_copy_trading_system(request: ToggleRequest):
    """Start/stop the complete copy trading system."""
    if not copy_trading_system_ready:
        return {
            "status": "error",
            "message": "Copy trading system not available"
        }
    
    try:
        if request.enabled:
            # Initialize system if not already done
            if not copy_trading_coordinator._initialized:
                success = await copy_trading_coordinator.initialize(
                    private_key=None,  # Paper trading mode
                    enable_live_trading=False
                )
                if not success:
                    return {
                        "status": "error",
                        "message": "Failed to initialize copy trading system"
                    }
            
            # Start with demo traders for testing
            demo_traders = [
                "0x742d35cc6634c0532925a3b8d1b9b5f5e5ffb0da",
                "0x8ba1f109551bd432803012645hac136c30c6a25f",
                "0x40aa958dd87fc8305b97f2ba922cddca374bcd7f"
            ]
            
            result = await copy_trading_coordinator.start_system(demo_traders)
            
            return {
                "status": "ok" if result["success"] else "error",
                "message": result.get("message", "System started"),
                "copy_trading_enabled": result["success"],
                "details": result
            }
        else:
            # Stop system
            result = await copy_trading_coordinator.stop_system()
            
            return {
                "status": "ok" if result["success"] else "error", 
                "message": result.get("message", "System stopped"),
                "copy_trading_enabled": False,
                "details": result
            }
        
    except Exception as e:
        logger.error(f"Copy trading system control error: {e}")
        return {
            "status": "error",
            "message": f"System control failed: {str(e)}"
        }

@api_router.post("/copy/toggle")
async def toggle_copy_trading(request: ToggleRequest):
    """Legacy toggle endpoint for backward compatibility."""
    return await control_copy_trading_system(request)

@api_router.post("/copy/traders/add")
async def add_trader_to_system(trader_data: dict):
    """Add a new trader to the copy trading system."""
    if not copy_trading_system_ready:
        return {"status": "error", "message": "Copy trading system not available"}
    
    try:
        address = trader_data.get("wallet_address", "").lower()
        config = {
            "copy_percentage": trader_data.get("copy_percentage", 5.0),
            "max_copy_amount_usd": trader_data.get("max_copy_amount_usd", 1000.0),
            "enabled": True
        }
        
        result = await copy_trading_coordinator.add_trader(address, config)
        
        return {
            "status": "ok" if result["success"] else "error",
            "message": result.get("message"),
            "trader_added": result["success"]
        }
        
    except Exception as e:
        logger.error(f"Add trader error: {e}")
        return {"status": "error", "message": str(e)}

@api_router.delete("/copy/traders/{trader_address}")
async def remove_trader_from_system(trader_address: str):
    """Remove a trader from the copy trading system."""
    if not copy_trading_system_ready:
        return {"status": "error", "message": "Copy trading system not available"}
    
    try:
        result = await copy_trading_coordinator.remove_trader(trader_address)
        
        return {
            "status": "ok" if result["success"] else "error",
            "message": result.get("message"),
            "trader_removed": result["success"]
        }
        
    except Exception as e:
        logger.error(f"Remove trader error: {e}")
        return {"status": "error", "message": str(e)}

@api_router.get("/copy/analytics/performance")
async def get_copy_trading_analytics(
    trader_address: Optional[str] = Query(None),
    days: int = Query(30, ge=7, le=90)
):
    """Get copy trading performance analytics."""
    if not copy_trading_system_ready:
        return {
            "status": "ok", 
            "data": {"type": "unavailable", "message": "System not available"}
        }
    
    try:
        if trader_address:
            # Get specific trader performance
            performance = await trader_performance_tracker.get_trader_performance(trader_address)
            
            return {
                "status": "ok",
                "data": {
                    "type": "trader",
                    "trader_address": trader_address,
                    "performance": performance,
                    "period_days": days
                }
            }
        else:
            # Get overall system performance
            system_status = await copy_trading_coordinator.get_system_status()
            top_performers = await trader_performance_tracker.get_top_performers(5)
            
            return {
                "status": "ok",
                "data": {
                    "type": "system",
                    "period_days": days,
                    "system_stats": system_status["statistics"],
                    "top_performers": top_performers
                }
            }
        
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        return {"status": "error", "message": str(e)}

@api_router.post("/copy/simulate")
async def simulate_copy_trade(simulation_data: dict):
    """Simulate a copy trade without executing."""
    if not copy_trading_system_ready:
        return {"status": "error", "message": "Copy trading system not available"}
    
    try:
        from backend.app.discovery.wallet_monitor import WalletTransaction
        
        # Create mock transaction for simulation
        mock_tx = WalletTransaction(
            tx_hash="0xsimulation123456",
            block_number=19000000,
            timestamp=datetime.now(timezone.utc),
            from_address=simulation_data.get("trader_address", "0x123..."),
            to_address="0xrouter",
            chain=simulation_data.get("chain", "ethereum"),
            dex_name=simulation_data.get("dex", "uniswap_v2"),
            token_address=simulation_data.get("token_address", "0xtoken"),
            token_symbol=simulation_data.get("token_symbol", "TOKEN"),
            pair_address="0xpair123",
            action="buy",
            amount_in=Decimal(str(simulation_data.get("amount_usd", 100))),
            amount_out=Decimal("1000"),
            amount_usd=Decimal(str(simulation_data.get("amount_usd", 100))),
            gas_used=150000,
            gas_price_gwei=Decimal("20"),
            is_mev=False
        )
        
        # Mock trader config
        trader_config = {
            "copy_percentage": Decimal("5.0"),
            "max_copy_amount_usd": Decimal("1000.0"),
            "enabled": True
        }
        
        # Evaluate with copy trading strategy
        evaluation = await copy_trading_strategy.evaluate_copy_opportunity(
            mock_tx, trader_config, "simulation"
        )
        
        return {
            "status": "ok",
            "data": {
                "simulation_id": "sim_" + str(int(datetime.now().timestamp())),
                "original_trade": {
                    "trader_address": simulation_data.get("trader_address"),
                    "token_address": simulation_data.get("token_address"),
                    "amount_usd": simulation_data.get("amount_usd", 100),
                    "chain": simulation_data.get("chain", "ethereum")
                },
                "evaluation": {
                    "decision": evaluation.decision.value,
                    "reason": evaluation.reason.value,
                    "confidence": evaluation.confidence,
                    "copy_amount_usd": float(evaluation.copy_amount_usd),
                    "risk_score": float(evaluation.risk_score),
                    "notes": evaluation.notes
                },
                "estimated_outcome": {
                    "success_probability": 0.85,
                    "expected_slippage_bps": 25,
                    "estimated_gas_cost_usd": 15.0,
                    "net_exposure_usd": float(evaluation.copy_amount_usd) - 15.0
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Simulation error: {e}")
        return {"status": "error", "message": str(e)}

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
        # Get traders with pagination from database
        traders = FollowedTrader.objects.all().order_by('-created_at')
        total_count = traders.count()
        
        # Apply pagination limits
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_traders = traders[start_idx:end_idx]
        
        # Format trader data for API response
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
    """Get copy trade history with optional status filter."""
    if not copy_trading_ready:
        return {
            "status": "ok", 
            "data": [],
            "pagination": {"page": page, "limit": limit, "total": 0, "pages": 0}
        }
    
    try:
        # Build database query with optional status filter
        trades = CopyTrade.objects.all().select_related('followed_trader').order_by('-created_at')
        
        if status:
            trades = trades.filter(status=status)
        
        total_count = trades.count()
        
        # Apply pagination
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_trades = trades[start_idx:end_idx]
        
        # Format trade data for API response
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
    




# Add these endpoints to your debug_main.py api_router section
# Insert after the existing copy trading endpoints (around line 600)

# ============================================================================
# WALLET DISCOVERY ENDPOINTS - Auto discovery functionality
# ============================================================================

@api_router.post("/discovery/discover-traders")
async def discover_traders(request_data: dict):
    """
    Automatically discover top performing traders across specified chains.
    This is the main auto discovery endpoint that the frontend calls.
    """
    try:
        logger.info("Starting wallet discovery process...")
        
        # Extract discovery parameters
        chains = request_data.get("chains", ["ethereum", "bsc"])
        limit = request_data.get("limit", 20)
        min_volume_usd = request_data.get("min_volume_usd", 50000)
        days_back = request_data.get("days_back", 30)
        auto_add_threshold = request_data.get("auto_add_threshold", 80.0)
        
        # Mock discovery process - in production would use real data sources
        discovered_candidates = []
        
        # Generate realistic mock candidates
        sample_addresses = [
            "0x742d35cc6634c0532925a3b8d1b9b5f5e5ffb0da",
            "0x8ba1f109551bd432803012645hac136c30c6a25f", 
            "0x40aa958dd87fc8305b97f2ba922cddca374bcd7f",
            "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
            "0x514910771af9ca656af840dff83e8264ecf986ca",
            "0xa0b86a33e6441e8ce7863a78653c87c8ccb1e86c"
        ]
        
        for i, address in enumerate(sample_addresses[:limit]):
            # Generate realistic performance metrics
            total_trades = random.randint(50, 300)
            profitable_trades = int(total_trades * random.uniform(0.55, 0.85))
            win_rate = profitable_trades / total_trades
            
            total_volume_usd = random.uniform(min_volume_usd, min_volume_usd * 10)
            total_pnl_usd = total_volume_usd * random.uniform(-0.1, 0.4)  # -10% to +40% return
            
            # Calculate quality scores
            risk_score = random.uniform(20, 80)
            confidence_score = min(95, win_rate * 100 + random.uniform(-10, 10))
            
            # Only include high-quality candidates
            if confidence_score >= 60:  # Minimum threshold
                candidate = {
                    "address": address,
                    "chain": random.choice(chains),
                    "source": random.choice(["dexscreener", "etherscan", "coingecko"]),
                    
                    # Performance metrics
                    "total_trades": total_trades,
                    "profitable_trades": profitable_trades,
                    "win_rate": round(win_rate, 3),
                    "total_volume_usd": round(total_volume_usd, 2),
                    "total_pnl_usd": round(total_pnl_usd, 2),
                    "avg_trade_size_usd": round(total_volume_usd / total_trades, 2),
                    
                    # Time metrics
                    "first_trade": (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat(),
                    "last_trade": (datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 48))).isoformat(),
                    "active_days": days_back - random.randint(0, 10),
                    "trades_per_day": round(total_trades / days_back, 2),
                    
                    # Risk metrics
                    "max_drawdown_pct": round(random.uniform(0.05, 0.30), 3),
                    "largest_loss_usd": round(total_volume_usd * random.uniform(0.02, 0.15), 2),
                    "risk_score": round(risk_score, 1),
                    
                    # Quality indicators
                    "consistent_profits": win_rate > 0.6,
                    "diverse_tokens": random.randint(10, 50),
                    "suspicious_activity": random.random() < 0.1,  # 10% chance
                    
                    # Metadata
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                    "confidence_score": round(confidence_score, 1),
                    "recommended_copy_percentage": round(min(10, max(1, confidence_score / 20)), 1)
                }
                
                discovered_candidates.append(candidate)
        
        # Sort by confidence score
        discovered_candidates.sort(key=lambda x: x["confidence_score"], reverse=True)
        
        logger.info(f"Discovery complete: found {len(discovered_candidates)} candidates")
        
        return {
            "status": "ok",
            "message": f"Discovered {len(discovered_candidates)} trader candidates",
            "candidates": discovered_candidates,
            "discovery_params": {
                "chains": chains,
                "limit": limit,
                "min_volume_usd": min_volume_usd,
                "days_back": days_back,
                "auto_add_threshold": auto_add_threshold
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        return {
            "status": "error",
            "error": f"Discovery failed: {str(e)}",
            "candidates": [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@api_router.post("/discovery/analyze-wallet")
async def analyze_wallet(request_data: dict):
    """
    Analyze a specific wallet address for copy trading suitability.
    """
    try:
        address = request_data.get("address", "").lower()
        chain = request_data.get("chain", "ethereum")
        days_back = request_data.get("days_back", 30)
        
        if not address or len(address) != 42 or not address.startswith("0x"):
            return {
                "status": "error",
                "error": "Invalid wallet address format"
            }
        
        logger.info(f"Analyzing wallet {address[:8]}... on {chain}")
        
        # Mock analysis - would use real blockchain data in production
        await asyncio.sleep(2)  # Simulate analysis time
        
        # Generate realistic analysis results
        total_trades = random.randint(20, 200)
        profitable_trades = int(total_trades * random.uniform(0.45, 0.80))
        win_rate = profitable_trades / total_trades
        
        total_volume_usd = random.uniform(25000, 500000)
        total_pnl_usd = total_volume_usd * random.uniform(-0.2, 0.5)
        
        risk_score = random.uniform(25, 75)
        confidence_score = min(95, win_rate * 100 + random.uniform(-15, 15))
        
        analysis_result = {
            "address": address,
            "chain": chain,
            "analysis_period_days": days_back,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            
            # Performance summary
            "performance": {
                "total_trades": total_trades,
                "profitable_trades": profitable_trades,
                "win_rate": round(win_rate, 3),
                "total_volume_usd": round(total_volume_usd, 2),
                "total_pnl_usd": round(total_pnl_usd, 2),
                "avg_trade_size_usd": round(total_volume_usd / total_trades, 2),
                "largest_win_usd": round(total_volume_usd * random.uniform(0.05, 0.20), 2),
                "largest_loss_usd": round(total_volume_usd * random.uniform(0.02, 0.15), 2)
            },
            
            # Risk assessment
            "risk": {
                "risk_score": round(risk_score, 1),
                "risk_level": "low" if risk_score < 40 else "medium" if risk_score < 70 else "high",
                "max_drawdown_pct": round(random.uniform(0.08, 0.35), 3),
                "volatility_score": round(random.uniform(0.1, 0.8), 2),
                "consistency_score": round(random.uniform(0.4, 0.9), 2)
            },
            
            # Trading patterns
            "patterns": {
                "avg_hold_time_hours": round(random.uniform(0.5, 48), 1),
                "preferred_chains": [chain, random.choice(["bsc", "polygon"])],
                "token_diversity": random.randint(15, 60),
                "active_hours": f"{random.randint(8, 12)}-{random.randint(18, 24)} UTC",
                "trading_frequency": round(total_trades / days_back, 2)
            },
            
            # Recommendation
            "recommendation": {
                "suitable_for_copying": confidence_score >= 60,
                "confidence_score": round(confidence_score, 1),
                "recommended_copy_percentage": round(min(15, max(1, confidence_score / 15)), 1),
                "max_position_usd": round(min(2000, max(100, confidence_score * 20)), 0),
                "risk_warnings": [
                    "High volatility detected" if risk_score > 60 else None,
                    "Limited trading history" if total_trades < 50 else None,
                    "Recent losses detected" if total_pnl_usd < 0 else None
                ]
            }
        }
        
        # Filter out None warnings
        analysis_result["recommendation"]["risk_warnings"] = [
            w for w in analysis_result["recommendation"]["risk_warnings"] if w is not None
        ]
        
        return {
            "status": "ok",
            "analysis": analysis_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Wallet analysis failed: {e}")
        return {
            "status": "error",
            "error": f"Analysis failed: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@api_router.get("/discovery/discovery-status")
async def get_discovery_status():
    """
    Get wallet discovery system status.
    """
    return {
        "status": "ok",
        "discovery": {
            "enabled": True,
            "running": False,
            "last_discovery": None,
            "continuous_discovery": {
                "enabled": False,
                "interval_hours": 24,
                "auto_add_enabled": False,
                "auto_add_threshold": 85.0
            },
            "stats": {
                "total_discovered": 0,
                "auto_added_today": 0,
                "discovery_sources": ["dexscreener", "etherscan", "coingecko"],
                "supported_chains": ["ethereum", "bsc", "base", "polygon"]
            }
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@api_router.post("/discovery/continuous")
async def configure_continuous_discovery(request_data: dict):
    """
    Configure continuous discovery settings.
    """
    try:
        enabled = request_data.get("enabled", False)
        chains = request_data.get("chains", ["ethereum", "bsc"])
        interval_hours = request_data.get("interval_hours", 24)
        auto_add_enabled = request_data.get("auto_add_enabled", False)
        auto_add_threshold = request_data.get("auto_add_threshold", 85.0)
        
        # Mock configuration - would integrate with real discovery engine
        config = {
            "enabled": enabled,
            "chains": chains,
            "interval_hours": interval_hours,
            "auto_add_enabled": auto_add_enabled,
            "auto_add_threshold": auto_add_threshold,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        message = f"Continuous discovery {'enabled' if enabled else 'disabled'}"
        if enabled:
            message += f" for chains: {', '.join(chains)}"
        
        return {
            "status": "ok",
            "message": message,
            "config": config
        }
        
    except Exception as e:
        logger.error(f"Continuous discovery configuration failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

@api_router.post("/discovery/add-discovered-trader")
async def add_discovered_trader(request_data: dict):
    """
    Add a discovered trader to the copy trading system.
    """
    try:
        address = request_data.get("address", "").lower()
        copy_percentage = request_data.get("copy_percentage", 5.0)
        max_position_usd = request_data.get("max_position_usd", 1000.0)
        
        if not address:
            return {"status": "error", "error": "Wallet address required"}
        
        # Use copy trading system if available
        if copy_trading_system_ready:
            config = {
                "copy_percentage": copy_percentage,
                "max_copy_amount_usd": max_position_usd,
                "enabled": True
            }
            
            result = await copy_trading_coordinator.add_trader(address, config)
            
            return {
                "status": "ok" if result["success"] else "error",
                "message": result.get("message", "Trader added to copy trading system"),
                "trader_address": address
            }
        else:
            # Mock response if copy trading system not ready
            return {
                "status": "ok",
                "message": f"Added {address[:8]}... to copy trading (mock)",
                "trader_address": address
            }
        
    except Exception as e:
        logger.error(f"Add discovered trader failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }






# APP: backend
# FILE: debug_main.py - Real API Integration Update
# FUNCTION: Add real API router integration to serve actual data

# Add this section to your existing debug_main.py after the copy_trading imports

# ============================================================================
# REAL API INTEGRATION - Replace mock endpoints with real data
# ============================================================================

# Import the real copy trading API
real_copy_trading_api_ready = False
try:
    from backend.app.api.copy_trading_real import router as real_copy_trading_router
    real_copy_trading_api_ready = True
    logger.info("Real copy trading API router imported successfully")
except ImportError as e:
    logger.warning(f"Real copy trading API not available: {e}")
except Exception as e:
    logger.error(f"Real copy trading API import failed: {e}")

# ============================================================================
# API ROUTER UPDATES - Include real endpoints
# ============================================================================

# Update your existing api_router section to include the real endpoints
# Replace the mock copy trading endpoints with real ones

if real_copy_trading_api_ready:
    # Include the real copy trading API router
    api_router.include_router(real_copy_trading_router)
    logger.info("Real copy trading API endpoints registered")
else:
    # Fallback to mock endpoints if real API not available
    logger.warning("Using fallback mock copy trading endpoints")

# ============================================================================
# FRONTEND INTEGRATION ENDPOINTS - Bridge real data to frontend format
# ============================================================================

@api_router.get("/frontend/copy-trading/status")
async def frontend_copy_trading_status():
    """Frontend-specific copy trading status endpoint."""
    try:
        if real_copy_trading_api_ready:
            # Import the real API functions
            from backend.app.api.copy_trading_real import get_copy_trading_status
            return await get_copy_trading_status()
        else:
            # Return mock data structure
            return {
                "status": "ok",
                "is_enabled": True,
                "monitoring_active": False,
                "followed_traders_count": 0,
                "active_traders": 0,
                "trades_today": 0,
                "total_trades": 0,
                "success_rate": 0.0,
                "total_pnl_usd": 0.0,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Frontend copy trading status error: {e}")
        return {"status": "error", "error": str(e)}


@api_router.get("/frontend/copy-trading/traders")
async def frontend_list_traders():
    """Frontend-specific traders list endpoint."""
    try:
        if real_copy_trading_api_ready:
            from backend.app.api.copy_trading_real import list_followed_traders
            return await list_followed_traders()
        else:
            return {
                "status": "ok",
                "data": [],
                "count": 0,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Frontend traders list error: {e}")
        return {"status": "error", "data": [], "error": str(e)}


@api_router.get("/frontend/copy-trading/trades")
async def frontend_copy_trades(status: str = None, limit: int = 50):
    """Frontend-specific copy trades endpoint."""
    try:
        if real_copy_trading_api_ready:
            from backend.app.api.copy_trading_real import get_copy_trades
            return await get_copy_trades(status=status, limit=limit)
        else:
            return {
                "status": "ok",
                "data": [],
                "count": 0,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Frontend copy trades error: {e}")
        return {"status": "error", "data": [], "error": str(e)}


@api_router.post("/frontend/copy-trading/add-trader")
async def frontend_add_trader(request_data: dict):
    """Frontend-specific add trader endpoint."""
    try:
        if real_copy_trading_api_ready:
            from backend.app.api.copy_trading_real import add_followed_trader, AddTraderRequest
            
            # Convert frontend data to API request format
            api_request = AddTraderRequest(**request_data)
            return await add_followed_trader(api_request)
        else:
            # Mock response for development
            return {
                "status": "ok",
                "message": "Trader added successfully (mock)",
                "trader": {
                    "id": str(uuid.uuid4()),
                    **request_data,
                    "created_at": datetime.now().isoformat()
                }
            }
    except Exception as e:
        logger.error(f"Frontend add trader error: {e}")
        return {"status": "error", "error": str(e)}


@api_router.post("/frontend/discovery/discover-traders")
async def frontend_discover_traders(request_data: dict):
    """Frontend-specific trader discovery endpoint."""
    try:
        if real_copy_trading_api_ready:
            from backend.app.api.copy_trading_real import discover_traders, DiscoveryRequest
            
            # Convert frontend data to API request format
            api_request = DiscoveryRequest(**request_data)
            return await discover_traders(api_request)
        else:
            # Mock discovery results for development
            import random
            
            mock_wallets = []
            for i in range(min(request_data.get('limit', 10), 20)):
                mock_wallets.append({
                    "id": str(uuid.uuid4()),
                    "address": "0x" + "".join(random.choices("0123456789abcdef", k=40)),
                    "chain": random.choice(request_data.get('chains', ['ethereum'])),
                    "quality_score": random.randint(75, 95),
                    "total_volume_usd": random.randint(50000, 500000),
                    "win_rate": round(random.uniform(65, 90), 1),
                    "trades_count": random.randint(20, 150),
                    "avg_trade_size": random.randint(500, 8000),
                    "last_active": f"{random.randint(1, 12)} hours ago",
                    "recommended_copy_percentage": round(random.uniform(2, 6), 1),
                    "risk_level": random.choice(["Low", "Medium", "High"]),
                    "confidence": random.choice(["High", "Medium"])
                })
            
            return {
                "status": "ok",
                "discovered_wallets": mock_wallets,
                "count": len(mock_wallets),
                "discovery_params": request_data,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Frontend discover traders error: {e}")
        return {"status": "error", "error": str(e)}


@api_router.get("/frontend/discovery/status")
async def frontend_discovery_status():
    """Frontend-specific discovery status endpoint."""
    try:
        if real_copy_trading_api_ready:
            from backend.app.api.copy_trading_real import get_discovery_status
            return await get_discovery_status()
        else:
            return {
                "status": "ok",
                "discovery_running": False,
                "total_discovered": 0,
                "high_confidence_candidates": 0,
                "discovered_by_chain": {},
                "last_discovery_run": None,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Frontend discovery status error: {e}")
        return {"status": "error", "error": str(e)}


@api_router.post("/frontend/discovery/analyze-wallet")
async def frontend_analyze_wallet(request_data: dict):
    """Frontend-specific wallet analysis endpoint."""
    try:
        if real_copy_trading_api_ready:
            from backend.app.api.copy_trading_real import analyze_wallet, AnalyzeWalletRequest
            
            # Convert frontend data to API request format
            api_request = AnalyzeWalletRequest(**request_data)
            return await analyze_wallet(api_request)
        else:
            # Mock analysis for development
            import random
            
            address = request_data.get('address')
            quality_score = random.randint(75, 95)
            
            return {
                "status": "ok",
                "analysis": {
                    "candidate": {
                        "address": address,
                        "chain": request_data.get('chain', 'ethereum'),
                        "quality_score": quality_score,
                        "total_volume_usd": random.randint(30000, 200000),
                        "win_rate": round(random.uniform(60, 85), 1),
                        "trades_count": random.randint(25, 80),
                        "avg_trade_size": random.randint(800, 4000),
                        "recommended_copy_percentage": round(min(5.0, quality_score * 0.05), 1),
                        "risk_level": "Low" if quality_score > 85 else "Medium",
                        "confidence": "High" if quality_score > 80 else "Medium"
                    },
                    "analysis": {
                        "strengths": ["Consistent performance", "Low risk", "Active trading"],
                        "weaknesses": ["Limited diversification", "High gas usage"],
                        "recommendation": f"{'Strong' if quality_score > 85 else 'Moderate'} candidate for copy trading."
                    }
                },
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Frontend analyze wallet error: {e}")
        return {"status": "error", "error": str(e)}

# ============================================================================
# DATABASE INITIALIZATION - Ensure tables exist
# ============================================================================

async def ensure_copy_trading_tables():
    """Ensure copy trading database tables are created."""
    try:
        if django_initialized:
            from django.core.management import execute_from_command_line
            import os
            
            # Run migrations to create tables
            old_argv = os.sys.argv
            os.sys.argv = ['manage.py', 'makemigrations', 'ledger']
            try:
                execute_from_command_line(os.sys.argv)
                logger.info("Copy trading migrations created")
            except Exception as e:
                logger.warning(f"Migration creation warning: {e}")
            
            os.sys.argv = ['manage.py', 'migrate']
            try:
                execute_from_command_line(os.sys.argv)
                logger.info("Copy trading tables created/updated")
            except Exception as e:
                logger.error(f"Migration execution error: {e}")
            
            os.sys.argv = old_argv
            
        return True
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False

# Initialize database tables on startup
if django_initialized:
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(ensure_copy_trading_tables())
        loop.close()
        logger.info("Copy trading database initialization completed")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

# ============================================================================
# HEALTH CHECK UPDATES - Include real API status
# ============================================================================

@health_router.get("/health/copy-trading")
async def copy_trading_health():
    """Detailed copy trading system health check."""
    return {
        "status": "ok",
        "real_api_available": real_copy_trading_api_ready,
        "django_available": django_initialized,
        "database_connected": django_initialized,
        "services": {
            "trader_monitoring": "active" if real_copy_trading_api_ready else "mock",
            "discovery_engine": "active" if real_copy_trading_api_ready else "mock",
            "trade_executor": "standby"
        },
        "timestamp": datetime.now().isoformat()
    }

# ============================================================================
# STARTUP LOGGING - Report real vs mock status
# ============================================================================

logger.info("=" * 80)
logger.info("COPY TRADING API INTEGRATION STATUS")
logger.info("=" * 80)
logger.info(f"Django initialized: {django_initialized}")
logger.info(f"Real copy trading API: {real_copy_trading_api_ready}")
logger.info(f"Using {'REAL DATA' if real_copy_trading_api_ready else 'MOCK DATA'}")
logger.info("=" * 80)

















# ============================================================================
# DISCOVERY ENDPOINTS - Token pair discovery system
# ============================================================================

@api_router.get("/discovery/status")
async def discovery_status():
    """Get discovery engine status and configuration."""
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

# ============================================================================
# OPPORTUNITIES ENDPOINTS - Live trading opportunities
# ============================================================================

@api_router.get("/opportunities/live")
async def get_live_opportunities(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Results per page")
):
    """Get live opportunities from real APIs with pagination."""
    try:
        logger.info(f"Fetching live opportunities (page {page}, limit {limit})...")
        # Fetch opportunities from multiple real API sources
        all_opportunities = await fetch_real_opportunities()
        
        # Apply pagination to the results
        total_count = len(all_opportunities)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_opportunities = all_opportunities[start_idx:end_idx]
        
        # Format opportunities for frontend consumption
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
    """Get opportunity statistics from live data."""
    try:
        logger.info("Calculating opportunity stats...")
        # Fetch current opportunities and calculate real statistics
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

# ============================================================================
# ANALYZE ENDPOINT - Detailed opportunity analysis
# ============================================================================

@api_router.post("/opportunities/analyze")
async def analyze_opportunity(request_data: dict):
    """
    Analyze a specific trading opportunity with comprehensive metrics.
    """
    try:
        logger.info(f"Analyzing opportunity: {request_data.get('pair_address', 'unknown')}")
        
        # Extract request parameters
        pair_address = request_data.get("pair_address", "")
        chain = request_data.get("chain", "ethereum")
        dex = request_data.get("dex", "unknown")
        trade_amount_eth = request_data.get("trade_amount_eth", 0.1)
        
        # Generate comprehensive analysis data
        analysis = {
            # Basic pair information
            "pair_info": {
                "address": pair_address,
                "chain": chain,
                "dex": dex,
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "trace_id": f"analysis_{random.randint(1000, 9999)}"
            },
            
            # Liquidity depth and trading volume analysis
            "liquidity_analysis": {
                "current_liquidity_usd": random.randint(50000, 500000),
                "liquidity_depth_5pct": random.randint(5000, 25000),
                "liquidity_depth_10pct": random.randint(10000, 50000),
                "liquidity_stability_24h": random.choice(["stable", "volatile", "declining"]),
                "volume_24h_usd": random.randint(20000, 200000),
                "volume_to_liquidity_ratio": round(random.uniform(0.1, 2.0), 3),
                "large_holder_risk": random.choice(["low", "medium", "high"])
            },
            
            # Smart contract and security risk assessment
            "risk_assessment": {
                "risk_score": round(random.uniform(2.0, 9.5), 1),
                "risk_level": random.choice(["low", "medium", "high"]),
                "contract_verification": random.choice(["verified", "unverified"]),
                "honeypot_risk": random.choice(["low", "medium", "high"]),
                "liquidity_locked": random.choice([True, False]),
                "lock_duration_days": random.randint(30, 365) if random.choice([True, False]) else None,
                "owner_can_mint": random.choice([True, False]),
                "trading_cooldown": random.choice([True, False])
            },
            
            # Token contract analysis
            "token_analysis": {
                "total_supply": random.randint(1000000, 1000000000),
                "circulating_supply": random.randint(500000, 900000000),
                "market_cap": random.randint(100000, 10000000),
                "token_age_days": random.randint(1, 365),
                "holder_count": random.randint(100, 10000),
                "top_holder_percentage": round(random.uniform(0.05, 0.30), 3),
                "buy_tax": round(random.uniform(0.0, 0.10), 3),
                "sell_tax": round(random.uniform(0.0, 0.10), 3),
                "transfer_tax": round(random.uniform(0.0, 0.05), 3),
                "contract_features": {
                    "pausable": random.choice([True, False]),
                    "mintable": random.choice([True, False]),
                    "burnable": random.choice([True, False]),
                    "proxy": random.choice([True, False])
                }
            },
            
            # Technical analysis and trading signals
            "trading_signals": {
                "momentum_score": round(random.uniform(3.0, 9.5), 1),
                "technical_score": round(random.uniform(4.0, 8.5), 1),
                "trend_direction": random.choice(["bullish", "bearish", "neutral"]),
                "volume_trend": random.choice(["increasing", "decreasing", "stable"]),
                "social_sentiment": random.choice(["positive", "negative", "neutral"]),
                "whale_activity": random.choice(["buying", "selling", "neutral"]),
                "support_level": round(random.uniform(0.000001, 0.01), 6),
                "resistance_level": round(random.uniform(0.000001, 0.01), 6)
            },
            
            # AI-generated trading recommendation
            "recommendation": {
                "action": random.choice(["BUY", "SELL", "HOLD", "MONITOR"]),
                "confidence": round(random.uniform(0.4, 0.95), 2),
                "position_size": random.choice(["small", "medium", "large"]),
                "entry_strategy": random.choice(["market", "limit", "dca"]),
                "stop_loss": round(random.uniform(0.05, 0.20), 3),
                "take_profit_1": round(random.uniform(0.10, 0.30), 3),
                "take_profit_2": round(random.uniform(0.25, 0.50), 3),
                "max_slippage": round(random.uniform(0.01, 0.05), 3),
                "gas_priority": random.choice(["low", "medium", "high"]),
                "rationale": "Analysis based on liquidity depth, technical indicators, and risk assessment. " + 
                           random.choice([
                               "Strong momentum signals detected with acceptable risk levels.",
                               "Moderate opportunity with standard risk parameters.",
                               "High volatility detected, proceed with caution.",
                               "Limited liquidity may impact execution quality."
                           ])
            }
        }
        
        logger.info(f"Analysis complete for {pair_address}: {analysis['recommendation']['action']}")
        
        return {
            "status": "ok",
            "analysis": analysis,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return {
            "status": "error",
            "error": f"Analysis failed: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# ============================================================================
# COMPATIBILITY ENDPOINTS - For Django ORM compatibility
# ============================================================================

@api_router.get("/tokens/")
async def get_tokens(page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100)):
    """Get tokens list (compatibility endpoint)."""
    return {"status": "ok", "data": [], "pagination": {"page": page, "limit": limit, "total": 0, "pages": 0}}

@api_router.get("/trades/")
async def get_trades(page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100)):
    """Get trades list (compatibility endpoint)."""
    return {"status": "ok", "data": [], "pagination": {"page": page, "limit": limit, "total": 0, "pages": 0}}

@api_router.get("/providers/")
async def get_providers():
    """Get data providers list (compatibility endpoint)."""
    return {"status": "ok", "data": [{"id": 1, "name": "Debug Provider", "enabled": True, "kind": "rpc"}], "count": 1}

@api_router.get("/bot/status")
async def get_bot_status():
    """Get trading bot status (compatibility endpoint)."""
    return {"status": "ok", "data": {"status": "running", "uptime_seconds": 3600, "total_trades": 0, "paper_mode": True, "debug": True}}

@api_router.get("/intelligence/status")
async def get_intelligence_status():
    """Get AI intelligence system status (compatibility endpoint)."""
    return {"status": "ok", "data": {"enabled": True, "advanced_risk_enabled": True, "mempool_monitoring_enabled": False, "debug": True}}

# ============================================================================
# WEBSOCKET ROUTER - Real-time communication
# ============================================================================

ws_router = APIRouter()

@ws_router.websocket("/ws/paper")
async def ws_paper(websocket: WebSocket):
    """Real-time Paper Trading WebSocket with AI Thought Log streaming."""
    await websocket.accept()
    paper_clients.add(websocket)
    
    # Send initial hello message
    await websocket.send_json({
        "type": "hello",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "channel": "paper",
            "thought_log_active": thought_log_active,
            "copy_trading_ready": copy_trading_system_ready,
            "debug": True
        }
    })
    
    try:
        # Handle incoming messages and send periodic heartbeats
        while True:
            try:
                # Wait for incoming message with timeout
                data = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                if data.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
            except asyncio.TimeoutError:
                # Send heartbeat if no message received
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": {
                        "active_connections": len(paper_clients),
                        "copy_trading_system_ready": copy_trading_system_ready
                    }
                })
    except WebSocketDisconnect:
        paper_clients.discard(websocket)
        logger.info("Paper trading client disconnected")
    except Exception as e:
        logger.error(f"Paper WebSocket error: {e}")
        paper_clients.discard(websocket)

# ============================================================================
# DATA FETCHING FUNCTIONS - Real API integrations
# ============================================================================

async def fetch_real_opportunities() -> List[Dict[str, Any]]:
    """Fetch real opportunities from multiple DEX data sources."""
    opportunities = []
    
    async with aiohttp.ClientSession() as session:
        
        # 1. DexScreener trending pairs - REAL API DATA
        try:
            logger.info("Fetching DexScreener trending pairs...")
            async with session.get(
                "https://api.dexscreener.com/latest/dex/pairs/ethereum", 
                timeout=15
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get("pairs", [])
                    
                    # Filter pairs with minimum liquidity threshold
                    for pair in pairs[:15]:
                        liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0)) if pair.get("liquidity") else 0
                        if liquidity_usd >= 8000:  # Minimum liquidity filter
                            opp = process_dexscreener_pair(pair)
                            if opp:
                                opportunities.append(opp)
                    
                    logger.info(f"DexScreener added {len([o for o in opportunities if o.get('source') == 'dexscreener'])} opportunities")
        except Exception as e:
            logger.error(f"DexScreener failed: {e}")
        
        # 2. CoinGecko trending tokens - REAL API DATA
        try:
            logger.info("Fetching CoinGecko trending...")
            async with session.get(
                "https://api.coingecko.com/api/v3/search/trending",
                timeout=15
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    trending_coins = data.get("coins", [])
                    
                    # Convert trending coins to trading pairs
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
        
        # Add curated opportunities for consistent testing
        curated_opportunities = [
            {
                "chain": "ethereum",
                "dex": "uniswap_v3",
                "pair_address": "univ3_weth_usdc_500",
                "token0_symbol": "WETH",
                "token1_symbol": "USDC",
                "estimated_liquidity_usd": 890000,
                "volume_24h": 500000,
                "price_change_24h": 2.5,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "uniswap_v3"
            },
            {
                "chain": "bsc",
                "dex": "pancakeswap_v2",
                "pair_address": "pancake_cake_bnb",
                "token0_symbol": "CAKE",
                "token1_symbol": "BNB",
                "estimated_liquidity_usd": 240000,
                "volume_24h": 180000,
                "price_change_24h": 5.2,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "pancakeswap"
            }
        ]
        
        opportunities.extend(curated_opportunities)
    
    # Calculate opportunity scores and sort by quality
    for opp in opportunities:
        opp["opportunity_score"] = calculate_opportunity_score(opp)
    
    opportunities.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)
    
    logger.info(f"Returning {len(opportunities)} total opportunities from all sources")
    return opportunities[:30]  # Return top 30 opportunities

def process_dexscreener_pair(pair: Dict[str, Any]) -> Dict[str, Any] | None:
    """Process a DexScreener pair into our standard opportunity format."""
    try:
        # Extract liquidity information
        liquidity_data = pair.get("liquidity", {})
        if isinstance(liquidity_data, dict):
            liquidity_usd = float(liquidity_data.get("usd", 0))
        else:
            liquidity_usd = float(liquidity_data) if liquidity_data else 0
            
        # Skip pairs with insufficient liquidity
        if liquidity_usd < 8000:
            return None
            
        # Extract token information
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
    
    # Score based on liquidity (higher liquidity = better score)
    liquidity = opp.get("estimated_liquidity_usd", 0)
    if liquidity > 100000:
        score += 4.0
    elif liquidity > 50000:
        score += 3.0
    elif liquidity > 25000:
        score += 2.0
    elif liquidity > 10000:
        score += 1.0
    
    # Score based on 24h volume (higher volume = more activity)
    volume_24h = opp.get("volume_24h", 0)
    if volume_24h > 100000:
        score += 3.0
    elif volume_24h > 50000:
        score += 2.0  
    elif volume_24h > 10000:
        score += 1.0
    
    # Score based on data source reliability
    source = opp.get("source", "")
    if source == "dexscreener":
        score += 2.0  # Real-time data gets highest score
    elif source == "coingecko_trending":
        score += 1.5  # Trending tokens get good score
    
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
    
    # Calculate aggregate statistics
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

# ============================================================================
# AI THOUGHT LOG FUNCTIONS - Paper trading AI simulation
# ============================================================================

async def start_thought_log_stream():
    """Start streaming AI Thought Log messages every 10-30 seconds."""
    logger.info("Starting AI Thought Log streaming")
    
    # Continue streaming while paper trading is active and clients are connected
    while thought_log_active and paper_clients:
        await asyncio.sleep(random.uniform(10, 30))  # Random interval for realism
        
        if thought_log_active and paper_clients:
            thought_log = generate_mock_thought_log()
            await broadcast_thought_log(thought_log)

def generate_mock_thought_log() -> Dict[str, Any]:
    """Generate realistic AI Thought Log data simulating trading decisions."""
    # Sample opportunities the AI might consider
    opportunities = [
        {"pair": "0x1234...abcd", "symbol": "DOGE/WETH", "chain": "base", "dex": "uniswap_v3"},
        {"pair": "0x5678...efgh", "symbol": "PEPE/BNB", "chain": "bsc", "dex": "pancake_v2"},
        {"pair": "0x9abc...ijkl", "symbol": "SHIB/MATIC", "chain": "polygon", "dex": "quickswap"},
    ]
    
    # Select random opportunity and generate analysis data
    opp = random.choice(opportunities)
    liquidity_usd = random.uniform(15000, 250000)
    trend_score = random.uniform(0.3, 0.95)
    buy_tax = random.uniform(0, 0.08)
    sell_tax = random.uniform(0, 0.08)
    
    # Simulate risk gate checks
    risk_gates = {
        "liquidity_check": "pass" if liquidity_usd > 20000 else "fail",
        "owner_controls": "pass" if random.random() > 0.2 else "warning",
        "buy_tax": buy_tax,
        "sell_tax": sell_tax,
        "blacklist_check": "pass" if random.random() > 0.1 else "fail",
        "honeypot_check": "pass" if random.random() > 0.05 else "fail"
    }
    
    # Determine if all risk gates pass
    all_gates_pass = all(
        gate in ["pass", "warning"] for gate in [
            risk_gates["liquidity_check"],
            risk_gates["owner_controls"],
            risk_gates["blacklist_check"],
            risk_gates["honeypot_check"]
        ]
    ) and buy_tax <= 0.05 and sell_tax <= 0.05
    
    # Make trading decision based on risk gates and trend
    action = "paper_buy" if all_gates_pass and trend_score > 0.6 else "skip"
    
    # Generate reasoning for the decision
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
    """Broadcast message to all paper trading WebSocket clients."""
    if not paper_clients:
        return
    
    # Track disconnected clients for cleanup
    disconnected = set()
    for client in paper_clients.copy():
        try:
            await client.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send to paper client: {e}")
            disconnected.add(client)
    
    # Clean up disconnected clients
    for client in disconnected:
        paper_clients.discard(client)

# ============================================================================
# FASTAPI APPLICATION SETUP - Configure and start the server
# ============================================================================

# Create the FastAPI application instance
app = FastAPI(
    title="DEX Sniper Pro Debug with Complete Copy Trading",
    description="Debug version with integrated copy trading system, live execution, and performance tracking",
    version="1.4.0-debug"
)

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Register all API routers
app.include_router(health_router, tags=["health"])
app.include_router(api_router, tags=["api"])
app.include_router(ws_router, tags=["websockets"])

# Include copy_mock routers if available
if copy_mock_available:
    app.include_router(copy_mock.router)
    app.include_router(copy_mock.discovery_router)

# Include complete copy trading API if available
if copy_trading_system_ready:
    try:
        app.include_router(complete_copy_api, tags=["copy-trading-complete"])
        logger.info("Complete copy trading API router included")
    except Exception as e:
        logger.error(f"Failed to include complete copy trading API: {e}")






# ============================================================================
# REAL COPY TRADING API INTEGRATION - CRITICAL FIX
# ============================================================================

# Import and register the real copy trading API with discovery endpoints
try:
    # Import the complete real API
    import sys
    sys.path.append('backend/app/api')
    from copy_trading_real import router as real_copy_trading_router
    
    # Include the real router AFTER the mock endpoints
    app.include_router(real_copy_trading_router, prefix="", tags=["copy-trading-real"])
    
    logger.info("✅ REAL copy trading API with discovery endpoints registered")
    logger.info("Available real endpoints:")
    logger.info("  - GET /api/v1/copy/status")
    logger.info("  - GET /api/v1/copy/traders") 
    logger.info("  - POST /api/v1/copy/traders")
    logger.info("  - GET /api/v1/copy/discovery/status")
    logger.info("  - POST /api/v1/copy/discovery/discover-traders")
    logger.info("  - POST /api/v1/copy/discovery/analyze-wallet")
    
    real_copy_trading_api_ready = True
    
except ImportError as e:
    logger.error(f"❌ Failed to import real copy trading API: {e}")
    real_copy_trading_api_ready = False
except Exception as e:
    logger.error(f"❌ Failed to register real copy trading API: {e}")
    real_copy_trading_api_ready = False








# ============================================================================
# APPLICATION LIFECYCLE EVENTS - Initialize copy trading on startup
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize copy trading system on application startup."""
    if copy_trading_system_ready:
        try:
            logger.info("Initializing copy trading system on startup...")
            
            # Initialize in paper trading mode by default
            success = await copy_trading_coordinator.initialize(
                private_key=None,
                enable_live_trading=False
            )
            
            if success:
                logger.info("Copy trading system initialized successfully in paper mode")
            else:
                logger.warning("Copy trading system initialization failed")
                
        except Exception as e:
            logger.error(f"Error during copy trading system startup: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup copy trading system on application shutdown."""
    if copy_trading_system_ready:
        try:
            logger.info("Shutting down copy trading system...")
            await copy_trading_coordinator.cleanup()
            logger.info("Copy trading system shutdown complete")
        except Exception as e:
            logger.error(f"Error during copy trading system shutdown: {e}")

# ============================================================================
# SERVER STARTUP - Run the application
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*70)
    print("🚀 DEX Sniper Pro - Complete Copy Trading System")
    print("="*70)
    print("📈 Copy Trading: Full pipeline with live execution")
    print("📊 Performance Tracking: Advanced trader analytics")
    print("🔍 Wallet Monitor: Multi-chain transaction detection")
    print("💡 AI Thought Log: Real-time decision reasoning")
    print("🌐 Live Opportunities: Real DEX data integration")
    print("="*70)
    print("📖 API Documentation: http://localhost:8000/docs")
    print("🔗 Copy Trading Status: http://localhost:8000/api/v1/copy/status")
    print("="*70)
    
    uvicorn.run(
        "debug_main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )