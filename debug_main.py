# APP: backend
# FILE: debug_main.py
"""
DEX Sniper Pro Debug Server - Entry Point

Streamlined entry point for the debug development server.
All complex logic has been moved to dedicated modules for better maintainability.

This module provides:
- FastAPI application factory for uvicorn
- Copy trading system integration
- Real-time opportunity fetching
- High-performance trading endpoints
"""

from __future__ import annotations

import aiohttp 
import asyncio
import logging
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import traceback
import uvicorn
import uuid
from fastapi import APIRouter

# System path setup - Add to path BEFORE importing app modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("debug_main")

# ============================================================================
# COPY TRADING SYSTEM INTEGRATION
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


def ensure_django_setup() -> bool:
    """Ensure Django is properly configured for database access."""
    try:
        import os
        import sys
        import django
        from django.conf import settings
        
        # Get the current working directory (should be D:\dex_django)
        current_dir = os.getcwd()
        logger.info(f"Current working directory: {current_dir}")
        
        # CRITICAL FIX: Add the current directory to Python path
        # This allows Python to find the dex_django.dex_django.settings module
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
            logger.info(f"Added {current_dir} to sys.path")
        
        # Verify the settings file exists at the expected location
        settings_file = os.path.join(current_dir, 'dex_django', 'dex_django', 'settings.py')
        logger.info(f"Settings file exists at {settings_file}: {os.path.exists(settings_file)}")
        
        # Set the Django settings module - this should now work
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.dex_django.settings')
        logger.info(f"Django settings module set to: {os.environ.get('DJANGO_SETTINGS_MODULE')}")
        
        # Show current Python path for debugging
        logger.info(f"Current Python path (first 3): {sys.path[:3]}")
        
        # Configure Django if not already configured
        if not settings.configured:
            django.setup()
            logger.info("Django setup() completed successfully")
        else:
            logger.info("Django already configured")
            
        # CRITICAL FIX: Check apps registry status without calling setup() again
        # This fixes the "populate() isn't reentrant" error
        from django.apps import apps
        if not apps.ready:
            # Only call setup if apps aren't ready AND settings aren't configured
            if not settings.configured:
                django.setup()
                logger.info("Django apps loaded successfully")
            else:
                # Django is configured but apps aren't ready - this shouldn't happen
                logger.warning("Django configured but apps not ready - this is unusual")
        else:
            logger.info("Django apps already loaded")
        
        # Test that we can now import Django models without error
        try:
            from django.apps import apps
            apps.check_apps_ready()
            logger.info("Django apps registry is ready")
        except Exception as app_error:
            logger.error(f"Django apps registry not ready: {app_error}")
            return False
            
        logger.info("Django configuration verified successfully")
        return True
        
    except Exception as e:
        logger.error(f"Django setup failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        logger.error(f"Current Python path: {sys.path[:5]}")
        logger.error(f"Current working directory: {os.getcwd()}")
        logger.error(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE', 'Not set')}")
        
        # Debug directory structure
        try:
            current_dir = os.getcwd()
            logger.error(f"Root directory contents: {os.listdir(current_dir)}")
            
            dex_django_path = os.path.join(current_dir, 'dex_django')
            if os.path.exists(dex_django_path):
                logger.error(f"dex_django directory contents: {os.listdir(dex_django_path)}")
                
                inner_path = os.path.join(dex_django_path, 'dex_django')
                if os.path.exists(inner_path):
                    logger.error(f"Inner dex_django contents: {os.listdir(inner_path)}")
                    
                    # Check if settings.py actually exists
                    settings_path = os.path.join(inner_path, 'settings.py')
                    logger.error(f"settings.py exists: {os.path.exists(settings_path)}")
                    
        except Exception as debug_e:
            logger.error(f"Error during debug info gathering: {debug_e}")
            
        return False


async def initialize_copy_trading_system():
    """Initialize copy trading system with correct paths."""
    global copy_trading_system_initialized, copy_trading_service_manager
    
    if copy_trading_system_initialized:
        logger.info("Copy trading system already initialized")
        return {"success": True, "message": "Already initialized"}
    
    try:
        logger.info("🚀 Initializing copy trading system...")
        
        # Ensure Django is setup first
        if not ensure_django_setup():
            logger.warning("Django setup failed - copy trading may have limited functionality")
            return {"success": False, "message": "Django setup failed"}
        
        # Setup paths for dex_django
        dex_django_path = Path(__file__).parent / "dex_django"
        if str(dex_django_path) not in sys.path:
            sys.path.insert(0, str(dex_django_path))
            logger.info(f"Added dex_django path: {dex_django_path}")
        
        # Try to import service manager
        try:
            from dex_django.apps.core.service_manager import service_manager
            copy_trading_service_manager = service_manager
            
            # Initialize all services
            result = await service_manager.initialize_all_services()
            
            if result["success"]:
                copy_trading_system_initialized = True
                logger.info("✅ Copy trading system initialized successfully")
                return result
            else:
                logger.error(f"❌ Copy trading system initialization failed: {result['message']}")
                return result
                
        except ImportError as import_e:
            logger.warning(f"⚠️ Copy trading service manager not available: {import_e}")
            # Continue without copy trading services
            copy_trading_system_initialized = True  # Mark as initialized to prevent retry loops
            return {"success": True, "message": "Copy trading services not available, running in basic mode"}
    
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
            copy_trading_system_initialized = False
            return {"success": True, "message": "No service manager to shutdown"}
    
    except Exception as e:
        logger.error(f"❌ Error during copy trading shutdown: {e}")
        return {"success": False, "message": str(e)}


def register_copy_trading_routes(app):
    """Register copy trading API routes."""
    try:
        logger.info("📡 Registering copy trading routes...")

        try:
            from dex_django.apps.api.copy_trading_integrated import router as integrated_router
            app.include_router(integrated_router, tags=["copy-trading-integrated"])
            logger.info("✅ Copy trading API routes registered successfully")

            # List available endpoints
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

            logger.info("Available copy trading endpoints:")
            for route in copy_routes:
                logger.info(f"  - {route}")

        except ImportError as e:
            logger.warning(f"⚠️ Copy trading API not available: {e}")

        return {"success": True, "message": "Copy trading routes registered"}

    except Exception as e:
        logger.error(f"❌ Failed to register copy trading routes: {e}")
        return {"success": False, "message": f"Route registration failed: {e}"}


# ============================================================================
# REAL OPPORTUNITIES FETCHING - For Development and Testing
# ============================================================================

async def fetch_real_opportunities() -> List[Dict[str, Any]]:
    """
    Fetch REAL opportunities from external APIs for development and testing.
    """
    opportunities = []
    
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            connector=aiohttp.TCPConnector(limit=10)
        ) as session:
            
            # Fetch multiple chains concurrently
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
    
        # Process and score opportunities
        processed_opportunities = []
        for opp in opportunities:
            opp["opportunity_score"] = calculate_opportunity_score(opp)
            opp["profit_potential"] = calculate_profit_potential(opp)
            processed_opportunities.append(opp)
        
        # Sort by profit potential
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
        
        logger.info(f"📈 Returning {len(unique_opportunities)} opportunities")
        return unique_opportunities[:50]  # Top 50
        
    except Exception as e:
        logger.error(f"Error fetching opportunities: {e}")
        return []


async def fetch_chain_opportunities(session, chain: str, limit: int) -> List[Dict[str, Any]]:
    """Fetch opportunities from a specific chain."""
    opportunities = []
    
    try:
        url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}"
        
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                pairs = data.get("pairs", [])
                
                for pair in pairs[:limit]:
                    try:
                        # Extract liquidity
                        liquidity_data = pair.get("liquidity", {})
                        if isinstance(liquidity_data, dict):
                            liquidity_usd = float(liquidity_data.get("usd", 0))
                        else:
                            liquidity_usd = float(liquidity_data) if liquidity_data else 0
                        
                        # Skip low liquidity
                        if liquidity_usd < 10000:
                            continue
                        
                        # Extract token info
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
                
                logger.info(f"📊 {chain.upper()}: Fetched {len(opportunities)} opportunities")
                
    except Exception as e:
        logger.error(f"Failed to fetch {chain} opportunities: {e}")
    
    return opportunities


def calculate_opportunity_score(opp: Dict[str, Any]) -> float:
    """Calculate opportunity score for ranking."""
    score = 0.0
    
    # Liquidity score
    liquidity = opp.get("estimated_liquidity_usd", 0)
    if liquidity > 1000000:
        score += 15
    elif liquidity > 500000:
        score += 12
    elif liquidity > 200000:
        score += 8
    elif liquidity > 100000:
        score += 5
    elif liquidity > 50000:
        score += 2
    
    # Volume score
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
    
    # Price momentum
    price_change = opp.get("price_change_24h", 0)
    if 3 <= price_change <= 15:
        score += 8
    elif 1 <= price_change < 3:
        score += 6
    elif -2 <= price_change < 1:
        score += 4
    elif -5 <= price_change < -2:
        score += 3
    
    # Chain preference
    chain = opp.get("chain", "unknown")
    if chain == "base":
        score += 8
    elif chain == "bsc":
        score += 7
    elif chain == "polygon":
        score += 6
    elif chain == "ethereum":
        score += 5
    
    return round(score, 2)


def calculate_profit_potential(opp: Dict[str, Any]) -> float:
    """Calculate profit potential for prioritization."""
    liquidity = opp.get("estimated_liquidity_usd", 0)
    volume = opp.get("volume_24h", 0)
    price_change = opp.get("price_change_24h", 0)
    
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
    if 5 <= price_change <= 12:
        profit_score += 12
    elif 2 <= price_change < 5:
        profit_score += 8
    elif -3 <= price_change < 2:
        profit_score += 4
    elif -8 <= price_change < -3:
        profit_score += 6
    
    return round(profit_score, 2)


