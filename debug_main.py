# APP: backend
# FILE: debug_main.py
"""
DEX Sniper Pro Unified Server - FastAPI + Django Channels Integration

High-performance unified server combining FastAPI REST APIs with Django Channels
WebSocket handling for optimal trading speed and minimal latency.

This is optimized for profit generation through:
- Single-process memory sharing for market data
- Zero inter-service communication delays  
- Unified state management across HTTP and WebSocket
- Maximum speed for AI Thought Log streaming
"""

from __future__ import annotations

import aiohttp 
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import traceback
import uvicorn
import uuid
from fastapi import APIRouter

# System path setup
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging for performance
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("debug_main")

# ============================================================================
# UNIFIED ASGI APPLICATION - FastAPI + Django Channels
# ============================================================================

def create_unified_asgi_app():
    """
    Create unified ASGI application with FastAPI + Django Channels.
    
    This architecture provides:
    - FastAPI for REST endpoints (speed optimized)
    - Django Channels for WebSocket (real-time AI streaming)
    - Single process for minimal latency
    - Shared state for maximum performance
    """
    
    # 1. Setup Django first for ORM access
    setup_django_for_channels()
    
    # 2. Create FastAPI app with trading optimizations
    from dex_django.apps.core.debug_server import create_configured_debug_app
    fastapi_app = create_configured_debug_app()
    
    # 3. Add discovery and copy trading routes
    fastapi_app.include_router(discovery_router, tags=["discovery"])
    fastapi_app.include_router(api_router, tags=["debug-api"])
    register_copy_trading_routes(fastapi_app)
    
    # 4. Create Django Channels WebSocket application
    django_channels_app = create_django_channels_app()
    
    # 5. Create unified ASGI application
    from fastapi.middleware.wsgi import WSGIMiddleware
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from django.urls import path
    
    # Import WebSocket consumer
    from apps.ws.consumers import PaperTradingConsumer
    
    # WebSocket routing
    websocket_urlpatterns = [
        path('ws/paper', PaperTradingConsumer.as_asgi()),
    ]
    
    # Unified ASGI application
    application = ProtocolTypeRouter({
        "http": fastapi_app,  # FastAPI handles HTTP
        "websocket": AuthMiddlewareStack(  # Django Channels handles WebSocket
            URLRouter(websocket_urlpatterns)
        ),
    })
    
    logger.info("🚀 Unified ASGI application created - FastAPI + Django Channels")
    logger.info("📈 Optimized for trading speed and profit generation")
    
    return application


def setup_django_for_database():
    """Setup Django specifically for database access only."""
    try:
        import os
        import django
        from django.conf import settings
        
        # Set Django settings
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.dex_django.settings')
        
        # Configure Django for database access
        if not settings.configured:
            django.setup()
            logger.info("Django configured for database access")
        
        return True
        
    except Exception as e:
        logger.error(f"Django database setup failed: {e}")
        return False


def add_paper_trading_websocket(app):
    """Add FastAPI WebSocket endpoint for paper trading."""
    from fastapi import WebSocket, WebSocketDisconnect
    import json
    
    # WebSocket client registry
    paper_clients = set()
    
    @app.websocket("/ws/paper")
    async def websocket_paper_trading(websocket: WebSocket):
        """Paper trading WebSocket for real-time AI Thought Log streaming."""
        await websocket.accept()
        paper_clients.add(websocket)
        
        # Generate unique client ID
        client_id = str(uuid.uuid4())
        
        try:
            # Send welcome message
            await websocket.send_json({
                "type": "connection_established",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "client_id": client_id,
                "payload": {
                    "thought_log_active": False,
                    "connected_clients": len(paper_clients),
                    "features_available": {
                        "copy_trading": copy_trading_system_initialized,
                        "django_orm": True
                    }
                }
            })
            
            # Handle incoming messages
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data) if data else {}
                    
                    if message.get("type") == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "payload": {"client_id": client_id}
                        })
                    
                except Exception as e:
                    logger.debug(f"Error processing WebSocket message: {e}")
                    break
                    
        except WebSocketDisconnect:
            logger.info(f"Paper trading client {client_id[:8]} disconnected")
        except Exception as e:
            logger.error(f"Paper trading WebSocket error: {e}")
        finally:
            paper_clients.discard(websocket)
    
    logger.info("FastAPI WebSocket endpoint added: /ws/paper")


# ============================================================================
# COPY TRADING SYSTEM INTEGRATION - Optimized for Performance
# ============================================================================

