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

# System path setup - Add to path BEFORE importing app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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

    # If your factory supports DI, you could pass fetch_real_opportunities here.
    # e.g., create_configured_debug_app(fetch_real_opportunities=fetch_real_opportunities)
    return create_configured_debug_app()


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
