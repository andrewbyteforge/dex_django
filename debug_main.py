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
    """Fetch REAL opportunities from DexScreener and other APIs."""
    install_missing_dependencies()
    import aiohttp  # imported after ensuring it's installed

    opportunities: List[Dict[str, Any]] = []

    async with aiohttp.ClientSession() as session:
        # 1) DexScreener trending pairs - REAL API DATA
        try:
            logger.info("Fetching DexScreener trending pairs...")

            # Fetch from multiple chains for diversity
            chains_to_fetch = ["ethereum", "bsc", "polygon", "base", "solana"]

            for chain in chains_to_fetch:
                try:
                    url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}"
                    async with session.get(url, timeout=15) as response:
                        if response.status == 200:
                            data = await response.json()
                            pairs = data.get("pairs", [])

                            # Process top pairs with good liquidity
                            for pair in pairs[:10]:  # Top 10 per chain
                                liquidity_data = pair.get("liquidity", {})
                                liquidity_usd = (
                                    float(liquidity_data.get("usd", 0))
                                    if isinstance(liquidity_data, dict)
                                    else 0.0
                                )

                                if liquidity_usd >= 10000:  # Minimum $10k liquidity
                                    base_token = pair.get("baseToken", {}) or {}
                                    quote_token = pair.get("quoteToken", {}) or {}
                                    volume_data = pair.get("volume", {}) or {}
                                    price_change = pair.get("priceChange", {}) or {}

                                    # Simple risk based on liquidity
                                    if liquidity_usd >= 100000:
                                        risk_level = "low"
                                    elif liquidity_usd >= 50000:
                                        risk_level = "medium"
                                    else:
                                        risk_level = "high"

                                    # Opportunity score (0-10)
                                    try:
                                        vol_24h = float(volume_data.get("h24", 0))
                                    except (TypeError, ValueError):
                                        vol_24h = 0.0

                                    score = min(
                                        10.0,
                                        (liquidity_usd / 50000.0) * 5.0
                                        + (vol_24h / max(liquidity_usd, 1.0)) * 2.0,
                                    )

                                    opp: Dict[str, Any] = {
                                        "id": f"opp_{(pair.get('pairAddress') or '')[:8]}",
                                        "symbol": f"{base_token.get('symbol', 'UNKNOWN')}/"
                                        f"{quote_token.get('symbol', 'UNKNOWN')}",
                                        "chain": chain,
                                        "dex": pair.get("dexId", "unknown"),
                                        "price_usd": str(pair.get("priceUsd", 0) or 0),
                                        "liquidity_usd": str(liquidity_usd),
                                        "volume_24h_usd": str(volume_data.get("h24", 0) or 0),
                                        "score": score,
                                        "risk_level": risk_level,
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                        "pair_address": pair.get("pairAddress", "") or "",
                                        "price_change_24h": price_change.get("h24", 0) or 0,
                                    }
                                    opportunities.append(opp)

                except Exception as chain_err:  # noqa: BLE001
                    logger.error("Error fetching %s pairs: %s", chain, chain_err)
                    continue

            logger.info(
                "DexScreener: Found %d opportunities across all chains",
                len(opportunities),
            )

        except Exception as e:  # noqa: BLE001
            logger.error("DexScreener main error: %s", e)

        # 2) If we have less than 20 opportunities, fetch trending tokens
        if len(opportunities) < 20:
            try:
                logger.info("Fetching DexScreener trending tokens...")
                async with session.get(
                    "https://api.dexscreener.com/latest/dex/tokens/trending",
                    timeout=15,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        trending = data.get("data", []) or []

                        for item in trending[:10]:
                            pairs = item.get("pairs", []) or []
                            for pair in pairs[:2]:  # Top 2 pairs per trending token
                                liquidity_data = pair.get("liquidity", {}) or {}
                                liquidity_usd = float(liquidity_data.get("usd", 0) or 0)

                                if liquidity_usd >= 10000:
                                    base_token = pair.get("baseToken", {}) or {}
                                    quote_token = pair.get("quoteToken", {}) or {}

                                    opp2: Dict[str, Any] = {
                                        "id": f"opp_trend_{(pair.get('pairAddress') or '')[:8]}",
                                        "symbol": f"{base_token.get('symbol', 'UNKNOWN')}/"
                                        f"{quote_token.get('symbol', 'UNKNOWN')}",
                                        "chain": pair.get("chainId", "unknown"),
                                        "dex": pair.get("dexId", "unknown"),
                                        "price_usd": str(pair.get("priceUsd", 0) or 0),
                                        "liquidity_usd": str(liquidity_usd),
                                        "volume_24h_usd": str(
                                            (pair.get("volume", {}) or {}).get("h24", 0)
                                        ),
                                        "score": min(10.0, float(random.uniform(5, 9))),
                                        "risk_level": "medium",
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                        "pair_address": pair.get("pairAddress", "") or "",
                                    }
                                    opportunities.append(opp2)

            except Exception as e:  # noqa: BLE001
                logger.error("Trending tokens error: %s", e)

    # Remove duplicates based on pair address
    seen: set[str] = set()
    unique_opportunities: List[Dict[str, Any]] = []
    for opp in opportunities:
        key = str(opp.get("pair_address") or opp.get("id") or "")
        if key and key not in seen:
            seen.add(key)
            unique_opportunities.append(opp)

    logger.info("Total unique real opportunities: %d", len(unique_opportunities))

    if not unique_opportunities:
        logger.warning("No real data available, returning empty set")
        return []

    # Return up to 100 opportunities
    return unique_opportunities[:100]


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