# Global copy trading system status
copy_trading_system_initialized = False
copy_trading_service_manager = None


def install_missing_dependencies() -> None:
    """Install missing dependencies if needed."""
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        logger.info("Installing missing aiohttp dependency...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
        logger.info("aiohttp installed successfully")


async def initialize_copy_trading_system():
    """Initialize copy trading system for maximum trading performance."""
    global copy_trading_system_initialized, copy_trading_service_manager
    
    if copy_trading_system_initialized:
        logger.info("Copy trading system already initialized")
        return {"success": True, "message": "Already initialized"}
    
    try:
        logger.info("🚀 Initializing copy trading system for profit generation...")
        
        # Setup paths for dex_django
        dex_django_path = Path(__file__).parent / "dex_django"
        if str(dex_django_path) not in sys.path:
            sys.path.insert(0, str(dex_django_path))
            logger.info(f"Added dex_django path for performance: {dex_django_path}")
        
        # Import service manager
        from dex_django.apps.core.service_manager import service_manager
        copy_trading_service_manager = service_manager
        
        # Initialize all services with speed optimization
        result = await service_manager.initialize_all_services()
        
        if result["success"]:
            copy_trading_system_initialized = True
            logger.info("✅ Copy trading system ready for profit generation")
            return result
        else:
            logger.error(f"❌ Copy trading system initialization failed: {result['message']}")
            return result
    
    except ImportError as e:
        logger.warning(f"⚠️ Copy trading components not available: {e}")
        return {"success": False, "message": f"Copy trading components not available: {e}"}
    
    except Exception as e:
        logger.error(f"❌ Unexpected error during copy trading initialization: {e}")
        return {"success": False, "message": f"Unexpected error: {e}"}


async def shutdown_copy_trading_system():
    """Shutdown copy trading system gracefully."""
    global copy_trading_system_initialized, copy_trading_service_manager
    
    if not copy_trading_system_initialized:
        logger.info("Copy trading system not initialized, nothing to shutdown")
        return {"success": True, "message": "Nothing to shutdown"}
    
    try:
        logger.info("🛑 Shutting down copy trading system...")
        
        if copy_trading_service_manager:
            result = await copy_trading_service_manager.shutdown_all_services()
            
            if result["success"]:
                logger.info("✅ Copy trading system shut down successfully")
            else:
                logger.error(f"❌ Copy trading system shutdown failed: {result['message']}")
            
            copy_trading_system_initialized = False
            copy_trading_service_manager = None
            
            return result
        else:
            logger.warning("⚠️ Service manager not available for shutdown")
            return {"success": True, "message": "No service manager to shutdown"}
    
    except Exception as e:
        logger.error(f"❌ Error during copy trading shutdown: {e}")
        return {"success": False, "message": str(e)}


def register_copy_trading_routes(app):
    """Register copy trading API routes for trading performance."""
    try:
        logger.info("📡 Registering high-performance copy trading routes...")

        try:
            from dex_django.apps.api.copy_trading_integrated import router as integrated_router
            app.include_router(integrated_router, tags=["copy-trading-integrated"])

            logger.info("✅ Copy trading API routes registered for profit generation")

            # List trading endpoints
            copy_routes = [
                "GET /api/v1/copy/status",
                "POST /api/v1/copy/system/control", 
                "GET /api/v1/copy/traders",
                "POST /api/v1/copy/traders",
                "DELETE /api/v1/copy/traders/{trader_key}",
                "GET /api/v1/copy/traders/{trader_key}",
                "GET /api/v1/copy/trades",
                "POST /api/v1/copy/paper/toggle",
                "GET /api/v1/copy/health",
            ]

            logger.info("Available high-speed trading endpoints:")
            for route in copy_routes:
                logger.info(f"  - {route}")

        except ImportError as e:
            logger.warning(f"⚠️ Copy trading API not available: {e}")

        # Note: WebSocket endpoints handled by Django Channels in unified app
        logger.info("📝 WebSocket endpoints handled by Django Channels (unified):")
        logger.info("  - WS /ws/paper (Real-time AI Thought Log streaming)")

        return {"success": True, "message": "Copy trading routes registered for performance"}

    except Exception as e:
        logger.error(f"❌ Failed to register copy trading routes: {e}")
        return {"success": False, "message": f"Route registration failed: {e}"}


# ============================================================================
# REAL OPPORTUNITIES FETCHING - Optimized for Speed
# ============================================================================

async def fetch_real_opportunities() -> List[Dict[str, Any]]:
    """
    Fetch REAL opportunities optimized for trading speed.
    Uses concurrent requests for minimum latency.
    """
    opportunities = []
    
    # Concurrent fetching for maximum speed
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=10),  # Faster timeout for trading
        connector=aiohttp.TCPConnector(limit=10)  # Connection pooling
    ) as session:
        
        # Fetch multiple chains concurrently for speed
        tasks = [
            fetch_chain_opportunities(session, "ethereum", 15),
            fetch_chain_opportunities(session, "bsc", 15), 
            fetch_chain_opportunities(session, "base", 10),
            fetch_chain_opportunities(session, "polygon", 10),
        ]
        
        # Execute all requests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        for result in results:
            if isinstance(result, list):
                opportunities.extend(result)
            else:
                logger.warning(f"Chain fetch failed: {result}")
    
    # Process and score opportunities for trading
    processed_opportunities = []
    for opp in opportunities:
        opp["opportunity_score"] = calculate_opportunity_score(opp)
        opp["profit_potential"] = calculate_profit_potential(opp)
        processed_opportunities.append(opp)
    
    # Sort by profit potential for trading priority
    processed_opportunities.sort(
        key=lambda x: (x.get("profit_potential", 0), x.get("opportunity_score", 0)), 
        reverse=True
    )
    
    # Remove duplicates while preserving order
    seen_pairs = set()
    unique_opportunities = []
    for opp in processed_opportunities:
        pair_key = f"{opp['chain']}_{opp['pair_address']}"
        if pair_key not in seen_pairs:
            seen_pairs.add(pair_key)
            unique_opportunities.append(opp)
    
    logger.info(f"📈 Returning {len(unique_opportunities)} profit opportunities")
    return unique_opportunities[:50]  # Top 50 for trading focus