# ============================================================================
# API ROUTERS - Debug Endpoints
# ============================================================================

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/copy/system/status")
async def get_copy_trading_system_status():
    """Get copy trading system status."""
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
                    "service_status": service_status
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


@api_router.get("/opportunities/live")
async def get_live_opportunities():
    """Get live trading opportunities."""
    try:
        opportunities = await fetch_real_opportunities()
        
        return {
            "status": "ok",
            "opportunities": opportunities,
            "count": len(opportunities),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching live opportunities: {e}")
        return {
            "status": "error",
            "error": str(e),
            "opportunities": [],
            "count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def debug_database_traders():
    """Debug function to check database traders."""
    try:
        if not ensure_django_setup():
            return {"error": "Django not configured"}
        
        from dex_django.apps.storage.models import FollowedTrader
        
        # Get all traders
        all_traders = FollowedTrader.objects.all()
        trader_count = all_traders.count()
        
        logger.info(f"Database contains {trader_count} total traders")
        
        traders_data = []
        for trader in all_traders:
            trader_info = {
                "id": str(trader.id),
                "wallet_address": trader.wallet_address,
                "trader_name": trader.trader_name,
                "status": trader.status,
                "created_at": trader.created_at.isoformat(),
                "allowed_chains": trader.allowed_chains,
            }
            traders_data.append(trader_info)
            logger.info(f"Trader: {trader.trader_name} - {trader.wallet_address}")
        
        return {
            "status": "ok",
            "database_traders": traders_data,
            "count": trader_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Database debug error: {e}")
        return {"error": str(e)}


# ============================================================================
# APP FACTORY - Fixed Implementation
# ============================================================================

def get_app():
    """
    Factory function for uvicorn import string.
    
    Creates the FastAPI application with all required components.
    """
    try:
        install_missing_dependencies()

        # Import here so path/logging is configured first
        from dex_django.apps.core.debug_server import create_configured_debug_app
        
        # Add debug logging for WebSocket import
        try:
            logger.info("🔍 Attempting to import WebSocket router...")
            from dex_django.apps.ws.debug_websockets import router as ws_router
            logger.info("✅ WebSocket router import successful")
            logger.info(f"WebSocket router type: {type(ws_router)}")
            
            # Check if router has routes
            if hasattr(ws_router, 'routes'):
                logger.info(f"WebSocket router has {len(ws_router.routes)} routes")
                for route in ws_router.routes:
                    logger.info(f"  - Route: {route.path} ({type(route).__name__})")
            else:
                logger.warning("⚠️ WebSocket router has no routes attribute")
                
        except Exception as import_error:
            logger.error(f"❌ WebSocket router import failed: {import_error}")
            logger.error(f"Import error type: {type(import_error)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Create a dummy router to prevent the app from crashing
            from fastapi import APIRouter
            ws_router = APIRouter()
            logger.info("Created dummy WebSocket router as fallback")

        # Create the app from the factory
        app = create_configured_debug_app()
        
        # ✅ REGISTER REAL WALLET DISCOVERY ROUTER (REPLACES MOCK)
        try:
            from dex_django.apps.api.wallet_discovery import router as real_discovery_router
            app.include_router(real_discovery_router, tags=["wallet-discovery"])
            logger.info("✅ Real wallet discovery router registered successfully")
            
            # List the real endpoints that are now available
            discovery_routes = [
                "POST /api/v1/discovery/discover-traders",
                "POST /api/v1/discovery/analyze-wallet", 
                "GET /api/v1/discovery/status",
                "POST /api/v1/discovery/add-discovered-wallet/{address}/{chain}",
                "POST /api/v1/discovery/continuous/start",
                "POST /api/v1/discovery/continuous/stop"
            ]
            
            logger.info("📋 Available discovery endpoints:")
            for route in discovery_routes:
                logger.info(f"  - {route}")
                
        except ImportError as e:
            logger.error(f"❌ Failed to import real wallet discovery router: {e}")
            logger.error("Discovery functionality will not be available")
            logger.error("This means the frontend will get 404 errors on discovery requests")
        
        # Add API router for copy trading status
        app.include_router(api_router, tags=["debug-api"])
        logger.info("API router added to debug app")
        
        # Add WebSocket router for real-time connections with debug logging
        try:
            logger.info("🔍 Attempting to include WebSocket router in app...")
            app.include_router(ws_router, tags=["websockets"])
            logger.info("✅ WebSocket router successfully included in debug app")
            
            # Log all routes after inclusion
            logger.info("📋 All app routes after WebSocket inclusion:")
            for route in app.routes:
                logger.info(f"  - {route.path} ({type(route).__name__})")
                
        except Exception as router_error:
            logger.error(f"❌ Failed to include WebSocket router: {router_error}")
            import traceback
            logger.error(f"Router inclusion traceback: {traceback.format_exc()}")
        
        # COPY TRADING INTEGRATION - Add copy trading routes
        register_copy_trading_routes(app)
        
        # Add startup and shutdown events
        @app.on_event("startup")
        async def startup_event():
            """Initialize copy trading system on startup."""
            logger.info("🚀 FastAPI startup - initializing copy trading system...")
            result = await initialize_copy_trading_system()
            
            if result["success"]:
                logger.info("✅ Copy trading system startup completed successfully")
            else:
                logger.warning(f"⚠️ Copy trading system startup failed: {result['message']}")
        
        @app.on_event("shutdown")
        async def shutdown_event():
            """Shutdown copy trading system on app shutdown."""
            logger.info("🛑 FastAPI shutdown - cleaning up copy trading system...")
            result = await shutdown_copy_trading_system()
            
            if result["success"]:
                logger.info("✅ Copy trading system shutdown completed successfully")
            else:
                logger.warning(f"⚠️ Copy trading system shutdown failed: {result['message']}")
        
        logger.info("🎉 Debug app with copy trading system ready!")
        logger.info("📍 Copy trading status: http://127.0.0.1:8000/api/v1/copy/system/status")
        logger.info("📍 Live opportunities: http://127.0.0.1:8000/api/v1/opportunities/live")
        logger.info("📍 Real discovery: http://127.0.0.1:8000/api/v1/discovery/discover-traders")
        logger.info("📍 Trading API: http://127.0.0.1:8000/api/v1/copy/")
        logger.info("🔌 WebSocket endpoints available at /ws/...")
        
        return app
        
    except Exception as e:
        logger.error(f"Failed to create app: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise
# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def main() -> None:
    """
    Main entry point for the debug server.
    """
    logger.info("🚀 Starting DEX Sniper Pro - High Performance Trading Server")

    try:
        # Ensure dependencies are present
        install_missing_dependencies()

        # Server configuration
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

        # Check for performance libraries and log availability
        try:
            import uvloop
            logger.info("uvloop available for enhanced performance")
        except ImportError:
            logger.info("uvloop not available, using standard asyncio")
        
        try:
            import httptools
            logger.info("httptools available for enhanced HTTP performance")
        except ImportError:
            logger.info("httptools not available, using h11")

        # Start the server with proper import string for reload mode
        if reload:
            uvicorn.run(
                "debug_main:get_app",
                host=host,
                port=port,
                reload=True,
                log_level="info",
                access_log=True,
            )
        else:
            # Direct app creation for non-reload mode
            app = get_app()
            
            # Add startup event for non-reload mode
            async def startup():
                result = await initialize_copy_trading_system()
                if result["success"]:
                    logger.info("✅ Copy trading system initialized in non-reload mode")
                else:
                    logger.warning(f"⚠️ Copy trading initialization failed: {result['message']}")
            
            # Run startup manually for non-reload mode
            try:
                asyncio.run(startup())
            except Exception as e:
                logger.warning(f"Startup task failed: {e}")
            
            uvicorn.run(
                app,
                host=host,
                port=port,
                reload=False,
                log_level="info",
                access_log=True,
            )

    except KeyboardInterrupt:  # pragma: no cover
        logger.info("Debug server stopped by user")
        
        # Cleanup copy trading system
        if copy_trading_system_initialized:
            try:
                asyncio.run(shutdown_copy_trading_system())
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
    
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to start debug server: %s", e)
        import traceback
        logger.error("Full traceback: %s", traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()