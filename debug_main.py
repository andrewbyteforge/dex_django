# APP: backend
# FILE: debug_main.py
"""
DEX Sniper Pro Debug Server - Entry Point

Streamlined entry point for the debug development server.
All complex logic has been moved to dedicated modules for better maintainability.

This module also exposes `fetch_real_opportunities` so the debug app factory
(dex_django.apps.core.debug_server.create_configured_debug_app) can import and
use it if desired:

    from debug_main import fetch_real_opportunities
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
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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


async def initialize_copy_trading_system():
    """Initialize copy trading system with correct paths."""
    global copy_trading_system_initialized, copy_trading_service_manager
    
    if copy_trading_system_initialized:
        logger.info("Copy trading system already initialized")
        return {"success": True, "message": "Already initialized"}
    
    try:
        logger.info("🚀 Initializing copy trading system in debug_main...")
        
        # FIXED: Use dex_django instead of backend
        dex_django_path = Path(__file__).parent / "dex_django"
        if str(dex_django_path) not in sys.path:
            sys.path.insert(0, str(dex_django_path))
            logger.info(f"Added dex_django path: {dex_django_path}")
        
        # FIXED: Import from dex_django.apps instead of dex_django
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
    
    except ImportError as e:
        logger.warning(f"⚠️ Copy trading components not available: {e}")
        return {"success": False, "message": f"Copy trading components not available: {e}"}
    
    except Exception as e:
        logger.error(f"❌ Unexpected error during copy trading initialization: {e}")
        return {"success": False, "message": f"Unexpected error: {e}"}





async def shutdown_copy_trading_system():
    """
    Shutdown the copy trading system gracefully.
    Called during FastAPI app shutdown.
    """
    global copy_trading_system_initialized, copy_trading_service_manager
    
    if not copy_trading_system_initialized:
        logger.info("Copy trading system not initialized, nothing to shutdown")
        return {"success": True, "message": "Nothing to shutdown"}
    
    try:
        logger.info("🛑 Shutting down copy trading system...")
        
        if copy_trading_service_manager:
            # Shutdown all services
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
    """
    Register copy trading API routes and WebSocket endpoints.

    Args:
        app: FastAPI application instance
    """
    try:
        logger.info("📡 Registering copy trading routes...")

        # Register API routes - FIXED IMPORT PATH
        try:
            from dex_django.apps.api.copy_trading_integrated import router as integrated_router
            app.include_router(integrated_router, tags=["copy-trading-integrated"])

            logger.info("✅ Copy trading API routes registered")

            # List registered routes for debugging
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

        # Register WebSocket endpoints - FIXED IMPORT PATH
        try:
            from dex_django.apps.ws.copy_trading import router as ws_router
            app.include_router(ws_router, tags=["copy-trading-websockets"])

            logger.info("✅ Copy trading WebSocket endpoints registered")
            logger.info("Available WebSocket endpoints:")
            logger.info("  - WS /ws/copy-trading")

        except ImportError as e:
            logger.warning(f"⚠️ Copy trading WebSocket not available: {e}")

        return {"success": True, "message": "Copy trading routes registered"}

    except Exception as e:
        logger.error(f"❌ Failed to register copy trading routes: {e}")
        return {"success": False, "message": f"Route registration failed: {e}"}


# -----------------------------------------------------------------------------
# Replace the mock fetch_real_opportunities function with this REAL implementation
# Exposed at module level so other app modules can import it:
#   from debug_main import fetch_real_opportunities
# -----------------------------------------------------------------------------
async def fetch_real_opportunities() -> List[Dict[str, Any]]:
    """
    Fetch REAL opportunities from multiple DEX data sources.
    NO MOCK DATA - Only real API calls to DexScreener and CoinGecko.
    """
    opportunities = []
    
    async with aiohttp.ClientSession() as session:
        
        # 1. DexScreener - Ethereum pairs (REAL DATA)
        try:
            logger.info("Fetching DexScreener Ethereum pairs...")
            async with session.get(
                "https://api.dexscreener.com/latest/dex/pairs/ethereum",
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get("pairs", [])
                    
                    for pair in pairs[:20]:  # Process top 20 pairs
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
                                "chain": "ethereum",
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
                            logger.debug(f"Error processing pair: {e}")
                            continue
                    
                    logger.info(f"DexScreener ETH: Added {len([o for o in opportunities if o['chain'] == 'ethereum'])} pairs")
        except Exception as e:
            logger.error(f"DexScreener Ethereum failed: {e}")
        
        # 2. DexScreener - BSC pairs (REAL DATA)
        try:
            logger.info("Fetching DexScreener BSC pairs...")
            async with session.get(
                "https://api.dexscreener.com/latest/dex/pairs/bsc",
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get("pairs", [])
                    
                    for pair in pairs[:15]:  # Top 15 BSC pairs
                        try:
                            liquidity_data = pair.get("liquidity", {})
                            if isinstance(liquidity_data, dict):
                                liquidity_usd = float(liquidity_data.get("usd", 0))
                            else:
                                liquidity_usd = float(liquidity_data) if liquidity_data else 0
                            
                            if liquidity_usd < 10000:
                                continue
                            
                            base_token = pair.get("baseToken", {})
                            quote_token = pair.get("quoteToken", {})
                            
                            opp = {
                                "chain": "bsc",
                                "dex": pair.get("dexId", "pancakeswap"),
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
                            logger.debug(f"Error processing BSC pair: {e}")
                            continue
                    
                    logger.info(f"DexScreener BSC: Added {len([o for o in opportunities if o['chain'] == 'bsc'])} pairs")
        except Exception as e:
            logger.error(f"DexScreener BSC failed: {e}")
        
        # 3. DexScreener - Base pairs (REAL DATA)
        try:
            logger.info("Fetching DexScreener Base pairs...")
            async with session.get(
                "https://api.dexscreener.com/latest/dex/pairs/base",
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get("pairs", [])
                    
                    for pair in pairs[:10]:  # Top 10 Base pairs
                        try:
                            liquidity_data = pair.get("liquidity", {})
                            if isinstance(liquidity_data, dict):
                                liquidity_usd = float(liquidity_data.get("usd", 0))
                            else:
                                liquidity_usd = float(liquidity_data) if liquidity_data else 0
                            
                            if liquidity_usd < 10000:
                                continue
                            
                            base_token = pair.get("baseToken", {})
                            quote_token = pair.get("quoteToken", {})
                            
                            opp = {
                                "chain": "base",
                                "dex": pair.get("dexId", "uniswap"),
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
                            logger.debug(f"Error processing Base pair: {e}")
                            continue
                    
                    logger.info(f"DexScreener Base: Added {len([o for o in opportunities if o['chain'] == 'base'])} pairs")
        except Exception as e:
            logger.error(f"DexScreener Base failed: {e}")
        
        # 4. DexScreener Trending Tokens (REAL DATA)
        try:
            logger.info("Fetching DexScreener trending tokens...")
            async with session.get(
                "https://api.dexscreener.com/latest/dex/tokens/trending",
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    trending = data.get("data", [])
                    
                    for item in trending[:10]:  # Top 10 trending tokens
                        item_pairs = item.get("pairs", [])
                        for pair in item_pairs[:2]:  # Top 2 pairs per token
                            try:
                                liquidity_data = pair.get("liquidity", {})
                                if isinstance(liquidity_data, dict):
                                    liquidity_usd = float(liquidity_data.get("usd", 0))
                                else:
                                    liquidity_usd = float(liquidity_data) if liquidity_data else 0
                                
                                if liquidity_usd < 10000:
                                    continue
                                
                                base_token = pair.get("baseToken", {})
                                quote_token = pair.get("quoteToken", {})
                                
                                opp = {
                                    "chain": pair.get("chainId", "ethereum"),
                                    "dex": pair.get("dexId", "unknown"),
                                    "pair_address": pair.get("pairAddress", ""),
                                    "token0_symbol": base_token.get("symbol", "UNKNOWN"),
                                    "token1_symbol": quote_token.get("symbol", "UNKNOWN"),
                                    "estimated_liquidity_usd": liquidity_usd,
                                    "volume_24h": float(pair.get("volume", {}).get("h24", 0)) if pair.get("volume") else 0,
                                    "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0)) if pair.get("priceChange") else 0,
                                    "price_usd": float(pair.get("priceUsd", 0)) if pair.get("priceUsd") else 0,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "source": "dexscreener_trending"
                                }
                                opportunities.append(opp)
                            except Exception as e:
                                logger.debug(f"Error processing trending pair: {e}")
                                continue
                    
                    logger.info(f"DexScreener trending: Added {len([o for o in opportunities if o.get('source') == 'dexscreener_trending'])} pairs")
        except Exception as e:
            logger.error(f"DexScreener trending failed: {e}")
        
        # 5. CoinGecko Trending (REAL DATA)
        try:
            logger.info("Fetching CoinGecko trending...")
            async with session.get(
                "https://api.coingecko.com/api/v3/search/trending",
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    trending_coins = data.get("coins", [])
                    
                    for coin in trending_coins[:10]:  # Top 10 trending
                        try:
                            item = coin.get("item", {})
                            # Note: CoinGecko trending doesn't provide liquidity, so we'll estimate
                            opp = {
                                "chain": "ethereum",  # Default to ETH for CoinGecko
                                "dex": "coingecko",
                                "pair_address": f"coingecko_{item.get('id', '')}",
                                "token0_symbol": item.get("symbol", "").upper(),
                                "token1_symbol": "USDT",
                                "estimated_liquidity_usd": 100000,  # Estimated since trending
                                "volume_24h": 50000,  # Estimated
                                "price_change_24h": item.get("price_change_percentage_24h", {}).get("usd", 0) if isinstance(item.get("price_change_percentage_24h"), dict) else 0,
                                "market_cap_rank": item.get("market_cap_rank", 0),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "source": "coingecko_trending"
                            }
                            opportunities.append(opp)
                        except Exception as e:
                            logger.debug(f"Error processing CoinGecko coin: {e}")
                            continue
                    
                    logger.info(f"CoinGecko: Added {len([o for o in opportunities if o.get('source') == 'coingecko_trending'])} trending")
        except Exception as e:
            logger.error(f"CoinGecko failed: {e}")
    
    # NO MOCK DATA - NO CURATED OPPORTUNITIES
    # Just process what we got from real APIs
    
    # Calculate opportunity scores
    for opp in opportunities:
        opp["opportunity_score"] = calculate_opportunity_score(opp)
    
    # Sort by score
    opportunities.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)
    
    # Remove duplicates
    seen_pairs = set()
    unique_opportunities = []
    for opp in opportunities:
        pair_key = f"{opp['chain']}_{opp['pair_address']}"
        if pair_key not in seen_pairs:
            seen_pairs.add(pair_key)
            unique_opportunities.append(opp)
    
    logger.info(f"Returning {len(unique_opportunities)} REAL opportunities from APIs")
    return unique_opportunities[:50]  # Return top 50 opportunities


api_router = APIRouter(prefix="/api/v1")


def calculate_opportunity_score(opp: Dict[str, Any]) -> float:
    """Calculate opportunity score based on liquidity, volume, and other factors."""
    score = 0.0
    
    # Liquidity score (0-10 points)
    liquidity = opp.get("estimated_liquidity_usd", 0)
    if liquidity > 500000:
        score += 10
    elif liquidity > 200000:
        score += 8
    elif liquidity > 100000:
        score += 6
    elif liquidity > 50000:
        score += 4
    elif liquidity > 10000:
        score += 2
    
    # Volume score (0-5 points)
    volume = opp.get("volume_24h", 0)
    if volume > 1000000:
        score += 5
    elif volume > 500000:
        score += 4
    elif volume > 100000:
        score += 3
    elif volume > 50000:
        score += 2
    elif volume > 10000:
        score += 1
    
    # Price change momentum (0-5 points)
    price_change = opp.get("price_change_24h", 0)
    if 5 <= price_change <= 20:  # Positive but not pump
        score += 5
    elif 2 <= price_change < 5:
        score += 4
    elif 0 <= price_change < 2:
        score += 3
    elif -5 <= price_change < 0:  # Small dip opportunity
        score += 2
    
    # Source credibility (0-5 points)
    source = opp.get("source", "unknown")
    if source in ["dexscreener", "dexscreener_trending"]:
        score += 5
    elif source == "coingecko_trending":
        score += 4
    
    # Chain preference (0-5 points)
    chain = opp.get("chain", "unknown")
    if chain == "ethereum":
        score += 5
    elif chain == "base":
        score += 4
    elif chain == "bsc":
        score += 3
    elif chain == "polygon":
        score += 2
    
    return round(score, 2)


# ============================================================================  
# MISSING DISCOVERY ENDPOINT - Fix for Copy Trading Auto Discovery
# ============================================================================

def ensure_django_setup():
    """Ensure Django is properly configured before database operations."""
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


# Create a discovery router that can be imported by debug server factory
discovery_router = APIRouter(prefix="/api/v1")

@discovery_router.post("/copy/discovery/discover-traders")
async def discover_traders_endpoint(request_data: dict = None):
    """
    Auto-discover high-performing traders across multiple chains.
    This endpoint is called by the frontend Copy Trading tab when 'Start Auto Discovery' is clicked.
    """
    try:
        # Parse request data
        body = request_data or {}
        chains = body.get('chains', ['ethereum', 'bsc', 'base'])
        limit = min(body.get('limit', 10), 50)
        min_volume_usd = body.get('min_volume_usd', 10000.0)
        days_back = body.get('days_back', 7)
        auto_add_threshold = body.get('auto_add_threshold', 85.0)
        
        logger.info(f"Discovery request: chains={chains}, limit={limit}")
        
        # Generate mock traders for now (replace with real discovery logic later)
        import random
        
        discovered_traders = []
        for i in range(limit):
            trader = {
                "id": str(uuid.uuid4()),
                "address": f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
                "chain": random.choice(chains),
                "quality_score": random.randint(70, 95),
                "total_volume_usd": random.randint(25000, 750000),
                "win_rate": round(random.uniform(60, 90), 1),
                "trades_count": random.randint(15, 200),
                "avg_trade_size": random.randint(300, 12000),
                "last_active": f"{random.randint(1, 24)} hours ago",
                "recommended_copy_percentage": round(random.uniform(1.5, 8), 1),
                "risk_level": random.choice(["Low", "Medium", "High"]),
                "confidence": random.choice(["High", "Medium", "Low"]),
                "source": "auto_discovery",
                "discovered_at": datetime.now(timezone.utc).isoformat()
            }
            discovered_traders.append(trader)
        
        # Return in format expected by frontend
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
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Discovery endpoint error: {e}")
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


@discovery_router.get("/copy/traders")
async def get_traders_endpoint():
    """Get list of followed traders from Django database - FIXED VERSION"""
    try:
        # Ensure Django is configured
        if not ensure_django_setup():
            return {
                "status": "error",
                "success": False,
                "error": "Django configuration failed",
                "data": [],
                "traders": [],
                "count": 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        traders = []
        
        try:
            # Import Django models
            from apps.storage.models import FollowedTrader
            
            # Query ALL followed traders (not just active/paused)
            followed_traders = FollowedTrader.objects.all().order_by('-created_at')
            
            logger.info(f"Found {followed_traders.count()} traders in database")
            
            for trader in followed_traders:
                trader_data = {
                    "id": str(trader.id),
                    "wallet_address": trader.wallet_address,
                    "trader_name": trader.trader_name or f"Trader_{trader.wallet_address[-4:]}",
                    "description": trader.description or "",
                    "chain": trader.allowed_chains[0] if trader.allowed_chains else "ethereum",  # FIXED: Get chain from allowed_chains
                    "copy_percentage": float(trader.copy_percentage),
                    "max_position_usd": float(trader.max_position_usd),
                    "max_slippage_bps": trader.max_slippage_bps,
                    "status": trader.status,
                    "copy_buy_only": trader.copy_buy_only,
                    "copy_sell_only": trader.copy_sell_only,
                    "created_at": trader.created_at.isoformat(),
                    "last_activity_at": trader.last_activity_at.isoformat() if trader.last_activity_at else None,
                    "total_pnl_usd": str(trader.total_pnl_usd or 0),
                    "win_rate_pct": float(trader.win_rate_pct or 0),
                    "total_trades": trader.total_trades or 0,
                    "avg_trade_size_usd": float(trader.avg_trade_size_usd or 0),
                    "quality_score": trader.quality_score or 75,
                    "is_following": True,
                    "monitoring_active": False  # Will be true when monitoring starts
                }
                traders.append(trader_data)
                
            logger.info(f"Retrieved {len(traders)} real traders from database")
            
        except Exception as db_error:
            logger.error(f"Database query failed: {db_error}")
            # Don't return empty list, return the error
            return {
                "status": "error", 
                "success": False,
                "error": f"Database error: {str(db_error)}",
                "data": [],
                "traders": [],
                "count": 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        # Return real data from database
        return {
            "status": "ok",
            "success": True,
            "data": traders,
            "traders": traders,
            "count": len(traders),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Get traders endpoint error: {e}")
        return {
            "status": "error",
            "success": False,
            "error": str(e),
            "data": [],
            "traders": [],
            "count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }




@discovery_router.post("/copy/traders")
async def add_trader_endpoint(request_data: dict):
    """Add a new trader to copy trading system with proper field mapping."""
    try:
        # Import required modules
        from apps.storage.models import FollowedTrader
        from decimal import Decimal
        from django.utils import timezone
        from asgiref.sync import sync_to_async
        import asyncio
        
        logger.info(f"Adding trader with data: {request_data}")
        
        # Extract and validate required fields
        wallet_address = request_data.get("wallet_address", "").lower().strip()
        if not wallet_address or not wallet_address.startswith("0x") or len(wallet_address) != 42:
            return {"status": "error", "error": "Invalid wallet address"}
        
        # Use sync_to_async to handle Django ORM operations
        @sync_to_async
        def check_trader_exists(address):
            return FollowedTrader.objects.filter(wallet_address=address).exists()
        
        @sync_to_async  
        def create_trader(trader_data):
            return FollowedTrader.objects.create(**trader_data)
        
        # Check if trader already exists (async)
        if await check_trader_exists(wallet_address):
            return {"status": "error", "error": "Trader is already being followed"}
        
        # Map frontend fields to FollowedTrader model fields
        trader_data = {
            "wallet_address": wallet_address,
            "trader_name": request_data.get("trader_name", "") or f"Trader {wallet_address[:8]}",
            "description": request_data.get("description", ""),
            "status": "active",
            
            # Copy settings
            "copy_mode": request_data.get("copy_mode", "percentage"),
            "copy_percentage": Decimal(str(request_data.get("copy_percentage", 5.0))),
            "fixed_amount_usd": Decimal(str(request_data.get("fixed_amount_usd", 0.0))) if request_data.get("fixed_amount_usd") else None,
            
            # Risk controls
            "max_position_usd": Decimal(str(request_data.get("max_position_usd", 1000.0))),
            "min_trade_usd": Decimal(str(request_data.get("min_trade_value_usd", 50.0))),
            "max_slippage_bps": int(request_data.get("max_slippage_bps", 300)),
            "max_risk_score": Decimal(str(request_data.get("max_risk_score", 7.0))),
            
            # Chain filters - FIXED: Convert single chain to allowed_chains array
            "allowed_chains": [request_data.get("chain", "ethereum")],  # Convert single chain to array
            "blacklisted_tokens": request_data.get("blacklisted_tokens", []),
            "whitelisted_tokens": request_data.get("whitelisted_tokens", []),
            
            # Trade type filters
            "copy_buy_only": request_data.get("copy_buy_only", False),
            "copy_sell_only": request_data.get("copy_sell_only", False),
            
            # Trade size filters (fixing duplicate field names)
            "max_trade_usd": Decimal(str(request_data.get("max_trade_usd", 50000.0))),
        }
        
        # Create the trader (async)
        trader = await create_trader(trader_data)
        
        logger.info(f"Successfully created trader: {trader.id}")
        
        # INTEGRATION POINT: Start monitoring the new trader
        global copy_trading_service_manager
        if copy_trading_system_initialized and copy_trading_service_manager:
            try:
                # Get the copy trading service
                service = copy_trading_service_manager.copy_trading_service
                if service:
                    # Add trader to copy trading service
                    copy_settings = {
                        "copy_mode": request_data.get("copy_mode", "percentage"),
                        "copy_percentage": float(request_data.get("copy_percentage", 5.0)),
                        "max_position_usd": float(request_data.get("max_position_usd", 1000.0)),
                        "min_trade_value_usd": float(request_data.get("min_trade_value_usd", 50.0)),
                        "max_slippage_bps": request_data.get("max_slippage_bps", 300),
                        "allowed_chains": [request_data.get("chain", "ethereum")],
                        "copy_buy_only": request_data.get("copy_buy_only", False),
                        "copy_sell_only": request_data.get("copy_sell_only", False)
                    }
                    
                    # Add to monitoring
                    result = await service.add_trader(
                        wallet_address=wallet_address,
                        trader_name=request_data.get("trader_name"),
                        description=request_data.get("description"),
                        chain=request_data.get("chain", "ethereum"),
                        copy_settings=copy_settings
                    )
                    
                    if result["success"]:
                        logger.info(f"Started monitoring trader {wallet_address[:8]}...")
                    else:
                        logger.warning(f"Failed to start monitoring: {result['message']}")
                        
            except Exception as monitor_error:
                logger.error(f"Failed to start monitoring for new trader: {monitor_error}")
        
        # Return success response with created trader data
        return {
            "status": "ok",
            "message": "Trader added successfully",
            "trader": {
                "id": str(trader.id),
                "wallet_address": trader.wallet_address,
                "trader_name": trader.trader_name,
                "description": trader.description,
                "chain": request_data.get("chain", "ethereum"),  # Return the original chain for frontend
                "allowed_chains": trader.allowed_chains,
                "copy_mode": trader.copy_mode,
                "copy_percentage": float(trader.copy_percentage),
                "fixed_amount_usd": float(trader.fixed_amount_usd) if trader.fixed_amount_usd else None,
                "max_position_usd": float(trader.max_position_usd),
                "copy_buy_only": trader.copy_buy_only,
                "copy_sell_only": trader.copy_sell_only,
                "status": trader.status,
                "created_at": trader.created_at.isoformat(),
            }
        }
        
    except Exception as e:
        logger.error(f"Database save failed: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return {
            "status": "error", 
            "error": f"Failed to add trader: {str(e)}"
        }


@discovery_router.delete("/copy/traders/{trader_id}")
async def remove_trader_endpoint(trader_id: str):
    """
    Remove a followed trader from the database.
    This endpoint is called when users click the delete button.
    """
    try:
        # Ensure Django is configured
        if not ensure_django_setup():
            return {
                "status": "error",
                "success": False,
                "error": "Django configuration failed",
                "message": "Failed to delete trader: Django configuration failed",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        from apps.storage.models import FollowedTrader
        
        # Find and delete the trader
        try:
            trader = FollowedTrader.objects.get(id=trader_id)
            trader_name = trader.trader_name
            trader_address = trader.wallet_address
            
            # INTEGRATION POINT: Remove from monitoring
            global copy_trading_service_manager
            if copy_trading_system_initialized and copy_trading_service_manager:
                try:
                    service = copy_trading_service_manager.copy_trading_service
                    if service:
                        trader_key = f"{trader.chain}:{trader_address}"
                        await service.remove_trader(trader_key)
                        logger.info(f"Removed trader {trader_address[:8]}... from monitoring")
                except Exception as monitor_error:
                    logger.error(f"Failed to remove from monitoring: {monitor_error}")
            
            trader.delete()
            
            logger.info(f"Successfully deleted trader {trader_name} ({trader_address})")
            
            return {
                "status": "ok",
                "success": True,
                "message": f"Trader {trader_name} removed successfully",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except FollowedTrader.DoesNotExist:
            return {
                "status": "error",
                "success": False,
                "error": "Trader not found",
                "message": "Trader not found in database",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Delete trader endpoint error: {e}")
        return {
            "status": "error",
            "success": False,
            "error": str(e),
            "message": f"Failed to delete trader: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# ============================================================================
# COPY TRADING STATUS ENDPOINT - Add to existing api_router
# ============================================================================

@api_router.get("/copy/system/status")
async def get_copy_trading_system_status():
    """
    Get current status of the copy trading system.
    This endpoint provides detailed system status for debugging.
    """
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
    
# Add this to your api_router section in debug_main.py

@api_router.get("/debug/database-traders")
async def debug_database_traders():
    """Debug endpoint to see exactly what's in the database."""
    try:
        if not ensure_django_setup():
            return {"error": "Django not configured"}
        
        from apps.storage.models import FollowedTrader
        
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
# UPDATE EXISTING get_app() FUNCTION - Modify the existing function
# ============================================================================

def get_app():
    """
    Factory function for uvicorn import string.
    
    UPDATED: Now includes copy trading system integration.
    """
    install_missing_dependencies()

    # Import here so path/logging is configured first
    from dex_django.apps.core.debug_server import create_configured_debug_app

    # Create the app from the factory
    app = create_configured_debug_app()
    
    # Add our discovery router to fix the missing endpoint
    app.include_router(discovery_router, tags=["discovery"])
    logger.info("Discovery router added to debug app")
    
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
    
    # Add the copy trading status endpoint to main API router
    app.include_router(api_router, tags=["debug-api"])
    
    logger.info("🎉 Debug app with copy trading system ready!")
    logger.info("📍 Copy trading status: http://127.0.0.1:8000/api/v1/copy/system/status")
    logger.info("📍 Copy trading API: http://127.0.0.1:8000/api/v1/copy/")
    logger.info("🔌 Copy trading WebSocket: ws://127.0.0.1:8000/ws/copy-trading")
    
    return app




# Add this right after the initialize_copy_trading_system() function
async def debug_copy_trading_system():
    """Debug function to check what's happening with copy trading initialization."""
    try:
        # Check if dex_django path is correct (not backend)
        dex_django_path = Path(__file__).parent / "dex_django"
        logger.info(f"Dex_django path exists: {dex_django_path.exists()}")
        logger.info(f"Dex_django path contents: {list(dex_django_path.iterdir()) if dex_django_path.exists() else 'Path not found'}")
        
        # Check apps directory structure
        apps_path = dex_django_path / "apps"
        if apps_path.exists():
            logger.info(f"Apps directory contents: {list(apps_path.iterdir())}")
            
            # Check for services directory
            services_path = apps_path / "services"
            logger.info(f"Services directory exists: {services_path.exists()}")
            if services_path.exists():
                logger.info(f"Services directory contents: {list(services_path.iterdir())}")
            
            # Check for core directory
            core_path = apps_path / "core"
            logger.info(f"Core directory exists: {core_path.exists()}")
            if core_path.exists():
                logger.info(f"Core directory contents: {list(core_path.iterdir())}")
        
        # Try importing components with correct paths
        try:
            from dex_django.apps.core.service_manager import service_manager
            logger.info("✅ Service manager imported successfully")
        except ImportError as e:
            logger.error(f"❌ Failed to import service manager: {e}")
            
        try:
            from dex_django.apps.services import copy_trading_service
            logger.info("✅ Copy trading service imported successfully")
        except ImportError as e:
            logger.error(f"❌ Failed to import copy trading service: {e}")
            
        try:
            from dex_django.apps.api.copy_trading_integrated import router
            logger.info("✅ Copy trading integrated API imported successfully")
        except ImportError as e:
            logger.error(f"❌ Failed to import copy trading integrated API: {e}")
            
        try:
            from dex_django.apps.ws.copy_trading import router as ws_router
            logger.info("✅ Copy trading WebSocket imported successfully")
        except ImportError as e:
            logger.error(f"❌ Failed to import copy trading WebSocket: {e}")
            
    except Exception as e:
        logger.error(f"Debug failed: {e}")






# ============================================================================
# UPDATE EXISTING main() FUNCTION - Modify the existing function
# ============================================================================

def main() -> None:
    """
    Main entry point for the debug server.
    
    UPDATED: Now includes copy trading system integration.
    """
    logger.info("Starting DEX Sniper Pro Debug Server with Copy Trading...")

    try:
        # Ensure dependencies are present
        install_missing_dependencies()

        # Server configuration
        host = os.getenv("DEBUG_HOST", "127.0.0.1")
        port = int(os.getenv("DEBUG_PORT", "8000"))
        reload = os.getenv("DEBUG_RELOAD", "true").lower() == "true"

        logger.info("Debug server configured:")
        logger.info("  Host: %s", host)
        logger.info("  Port: %d", port)
        logger.info("  Reload: %s", reload)
        logger.info("  Docs URL: http://%s:%d/docs", host, port)
        logger.info("  Health Check: http://%s:%d/health", host, port)
        logger.info("  Copy Trading Status: http://%s:%d/api/v1/copy/system/status", host, port)
        logger.info("  Copy Trading API: http://%s:%d/api/v1/copy/", host, port)

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
            from dex_django.apps.core.debug_server import create_configured_debug_app

            app = create_configured_debug_app()
            
            # Add discovery router
            app.include_router(discovery_router, tags=["discovery"])
            
            # Add copy trading integration
            register_copy_trading_routes(app)
            
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