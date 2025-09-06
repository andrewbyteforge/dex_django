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
from fastapi import APIRouter, HTTPException


logging.getLogger("api.copy_trading_discovery").setLevel(logging.INFO)
logging.getLogger("discovery").setLevel(logging.INFO)

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




# Import the routers
try:
    from dex_django.apps.api.debug_routers import health_router, api_router
    logger.info("✅ Successfully imported debug_routers")
except ImportError as e:
    logger.error(f"❌ Failed to import debug_routers: {e}")
    # Create fallback routers
    health_router = APIRouter(prefix="/health", tags=["health"])
    api_router = APIRouter(prefix="/api/v1", tags=["debug-api"])

# CREATE THE MISSING DISCOVERY ROUTER
discovery_router = APIRouter(prefix="/api/v1", tags=["discovery"])



def load_environment_variables():
    """Load environment variables from .env file."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("Environment variables loaded from .env file")
    except ImportError:
        logger.warning("python-dotenv not installed, using system environment variables")
    except Exception as e:
        logger.error(f"Error loading environment variables: {e}")

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
        import django
        from django.conf import settings
        
        if not settings.configured:
            settings.configure(
                DEBUG=True,
                DATABASES={
                    'default': {
                        'ENGINE': 'django.db.backends.sqlite3',
                        'NAME': os.path.join(current_dir, 'db.sqlite3'),
                    }
                },
                INSTALLED_APPS=[
                    'django.contrib.contenttypes',
                    'django.contrib.auth',
                    'dex_django.apps.core',
                    'dex_django.apps.ledger',        # Add this
                    'dex_django.apps.intelligence',  # Add this
                ],
                USE_TZ=True,
                SECRET_KEY='debug-secret-key-not-for-production',
                DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
            )
            
        django.setup()
        
        # Create the required model files if they don't exist
        create_django_model_files()
        
        logger.info("Django ORM initialized successfully with copy trading apps")
        return True
        
    except Exception as e:
        logger.error(f"Django setup failed: {e}")
        return False



def create_django_model_files():
    """Create minimal Django model files for copy trading."""
    try:
        # Create ledger models
        ledger_models_path = os.path.join(current_dir, 'dex_django', 'apps', 'ledger', 'models.py')
        os.makedirs(os.path.dirname(ledger_models_path), exist_ok=True)
        
        ledger_models_content = '''
from django.db import models
import uuid

class FollowedTrader(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    wallet_address = models.CharField(max_length=42)
    trader_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    chain = models.CharField(max_length=20, default='ethereum')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class CopyTrade(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    followed_trader = models.ForeignKey(FollowedTrader, on_delete=models.CASCADE)
    token_symbol = models.CharField(max_length=20)
    action = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
'''
        
        with open(ledger_models_path, 'w') as f:
            f.write(ledger_models_content)
        
        # Create intelligence models
        intelligence_models_path = os.path.join(current_dir, 'dex_django', 'apps', 'intelligence', 'models.py')
        os.makedirs(os.path.dirname(intelligence_models_path), exist_ok=True)
        
        intelligence_models_content = '''
from django.db import models
import uuid

class WalletAnalysis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    wallet_address = models.CharField(max_length=42)
    quality_score = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

class TraderCandidate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    wallet_address = models.CharField(max_length=42)
    chain = models.CharField(max_length=20)
    quality_score = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
'''
        
        with open(intelligence_models_path, 'w') as f:
            f.write(intelligence_models_content)
            
        # Create __init__.py files
        for path in [
            os.path.join(current_dir, 'dex_django', 'apps', 'ledger', '__init__.py'),
            os.path.join(current_dir, 'dex_django', 'apps', 'intelligence', '__init__.py')
        ]:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write('')
                
        logger.info("Created Django model files for copy trading")
        
    except Exception as e:
        logger.error(f"Failed to create Django model files: {e}")



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
            # Use the REAL copy trading router instead of integrated
            from dex_django.apps.api.copy_trading_real import router as real_router
            app.include_router(real_router, tags=["copy-trading-real"])
            logger.info("✅ Copy trading REAL API routes registered successfully")

            # List available endpoints
            copy_routes = [
                "GET /api/v1/copy/status",
                "GET /api/v1/copy/traders",
                "POST /api/v1/copy/traders",  # This will now work!
                "DELETE /api/v1/copy/traders/{trader_key}",
                "GET /api/v1/copy/trades",
                "POST /api/v1/copy/discovery/discover-traders",
                "GET /api/v1/copy/discovery/status",
                "POST /api/v1/copy/discovery/analyze-wallet",
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




@api_router.post("/copy/discovery/discover-traders")
async def discover_traders_endpoint(request_data: dict = None):
    """Auto-discover REAL traders with optimized API usage."""
    
    logger.info(f"🔍 DISCOVERY ENDPOINT HIT: /copy/discovery/discover-traders")
    logger.info(f"📥 Request data: {request_data}")
    
    try:
        # Parse the request data
        if request_data is None:
            logger.warning("⚠️ No request data provided, using defaults")
            request_data = {
                "chains": ["ethereum", "bsc"],
                "limit": 20,
                "min_volume_usd": 50000,
                "days_back": 30,
                "auto_add_threshold": 80.0
            }
        
        logger.info(f"🎯 Processing request: {request_data}")
        
        # Import and call the real discovery function
        from dex_django.apps.api.copy_trading_real import discover_traders_real, DiscoveryRequest
        
        # Create the discovery request
        request = DiscoveryRequest(**request_data)
        logger.info(f"✅ DiscoveryRequest created: chains={request.chains}, limit={request.limit}")
        
        # Call the actual discovery function
        logger.info("🚀 Calling discover_traders_real...")
        discovered_wallets = await discover_traders_real(request)
        
        logger.info(f"📈 discover_traders_real returned: {len(discovered_wallets)} wallets")
        
        # Log each wallet for debugging
        for i, wallet in enumerate(discovered_wallets):
            logger.info(f"💰 Wallet {i+1}: {wallet.get('address', 'N/A')[:10]}... score: {wallet.get('quality_score', 'N/A')}")
        
        # Prepare response
        response = {
            "status": "ok",
            "success": True,
            "discovered_wallets": discovered_wallets,
            "candidates": discovered_wallets,  # For frontend compatibility
            "data": discovered_wallets,        # For frontend compatibility
            "count": len(discovered_wallets),
            "data_source": "real_blockchain_apis",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"📤 Final response: status={response['status']}, count={response['count']}")
        return response
        
    except ImportError as e:
        logger.error(f"❌ Failed to import discovery functions: {e}")
        raise HTTPException(500, "Discovery system not available")
        
    except Exception as e:
        logger.error(f"❌ Discovery failed: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Discovery failed: {str(e)}")

async def get_top_trader_for_token(session, token_address: str, chain: str) -> str:
    """Get REAL top trader address using optimized blockchain API calls."""
    try:
        # API endpoints for different chains
        api_endpoints = {
            "ethereum": "https://api.etherscan.io/api",
            "bsc": "https://api.bscscan.com/api", 
            "polygon": "https://api.polygonscan.com/api",
            "base": "https://api.basescan.org/api"
        }
        
        api_key = os.getenv("ETHERSCAN_API_KEY", "")
        
        if chain not in api_endpoints or not api_key:
            logger.warning(f"No API endpoint or key for chain {chain}")
            return None
            
        base_url = api_endpoints[chain]
        
        # Get recent transactions for this token with shorter timeout
        params = {
            "module": "account",
            "action": "tokentx", 
            "contractaddress": token_address,
            "page": 1,
            "offset": 50,  # Reduced from 100 to 50
            "sort": "desc",
            "apikey": api_key
        }
        
        # Use shorter timeout to prevent hanging
        timeout = aiohttp.ClientTimeout(total=5)
        
        async with session.get(base_url, params=params, timeout=timeout) as response:
            if response.status == 200:
                data = await response.json()
                
                if data.get("status") == "1" and data.get("result"):
                    transactions = data["result"]
                    
                    # Quick analysis - just get the most recent high-value trader
                    for tx in transactions[:10]:  # Only check first 10 transactions
                        try:
                            from_addr = tx.get("from", "")
                            value = float(tx.get("value", 0))
                            
                            # If we find a transaction with decent value, use that address
                            if value > 0 and from_addr and from_addr.startswith("0x") and len(from_addr) == 42:
                                logger.info(f"Found real trader {from_addr[:10]}... for token {token_address[:8]}... on {chain}")
                                return from_addr
                                
                        except (ValueError, TypeError):
                            continue
                
        logger.warning(f"No transactions found for token {token_address} on {chain}")
        return None
        
    except asyncio.TimeoutError:
        logger.warning(f"Timeout fetching trader for {token_address} on {chain}")
        return None
    except Exception as e:
        logger.error(f"Error fetching real trader for {token_address} on {chain}: {e}")
        return None







def calculate_confidence_from_pair_data(pair: dict) -> float:
    """Calculate trader confidence based on pair performance."""
    volume_24h = float(pair.get("volume", {}).get("h24", 0))
    price_change = float(pair.get("priceChange", {}).get("h24", 0))
    liquidity = float(pair.get("liquidity", {}).get("usd", 0))
    
    score = 50  # Base score
    
    # Volume scoring
    if volume_24h > 1000000:
        score += 20
    elif volume_24h > 500000:
        score += 15
    elif volume_24h > 100000:
        score += 10
    
    # Price stability scoring
    if -5 <= price_change <= 15:
        score += 15
    elif -10 <= price_change <= 25:
        score += 10
    
    # Liquidity scoring
    if liquidity > 1000000:
        score += 15
    elif liquidity > 500000:
        score += 10
    
    return min(95, max(60, score))


def estimate_trade_count(volume_24h: float) -> int:
    """Estimate trade count based on volume."""
    avg_trade_size = random.uniform(1000, 5000)
    return int(volume_24h / avg_trade_size)


def estimate_win_rate_from_volume(pair: dict) -> float:
    """Estimate win rate based on trading patterns."""
    price_change = float(pair.get("priceChange", {}).get("h24", 0))
    volume = float(pair.get("volume", {}).get("h24", 0))
    
    base_rate = 65.0
    
    if price_change > 0 and volume > 500000:
        base_rate += 10
    elif price_change > 0:
        base_rate += 5
    
    return min(85.0, max(55.0, base_rate + random.uniform(-5, 5)))


def assess_risk_level(pair: dict) -> str:
    """Assess risk level based on pair characteristics."""
    liquidity = float(pair.get("liquidity", {}).get("usd", 0))
    price_change = abs(float(pair.get("priceChange", {}).get("h24", 0)))
    
    if liquidity > 1000000 and price_change < 20:
        return "Low"
    elif liquidity > 500000 and price_change < 50:
        return "Medium-Low"
    elif price_change < 100:
        return "Medium"
    else:
        return "High"




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
            from fastapi import APIRouter, HTTPException
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
        # Load environment variables first
        load_environment_variables()

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