async def fetch_chain_opportunities(session, chain: str, limit: int) -> List[Dict[str, Any]]:
    """Fetch opportunities from a specific chain with speed optimization."""
    opportunities = []
    
    try:
        url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}"
        
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                pairs = data.get("pairs", [])
                
                for pair in pairs[:limit]:
                    try:
                        # Extract liquidity with speed optimization
                        liquidity_data = pair.get("liquidity", {})
                        if isinstance(liquidity_data, dict):
                            liquidity_usd = float(liquidity_data.get("usd", 0))
                        else:
                            liquidity_usd = float(liquidity_data) if liquidity_data else 0
                        
                        # Skip low liquidity for trading efficiency
                        if liquidity_usd < 10000:
                            continue
                        
                        # Fast token extraction
                        base_token = pair.get("baseToken", {})
                        quote_token = pair.get("quoteToken", {})
                        
                        opp = {
                            "chain": chain,
                            "dex": pair.get("dexId", "unknown"),
                            "pair_address": pair.get("pairAddress", ""),
                            "token0_symbol": base_token.get("symbol", "UNKNOWN"),
                            "token1_symbol": quote_token.get("symbol", "UNKNOWN"),
                            "estimated_liquidity_usd": liquidity_usd,
                            "volume_24h": float(pair.get("volume", {}).get("h24", 0)) if pair.get("volume") else 0,
                            "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0)) if pair.get("priceChange") else 0,
                            "price_usd": float(pair.get("priceUsd", 0)) if pair.get("priceUsd") else 0,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "source": "dexscreener"
                        }
                        opportunities.append(opp)
                        
                    except Exception as e:
                        logger.debug(f"Error processing {chain} pair: {e}")
                        continue
                
                logger.info(f"📊 {chain.upper()}: Fetched {len(opportunities)} trading opportunities")
                
    except Exception as e:
        logger.error(f"Failed to fetch {chain} opportunities: {e}")
    
    return opportunities


