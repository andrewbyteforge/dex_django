# APP: backend/app/api
# FILE: backend/app/api/copy_trading_integrated.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field, validator

from dex_django.apps.discovery.wallet_monitor import wallet_monitor
from dex_django.apps.strategy.copy_trading_strategy import copy_trading_strategy
from dex_django.apps.core.runtime_state import runtime_state

logger = logging.getLogger("api.copy_trading_integrated")

# Router
router = APIRouter(prefix="/api/v1/copy", tags=["copy-trading-integrated"])

# Global service instance (will be initialized in main.py)
_copy_trading_service = None


def initialize_copy_trading_api(copy_trading_service) -> None:
    """Initialize the API with the copy trading service."""
    global _copy_trading_service
    _copy_trading_service = copy_trading_service
    logger.info("Copy trading integrated API initialized")


# Request Models
class AddTraderRequest(BaseModel):
    """Request to add a new followed trader."""
    
    wallet_address: str = Field(..., min_length=42, max_length=42)
    trader_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    chain: str = Field("ethereum")
    
    # Copy settings
    copy_mode: str = Field("percentage", pattern="^(percentage|fixed_amount|proportional)$")
    copy_percentage: Decimal = Field(Decimal("5.0"), ge=0.1, le=50.0)
    fixed_amount_usd: Optional[Decimal] = Field(None, ge=10.0, le=10000.0)
    
    # Risk controls
    max_position_usd: Decimal = Field(Decimal("1000.0"), ge=50.0, le=50000.0)
    min_trade_value_usd: Decimal = Field(Decimal("100.0"), ge=10.0)
    max_slippage_bps: int = Field(300, ge=50, le=1000)
    
    # Filters
    allowed_chains: List[str] = Field(default_factory=lambda: ["ethereum", "bsc", "base"])
    copy_buy_only: bool = False
    copy_sell_only: bool = False
    
    @validator('wallet_address')
    def validate_wallet_address(cls, v):
        """Validate wallet address format."""
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError("Invalid wallet address format")
        return v.lower()
    
    @validator('chain')
    def validate_chain(cls, v):
        """Validate chain."""
        valid_chains = {"ethereum", "bsc", "base", "polygon", "arbitrum"}
        if v not in valid_chains:
            raise ValueError(f"Invalid chain: {v}. Must be one of: {valid_chains}")
        return v.lower()


class SystemControlRequest(BaseModel):
    """Request to control copy trading system."""
    enabled: bool
    paper_mode: Optional[bool] = None


class UpdateTraderRequest(BaseModel):
    """Request to update trader settings."""
    trader_name: Optional[str] = None
    description: Optional[str] = None
    copy_mode: Optional[str] = None
    copy_percentage: Optional[Decimal] = None
    fixed_amount_usd: Optional[Decimal] = None
    max_position_usd: Optional[Decimal] = None
    min_trade_value_usd: Optional[Decimal] = None
    max_slippage_bps: Optional[int] = None
    allowed_chains: Optional[List[str]] = None
    copy_buy_only: Optional[bool] = None
    copy_sell_only: Optional[bool] = None
    is_active: Optional[bool] = None


