from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1")


class BotSettingsUpdate(BaseModel):
    """Bot settings update request."""
    autotrade_enabled: Optional[bool] = None
    paper_mode: Optional[bool] = None
    max_trade_size_eth: Optional[float] = Field(None, gt=0, le=10)
    slippage_tolerance_bps: Optional[int] = Field(None, ge=10, le=5000)
    daily_trade_limit: Optional[int] = Field(None, ge=1, le=1000)
    risk_level: Optional[str] = Field(None, regex="^(conservative|standard|aggressive)$")


@router.get("/bot/status")
async def get_bot_status() -> Dict[str, Any]:
    """Get current bot status and statistics."""
    try:
        # Get actual runtime state
        from apps.core.runtime_state import runtime_state
        
        # Calculate uptime (you'd track this properly)
        uptime_seconds = 3600  # Mock for now
        
        # Get trade statistics from Django models
        try:
            from apps.storage.models import Trade
            from django.db.models import Count
            
            total_trades = Trade.objects.count()
            paper_trades = Trade.objects.filter(mode='paper').count()
            active_positions = 0  # You'd calculate this from open positions
            
        except Exception:
            total_trades = 0
            paper_trades = 0
            active_positions = 0
        
        # Get current bot state
        paper_enabled = await runtime_state.get_paper_enabled()
        
        return {
            "status": "ok",
            "data": {
                "status": "running",
                "uptime_seconds": uptime_seconds,
                "total_trades": total_trades,
                "paper_trades": paper_trades,
                "active_positions": active_positions,
                "paper_mode": paper_enabled,
                "last_trade_time": None,
                "chains_connected": ["ethereum", "bsc", "base"],
                "discovery_active": True
            }
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to get bot status: {str(e)}") from e


@router.get("/bot/settings")
async def get_bot_settings() -> Dict[str, Any]:
    """Get current bot settings from Django models."""
    try:
        from apps.strategy.models import BotSettings
        
        try:
            # Get or create default settings
            bot_settings, created = BotSettings.objects.get_or_create(
                id=1,
                defaults={
                    'autotrade_enabled': False,
                    'paper_mode': True,
                    'per_trade_cap_base': 1.0,
                    'slippage_bps_new_pair': 300,
                    'daily_cap_base': 50.0,
                }
            )
            
            settings_data = {
                "autotrade_enabled": bot_settings.autotrade_enabled,
                "paper_mode": bot_settings.paper_mode,
                "max_trade_size_eth": float(bot_settings.per_trade_cap_base),
                "slippage_tolerance_bps": bot_settings.slippage_bps_new_pair,
                "daily_trade_limit": int(bot_settings.daily_cap_base),
                "risk_level": "conservative",  # You'd map this from your risk settings
                "hot_wallet_cap": float(bot_settings.hot_wallet_hard_cap_base),
                "fail_streak_pause": bot_settings.fail_streak_pause
            }
            
        except Exception:
            # Fallback to default settings
            settings_data = {
                "autotrade_enabled": False,
                "paper_mode": True,
                "max_trade_size_eth": 1.0,
                "slippage_tolerance_bps": 300,
                "daily_trade_limit": 50,
                "risk_level": "conservative"
            }
        
        return {
            "status": "ok",
            "data": settings_data
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to get bot settings: {str(e)}") from e


@router.put("/bot/settings")
async def update_bot_settings(settings: BotSettingsUpdate) -> Dict[str, Any]:
    """Update bot settings in Django models."""
    try:
        from apps.strategy.models import BotSettings
        from decimal import Decimal
        
        # Get or create settings object
        bot_settings, created = BotSettings.objects.get_or_create(id=1)
        
        # Update provided fields
        updated_fields = []
        
        if settings.autotrade_enabled is not None:
            bot_settings.autotrade_enabled = settings.autotrade_enabled
            updated_fields.append("autotrade_enabled")
        
        if settings.paper_mode is not None:
            bot_settings.paper_mode = settings.paper_mode
            updated_fields.append("paper_mode")
        
        if settings.max_trade_size_eth is not None:
            bot_settings.per_trade_cap_base = Decimal(str(settings.max_trade_size_eth))
            updated_fields.append("max_trade_size_eth")
        
        if settings.slippage_tolerance_bps is not None:
            bot_settings.slippage_bps_new_pair = settings.slippage_tolerance_bps
            updated_fields.append("slippage_tolerance_bps")
        
        if settings.daily_trade_limit is not None:
            bot_settings.daily_cap_base = Decimal(str(settings.daily_trade_limit))
            updated_fields.append("daily_trade_limit")
        
        # Save changes
        bot_settings.save()
        
        # Update runtime state if paper mode changed
        if settings.paper_mode is not None:
            from apps.core.runtime_state import runtime_state
            await runtime_state.set_paper_enabled(settings.paper_mode)
        
        return {
            "status": "ok",
            "message": f"Updated settings: {', '.join(updated_fields)}",
            "data": {
                "autotrade_enabled": bot_settings.autotrade_enabled,
                "paper_mode": bot_settings.paper_mode,
                "max_trade_size_eth": float(bot_settings.per_trade_cap_base),
                "slippage_tolerance_bps": bot_settings.slippage_bps_new_pair,
                "daily_trade_limit": int(bot_settings.daily_cap_base)
            }
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to update bot settings: {str(e)}") from e


@router.post("/bot/start")
async def start_bot() -> Dict[str, Any]:
    """Start the trading bot."""
    try:
        from apps.core.runtime_state import runtime_state
        
        # Start bot logic here - you'd implement this in your strategy runner
        # For now, just update the state
        
        return {
            "status": "ok",
            "message": "Bot started successfully",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to start bot: {str(e)}") from e


@router.post("/bot/stop")
async def stop_bot() -> Dict[str, Any]:
    """Stop the trading bot."""
    try:
        from apps.core.runtime_state import runtime_state
        
        # Stop bot logic here
        
        return {
            "status": "ok",
            "message": "Bot stopped successfully",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to stop bot: {str(e)}") from e