def calculate_opportunity_score(opp: Dict[str, Any]) -> float:
    """Calculate opportunity score optimized for trading decisions."""
    score = 0.0
    
    # Liquidity score (critical for trading)
    liquidity = opp.get("estimated_liquidity_usd", 0)
    if liquidity > 1000000:  # High liquidity for large trades
        score += 15
    elif liquidity > 500000:
        score += 12
    elif liquidity > 200000:
        score += 8
    elif liquidity > 100000:
        score += 5
    elif liquidity > 50000:
        score += 2
    
    # Volume score (trading activity)
    volume = opp.get("volume_24h", 0)
    if volume > 2000000:
        score += 10
    elif volume > 1000000:
        score += 8
    elif volume > 500000:
        score += 6
    elif volume > 100000:
        score += 4
    elif volume > 50000:
        score += 2
    
    # Price momentum for trading
    price_change = opp.get("price_change_24h", 0)
    if 3 <= price_change <= 15:  # Optimal momentum
        score += 8
    elif 1 <= price_change < 3:
        score += 6
    elif -2 <= price_change < 1:
        score += 4
    elif -5 <= price_change < -2:  # Dip buying opportunity
        score += 3
    
    # Chain preference for speed
    chain = opp.get("chain", "unknown")
    if chain == "base":  # Fastest and cheapest
        score += 8
    elif chain == "bsc":  # Fast and cheap
        score += 7
    elif chain == "polygon":  # Fast
        score += 6
    elif chain == "ethereum":  # Highest liquidity but expensive
        score += 5
    
    return round(score, 2)


def calculate_profit_potential(opp: Dict[str, Any]) -> float:
    """Calculate profit potential for trading prioritization."""
    liquidity = opp.get("estimated_liquidity_usd", 0)
    volume = opp.get("volume_24h", 0)
    price_change = opp.get("price_change_24h", 0)
    
    # Profit potential based on liquidity, volume, and momentum
    profit_score = 0.0
    
    # High liquidity = more opportunities
    if liquidity > 1000000:
        profit_score += 10
    elif liquidity > 500000:
        profit_score += 8
    elif liquidity > 200000:
        profit_score += 6
    
    # High volume = active trading
    if volume > 1000000:
        profit_score += 8
    elif volume > 500000:
        profit_score += 6
    elif volume > 200000:
        profit_score += 4
    
    # Momentum scoring
    if 5 <= price_change <= 12:  # Strong uptrend
        profit_score += 12
    elif 2 <= price_change < 5:  # Moderate uptrend
        profit_score += 8
    elif -3 <= price_change < 2:  # Stable
        profit_score += 4
    elif -8 <= price_change < -3:  # Potential bounce
        profit_score += 6
    
    return round(profit_score, 2)


# ============================================================================
# API ROUTERS - Trading Optimized Endpoints
# ============================================================================

api_router = APIRouter(prefix="/api/v1")
discovery_router = APIRouter(prefix="/api/v1")


