from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/health", summary="Basic health check")
async def health_check() -> Dict[str, Any]:
    """Basic liveness check for the DEX Sniper Pro service."""
    return {
        "status": "ok",
        "service": "DEX Sniper Pro",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }


@router.get("/health/ready", summary="Readiness check with dependencies")
async def readiness_check() -> Dict[str, Any]:
    """
    Comprehensive readiness check including blockchain providers and DEX routers.
    Returns detailed status of all critical dependencies.
    """
    try:
        checks = {
            "status": "ok",
            "service": "DEX Sniper Pro",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dependencies": {}
        }
        
        # Try to import and check Web3 providers
        try:
            from apps.chains.providers import web3_manager
            provider_status = {}
            for chain in ["ethereum", "bsc", "base"]:
                try:
                    provider = await web3_manager.get_provider(chain)
                    if provider:
                        # Quick block number check with timeout
                        try:
                            block_number = await asyncio.wait_for(
                                provider.eth.get_block_number(), 
                                timeout=3.0
                            )
                            provider_status[chain] = {
                                "status": "ok",
                                "block_number": block_number
                            }
                        except asyncio.TimeoutError:
                            provider_status[chain] = {"status": "timeout"}
                    else:
                        provider_status[chain] = {"status": "unavailable"}
                except Exception as e:
                    provider_status[chain] = {
                        "status": "error",
                        "error": str(e)[:100]
                    }
            
            checks["dependencies"]["web3_providers"] = provider_status
        except ImportError as e:
            checks["dependencies"]["web3_providers"] = {
                "status": "error",
                "error": f"Import failed: {e}"
            }
        
        # Try to check DEX routers
        try:
            from apps.dex.routers import dex_manager
            router_status = {}
            for chain in ["ethereum", "bsc", "base"]:
                chain_routers = {}
                if chain == "bsc":
                    router_obj = await dex_manager.get_router(chain, "pancakeswap")
                    chain_routers["pancakeswap"] = "ok" if router_obj else "unavailable"
                elif chain == "base":
                    router_obj = await dex_manager.get_router(chain, "uniswap")
                    chain_routers["uniswap"] = "ok" if router_obj else "unavailable"
                elif chain == "ethereum":
                    router_obj = await dex_manager.get_router(chain, "uniswap")
                    chain_routers["uniswap"] = "ok" if router_obj else "unavailable"
                
                router_status[chain] = chain_routers
            
            checks["dependencies"]["dex_routers"] = router_status
        except ImportError as e:
            checks["dependencies"]["dex_routers"] = {
                "status": "error", 
                "error": f"Import failed: {e}"
            }
        
        # Check Django database connection
        try:
            from apps.storage.models import Provider
            provider_count = Provider.objects.count()
            checks["dependencies"]["database"] = {
                "status": "ok",
                "provider_count": provider_count
            }
        except Exception as e:
            checks["dependencies"]["database"] = {
                "status": "error",
                "error": str(e)[:100]
            }
        
        return checks
        
    except Exception as e:
        raise HTTPException(500, f"Health check failed: {str(e)}") from e