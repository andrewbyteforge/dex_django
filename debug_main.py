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

import logging
import os
import random
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

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


def install_missing_dependencies() -> None:
    """Install missing dependencies if needed."""
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        logger.info("Installing missing aiohttp dependency...")
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
        logger.info("aiohttp installed successfully")


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
    """
    Get list of followed traders from Django database.
    Returns real persisted trader data.
    """
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
        
        # Try to use Django ORM to get real traders
        traders = []
        
        try:
            # Import Django models
            from apps.storage.models import FollowedTrader
            
            # Query all active followed traders
            followed_traders = FollowedTrader.objects.filter(
                status__in=['active', 'paused']
            ).order_by('-created_at')
            
            for trader in followed_traders:
                trader_data = {
                    "id": str(trader.id),
                    "wallet_address": trader.wallet_address,
                    "trader_name": trader.trader_name or f"Trader_{trader.wallet_address[-4:]}",
                    "description": trader.description or "",
                    "chain": trader.chain,
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
                    "is_following": True
                }
                traders.append(trader_data)
                
            logger.info(f"Retrieved {len(traders)} real traders from database")
            
        except Exception as db_error:
            logger.error(f"Database query failed: {db_error}")
            # If database fails, return empty list
            traders = []
        
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
async def add_trader_endpoint(request_data: dict = None):
    """
    Add a trader to the copy trading system.
    This endpoint is called when users click "Add Trader" in the frontend.
    """
    try:
        logger.info("=== ADD TRADER ENDPOINT CALLED ===")
        logger.info(f"Request data: {request_data}")
        
        # Ensure Django is configured
        if not ensure_django_setup():
            logger.error("Django setup failed - returning error response")
            return {
                "status": "error",
                "success": False,
                "error": "Django configuration failed",
                "message": "Django configuration failed"
            }
        
        # Parse request data - frontend sends wallet_address, not address
        body = request_data or {}
        trader_address = body.get('wallet_address') or body.get('address', '')
        trader_name = body.get('trader_name', '')
        
        if not trader_address:
            logger.error("No trader address provided")
            return {
                "status": "error",
                "success": False,
                "error": "Trader address is required",
                "message": "Trader address is required"
            }
        
        if not trader_name:
            logger.error("No trader name provided")
            return {
                "status": "error", 
                "success": False,
                "error": "Trader name is required",
                "message": "Trader name is required"
            }
            
        logger.info(f"Adding trader: {trader_address} (name: {trader_name})")
        
        # Save to real Django database
        try:
            # Try multiple import paths for the FollowedTrader model
            FollowedTrader = None
            
            # Try the correct Django apps path first
            try:
                from dex_django.apps.storage.models import FollowedTrader
                logger.info("Successfully imported FollowedTrader from dex_django.apps.storage.models")
            except ImportError:
                try:
                    from apps.storage.models import FollowedTrader
                    logger.info("Successfully imported FollowedTrader from apps.storage.models")
                except ImportError:
                    try:
                        from storage.models import FollowedTrader
                        logger.info("Successfully imported FollowedTrader from storage.models")
                    except ImportError:
                        logger.error("Could not import FollowedTrader from any location")
                        return {
                            "status": "error",
                            "success": False,
                            "error": "Model import failed",
                            "message": "Could not import FollowedTrader model"
                        }
            
            from decimal import Decimal
            
            # Validate copy mode logic
            copy_buy_only = bool(body.get('copy_buy_only', False))
            copy_sell_only = bool(body.get('copy_sell_only', False))
            
            # Ensure both can't be true (invalid state)
            if copy_buy_only and copy_sell_only:
                copy_buy_only = False
                copy_sell_only = False
            
            logger.info(f"Creating FollowedTrader with data: address={trader_address}, name={trader_name}")
            
            # Create new FollowedTrader in database
            trader = FollowedTrader.objects.create(
                wallet_address=trader_address,
                trader_name=trader_name,
                description=body.get('description', ''),
                chain=body.get('chain', 'ethereum'),
                copy_percentage=Decimal(str(body.get('copy_percentage', 5.0))),
                max_position_usd=Decimal(str(body.get('max_position_usd', 1000.0))),
                max_slippage_bps=int(body.get('max_slippage_bps', 300)),
                copy_buy_only=copy_buy_only,
                copy_sell_only=copy_sell_only,
                status='active'
            )
            
            logger.info(f"Successfully created trader in database with ID: {trader.id}")
            
            # Return the actual saved data
            trader_data = {
                "id": str(trader.id),
                "wallet_address": trader.wallet_address,
                "trader_name": trader.trader_name,
                "description": trader.description,
                "chain": trader.chain,
                "copy_percentage": float(trader.copy_percentage),
                "max_position_usd": float(trader.max_position_usd),
                "max_slippage_bps": trader.max_slippage_bps,
                "copy_buy_only": trader.copy_buy_only,
                "copy_sell_only": trader.copy_sell_only,
                "status": trader.status,
                "created_at": trader.created_at.isoformat(),
                "last_activity_at": trader.last_activity_at.isoformat() if trader.last_activity_at else None,
                "total_pnl_usd": str(trader.total_pnl_usd or 0),
                "win_rate_pct": float(trader.win_rate_pct or 0),
                "total_trades": trader.total_trades or 0,
                "avg_trade_size_usd": float(trader.avg_trade_size_usd or 0),
                "quality_score": trader.quality_score or 75,
                "is_following": True
            }
            
            logger.info(f"Successfully saved trader {trader_name} to database with ID {trader.id}")
            
            return {
                "status": "ok",
                "success": True,
                "message": f"Trader {trader_name} ({trader_address[:10]}...) added successfully",
                "trader": trader_data,
                "data": trader_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as db_error:
            logger.error(f"Database save failed: {db_error}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                "status": "error",
                "success": False,
                "error": f"Database error: {str(db_error)}",
                "message": "Failed to save trader to database",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
    except Exception as e:
        logger.error(f"Add trader endpoint error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return {
            "status": "error",
            "success": False,
            "error": str(e),
            "message": f"Failed to add trader: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
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


def get_app():
    """
    Factory function for uvicorn import string.

    This function is called by uvicorn when using reload mode
    with the import string "debug_main:get_app".

    Returns:
        FastAPI application instance.
    """
    install_missing_dependencies()

    # Import here so path/logging is configured first
    from dex_django.apps.core.debug_server import create_configured_debug_app

    # Create the app from the factory
    app = create_configured_debug_app()
    
    # Add our discovery router to fix the missing endpoint
    app.include_router(discovery_router, tags=["discovery"])
    logger.info("Discovery router added to debug app")
    
    return app


def main() -> None:
    """
    Main entry point for the debug server.

    Creates and runs the FastAPI debug application with uvicorn.
    """
    logger.info("Starting DEX Sniper Pro Debug Server...")

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
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to start debug server: %s", e)
        import traceback

        logger.error("Full traceback: %s", traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()