@api_router.get("/copy/system/status")
async def get_copy_trading_system_status():
    """Get copy trading system status for trading dashboard."""
    try:
        global copy_trading_system_initialized, copy_trading_service_manager
        
        if not copy_trading_system_initialized:
            return {
                "status": "ok",
                "copy_trading": {
                    "available": False,
                    "initialized": False,
                    "message": "Copy trading system not initialized"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        if copy_trading_service_manager:
            service_status = copy_trading_service_manager.get_service_status()
            
            return {
                "status": "ok",
                "copy_trading": {
                    "available": True,
                    "initialized": copy_trading_system_initialized,
                    "service_status": service_status,
                    "performance_mode": "optimized"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            return {
                "status": "ok", 
                "copy_trading": {
                    "available": False,
                    "initialized": copy_trading_system_initialized,
                    "message": "Service manager not available"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    except Exception as e:
        logger.error(f"Error getting copy trading system status: {e}")
        return {
            "status": "error",
            "copy_trading": {
                "available": False,
                "initialized": False,
                "error": str(e)
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@discovery_router.post("/copy/discovery/discover-traders")
async def discover_traders_endpoint(request_data: dict = None):
    """Auto-discover high-performing traders for copy trading profits."""
    try:
        body = request_data or {}
        chains = body.get('chains', ['ethereum', 'bsc', 'base'])
        limit = min(body.get('limit', 10), 50)
        min_volume_usd = body.get('min_volume_usd', 10000.0)
        days_back = body.get('days_back', 7)
        auto_add_threshold = body.get('auto_add_threshold', 85.0)
        
        logger.info(f"🔍 Discovering profitable traders: chains={chains}, limit={limit}")
        
        # Mock high-performance traders for now
        discovered_traders = []

        return {
            "status": "ok",
            "success": True,
            "discovered_wallets": discovered_traders,
            "candidates": discovered_traders,
            "data": discovered_traders,
            "count": len(discovered_traders),
            "discovery_params": {
                "chains": chains,
                "limit": limit,
                "min_volume_usd": min_volume_usd,
                "days_back": days_back,
                "auto_add_threshold": auto_add_threshold
            },
            "performance_optimized": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Trader discovery error: {e}")
        return {
            "status": "error",
            "success": False,
            "error": str(e),
            "message": f"Discovery failed: {str(e)}",
            "discovered_wallets": [],
            "candidates": [],
            "data": [],
            "count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# ============================================================================
# UNIFIED APP FACTORY - Maximum Performance Configuration
# ============================================================================

def get_app():
    """
    Factory function for uvicorn - creates unified high-performance app.
    Optimized for trading speed and profit generation.
    """
    install_missing_dependencies()
    
    # Create unified ASGI application
    app = create_unified_asgi_app()
    
    logger.info("🎯 Unified trading server ready - optimized for profit")
    logger.info("📍 Copy trading status: http://127.0.0.1:8000/api/v1/copy/system/status")
    logger.info("📍 Trading API: http://127.0.0.1:8000/api/v1/copy/")
    logger.info("🔌 Real-time WebSocket: ws://127.0.0.1:8000/ws/paper")
    logger.info("⚡ Single-process architecture for maximum trading speed")
    
    return app


# ============================================================================
# MAIN ENTRY POINT - High Performance Trading Server
# ============================================================================

def main() -> None:
    """
    Main entry point for high-performance DEX Sniper Pro server.
    Optimized for speed, profit generation, and minimal latency.
    """
    logger.info("🚀 Starting DEX Sniper Pro - High Performance Trading Server")

    try:
        install_missing_dependencies()

        # Server configuration optimized for trading
        host = os.getenv("DEBUG_HOST", "127.0.0.1")
        port = int(os.getenv("DEBUG_PORT", "8000"))
        reload = os.getenv("DEBUG_RELOAD", "true").lower() == "true"

        logger.info("⚡ High-performance server configured:")
        logger.info("  Host: %s", host)
        logger.info("  Port: %d", port)
        logger.info("  Reload: %s", reload)
        logger.info("  Docs URL: http://%s:%d/docs", host, port)
        logger.info("  Health Check: http://%s:%d/health", host, port)
        logger.info("  Trading Status: http://%s:%d/api/v1/copy/system/status", host, port)
        logger.info("  Trading API: http://%s:%d/api/v1/copy/", host, port)
        logger.info("  Real-time WebSocket: ws://%s:%d/ws/paper", host, port)
        logger.info("📈 Unified FastAPI + Django Channels for maximum trading speed")

        # Performance-optimized server startup with Windows compatibility
        if reload:
            # Check for performance libraries and use if available
            try:
                import uvloop
                loop_type = "uvloop"
                logger.info("Using uvloop for maximum performance")
            except ImportError:
                loop_type = "asyncio" 
                logger.info("uvloop not available, using standard asyncio")
            
            try:
                import httptools
                http_type = "httptools"
            except ImportError:
                http_type = "h11"
                logger.info("httptools not available, using h11")
            
            uvicorn.run(
                "debug_main:get_app",
                host=host,
                port=port,
                reload=True,
                log_level="info",
                access_log=False,  # Disable for performance in dev
                loop=loop_type,
                http=http_type,
                ws_ping_interval=20,  # WebSocket optimization
                ws_ping_timeout=20,
            )
        else:
            # Direct app creation for production-like performance
            app = create_unified_asgi_app()
            
            # Manual initialization for non-reload mode
            async def startup():
                result = await initialize_copy_trading_system()
                if result["success"]:
                    logger.info("✅ Copy trading system ready for profit generation")
                else:
                    logger.warning(f"⚠️ Copy trading initialization failed: {result['message']}")
            
            try:
                asyncio.run(startup())
            except Exception as e:
                logger.warning(f"Startup task failed: {e}")
            
            # Check for performance libraries for production mode
            try:
                import uvloop
                loop_type = "uvloop"
            except ImportError:
                loop_type = "asyncio"
            
            try:
                import httptools
                http_type = "httptools"
            except ImportError:
                http_type = "h11"
            
            uvicorn.run(
                app,
                host=host,
                port=port,
                reload=False,
                log_level="info",
                access_log=False,  # Performance optimization
                loop=loop_type,
                http=http_type,
                ws_ping_interval=20,
                ws_ping_timeout=20,
            )

    except KeyboardInterrupt:
        logger.info("🛑 Trading server stopped by user")
        
        # Cleanup for clean shutdown
        if copy_trading_system_initialized:
            try:
                asyncio.run(shutdown_copy_trading_system())
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
    
    except Exception as e:
        logger.error("❌ Failed to start trading server: %s", e)
        import traceback
        logger.error("Full traceback: %s", traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()