# API Endpoints
@router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """Get comprehensive copy trading system status."""
    if not _copy_trading_service:
        raise HTTPException(500, "Copy trading service not initialized")
    
    try:
        status = await _copy_trading_service.get_service_status()
        
        return {
            "status": "ok",
            "system_status": {
                "is_enabled": status.is_enabled,
                "monitoring_active": status.monitoring_active,
                "followed_traders_count": status.followed_traders_count,
                "active_copies_today": status.trades_today,
                "total_copies": status.total_trades,
                "win_rate_pct": status.success_rate,
                "total_pnl_usd": str(status.total_pnl_usd),
                "paper_mode": status.paper_mode
            },
            "infrastructure": {
                "copy_trading_service": {
                    "initialized": True,
                    "is_running": status.is_enabled,
                    "active_monitoring_count": status.active_monitoring_count
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(500, f"Failed to get system status: {str(e)}")


@router.post("/system/control")
async def control_system(request: SystemControlRequest) -> Dict[str, Any]:
    """Enable/disable the copy trading system."""
    if not _copy_trading_service:
        raise HTTPException(500, "Copy trading service not initialized")
    
    try:
        if request.enabled:
            result = await _copy_trading_service.start_service()
        else:
            result = await _copy_trading_service.stop_service()
        
        # Set paper mode if specified
        if request.paper_mode is not None:
            await _copy_trading_service.set_paper_mode(request.paper_mode)
        
        if not result["success"]:
            raise HTTPException(500, result["message"])
        
        return {
            "status": "ok",
            "message": result["message"],
            "enabled": request.enabled,
            "paper_mode": _copy_trading_service.is_paper_mode(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error controlling system: {e}")
        raise HTTPException(500, f"Failed to control system: {str(e)}")


@router.get("/traders")
async def get_followed_traders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, regex="^(active|paused|all)$")
) -> Dict[str, Any]:
    """Get list of followed traders."""
    if not _copy_trading_service:
        raise HTTPException(500, "Copy trading service not initialized")
    
    try:
        traders = await _copy_trading_service.get_followed_traders()
        
        # Filter by status if specified
        if status and status != "all":
            if status == "active":
                traders = [t for t in traders if t.is_active]
            elif status == "paused":
                traders = [t for t in traders if not t.is_active]
        
        # Apply pagination
        total = len(traders)
        traders_page = traders[skip:skip + limit]
        
        # Convert to dict format for response
        traders_data = [trader.dict() for trader in traders_page]
        
        return {
            "status": "ok",
            "data": {
                "traders": traders_data,
                "pagination": {
                    "total": total,
                    "skip": skip,
                    "limit": limit,
                    "has_more": skip + limit < total
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting traders: {e}")
        raise HTTPException(500, f"Failed to get traders: {str(e)}")


@router.post("/traders")
async def add_followed_trader(
    request: AddTraderRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Add a new trader to follow."""
    if not _copy_trading_service:
        raise HTTPException(500, "Copy trading service not initialized")
    
    try:
        # Prepare copy settings from request
        copy_settings = {
            "copy_mode": request.copy_mode,
            "copy_percentage": float(request.copy_percentage),
            "fixed_amount_usd": float(request.fixed_amount_usd) if request.fixed_amount_usd else None,
            "max_position_usd": float(request.max_position_usd),
            "min_trade_value_usd": float(request.min_trade_value_usd),
            "max_slippage_bps": request.max_slippage_bps,
            "allowed_chains": request.allowed_chains,
            "copy_buy_only": request.copy_buy_only,
            "copy_sell_only": request.copy_sell_only
        }
        
        # Add trader through service
        result = await _copy_trading_service.add_trader(
            wallet_address=request.wallet_address,
            trader_name=request.trader_name,
            description=request.description,
            chain=request.chain,
            copy_settings=copy_settings
        )
        
        if not result["success"]:
            if "already being followed" in result["message"]:
                raise HTTPException(400, result["message"])
            else:
                raise HTTPException(500, result["message"])
        
        # Add background task for trader analysis
        background_tasks.add_task(
            analyze_trader_background,
            request.wallet_address,
            request.chain
        )
        
        return {
            "status": "ok",
            "message": result["message"],
            "trader": result["trader"],
            "monitoring_active": result.get("monitoring_active", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding trader {request.wallet_address}: {e}")
        raise HTTPException(500, f"Failed to add trader: {str(e)}")


@router.delete("/traders/{trader_key}")
async def remove_followed_trader(trader_key: str) -> Dict[str, Any]:
    """Remove a followed trader."""
    if not _copy_trading_service:
        raise HTTPException(500, "Copy trading service not initialized")
    
    try:
        result = await _copy_trading_service.remove_trader(trader_key)
        
        if not result["success"]:
            if "not found" in result["message"]:
                raise HTTPException(404, result["message"])
            else:
                raise HTTPException(500, result["message"])
        
        return {
            "status": "ok",
            "message": result["message"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing trader {trader_key}: {e}")
        raise HTTPException(500, f"Failed to remove trader: {str(e)}")


@router.get("/traders/{trader_key}")
async def get_trader_details(trader_key: str) -> Dict[str, Any]:
    """Get detailed information about a specific trader."""
    if not _copy_trading_service:
        raise HTTPException(500, "Copy trading service not initialized")
    
    try:
        traders = await _copy_trading_service.get_followed_traders()
        
        # Find trader by key
        trader = None
        for t in traders:
            if f"{t.chain}:{t.wallet_address}" == trader_key:
                trader = t
                break
        
        if not trader:
            raise HTTPException(404, f"Trader {trader_key} not found")
        
        return {
            "status": "ok",
            "trader": trader.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trader details {trader_key}: {e}")
        raise HTTPException(500, f"Failed to get trader details: {str(e)}")


@router.post("/traders/{trader_key}")
async def update_trader_settings(
    trader_key: str,
    request: UpdateTraderRequest
) -> Dict[str, Any]:
    """Update trader settings."""
    if not _copy_trading_service:
        raise HTTPException(500, "Copy trading service not initialized")
    
    try:
        # This would need implementation in the service
        # For now, return not implemented
        raise HTTPException(501, "Update trader settings not yet implemented")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating trader {trader_key}: {e}")
        raise HTTPException(500, f"Failed to update trader: {str(e)}")


@router.get("/trades")
async def get_copy_trades(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    trader_address: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get copy trading history."""
    if not _copy_trading_service:
        raise HTTPException(500, "Copy trading service not initialized")
    
    try:
        # For now, return empty data - would integrate with database
        return {
            "status": "ok",
            "data": {
                "trades": [],
                "pagination": {
                    "total": 0,
                    "skip": skip,
                    "limit": limit,
                    "has_more": False
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting copy trades: {e}")
        raise HTTPException(500, f"Failed to get copy trades: {str(e)}")


@router.post("/paper/toggle")
async def toggle_paper_mode(enabled: bool = Query(...)) -> Dict[str, Any]:
    """Toggle paper trading mode."""
    if not _copy_trading_service:
        raise HTTPException(500, "Copy trading service not initialized")
    
    try:
        await _copy_trading_service.set_paper_mode(enabled)
        
        return {
            "status": "ok",
            "message": f"Paper mode {'enabled' if enabled else 'disabled'}",
            "paper_mode": enabled,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error toggling paper mode: {e}")
        raise HTTPException(500, f"Failed to toggle paper mode: {str(e)}")


# Background Tasks
async def analyze_trader_background(trader_address: str, chain: str) -> None:
    """Background task to analyze a newly added trader."""
    try:
        logger.info(f"Starting background analysis for trader {trader_address[:8]}... on {chain}")
        
        # Placeholder for trader analysis logic
        # Would integrate with:
        # - Historical transaction analysis  
        # - Performance metrics calculation
        # - Risk assessment
        # - Pattern recognition
        
        # Simulate some work
        import asyncio
        await asyncio.sleep(2.0)
        
        logger.info(f"Completed background analysis for trader {trader_address[:8]}...")
        
    except Exception as e:
        logger.error(f"Background analysis failed for trader {trader_address}: {e}")


# Health check endpoint
@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Copy trading API health check."""
    return {
        "status": "ok",
        "service_initialized": _copy_trading_service is not None,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }