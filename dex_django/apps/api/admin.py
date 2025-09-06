# APP: backend
# FILE: backend/app/api/admin.py
from __future__ import annotations

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.copy_trading.copy_trading_coordinator import copy_trading_coordinator

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
logger = logging.getLogger("api.admin")


class SystemStatusResponse(BaseModel):
    """Response model for system status."""
    status: str
    message: str
    details: dict = {}


@router.get("/status", summary="Get system status")
async def get_system_status() -> Dict[str, Any]:
    """Get current system status and statistics."""
    
    try:
        # Get copy trading coordinator status
        coordinator_status = await copy_trading_coordinator.get_status()
        
        return {
            "status": "success",
            "system_status": {
                "copy_trading": coordinator_status,
                "database": "connected"
            },
            "message": "System operational"
        }
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(500, f"Status check failed: {str(e)}") from e


@router.post("/copy-trading/start", summary="Start copy trading system")
async def start_copy_trading() -> Dict[str, Any]:
    """Start the copy trading coordinator and wallet monitoring."""
    
    try:
        result = await copy_trading_coordinator.start()
        
        return {
            "status": "success",
            "message": "Copy trading system started",
            "details": result,
            "monitoring": {
                "active": True,
                "tracked_wallets": result.get("tracked_wallets", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to start copy trading system: {e}")
        raise HTTPException(500, f"Start failed: {str(e)}") from e


@router.post("/copy-trading/stop", summary="Stop copy trading system")
async def stop_copy_trading() -> Dict[str, Any]:
    """Stop the copy trading coordinator and wallet monitoring."""
    
    try:
        result = await copy_trading_coordinator.stop()
        
        return {
            "status": "success",
            "message": "Copy trading system stopped",
            "details": result
        }
        
    except Exception as e:
        logger.error(f"Failed to stop copy trading system: {e}")
        raise HTTPException(500, f"Stop failed: {str(e)}") from e


@router.post("/copy-trading/restart", summary="Restart copy trading system")
async def restart_copy_trading() -> Dict[str, Any]:
    """Restart the copy trading coordinator."""
    
    try:
        # Stop first
        await copy_trading_coordinator.stop()
        
        # Small delay
        import asyncio
        await asyncio.sleep(1)
        
        # Start again
        result = await copy_trading_coordinator.start()
        
        return {
            "status": "success",
            "message": "Copy trading system restarted",
            "details": result
        }
        
    except Exception as e:
        logger.error(f"Failed to restart copy trading system: {e}")
        raise HTTPException(500, f"Restart failed: {str(e)}") from e


@router.get("/copy-trading/stats", summary="Get copy trading statistics")
async def get_copy_trading_stats() -> Dict[str, Any]:
    """Get detailed copy trading statistics."""
    
    try:
        stats = await copy_trading_coordinator.get_statistics()
        
        return {
            "status": "success",
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get copy trading statistics: {e}")
        raise HTTPException(500, f"Statistics retrieval failed: {str(e)}") from e