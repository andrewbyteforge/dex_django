# APP: dex_django
# FILE: dex_django/apps/strategy/copy_trading_complete.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from apps.discovery.wallet_tracker import wallet_tracker
from apps.copy_trading.copy_trading_strategy import copy_trading_strategy
from apps.intelligence.copy_trading_engine import copy_trading_engine
from apps.core.runtime_state import runtime_state

router = APIRouter(prefix="/api/v1/strategy", tags=["strategy"])
logger = logging.getLogger("strategy.copy_trading_complete")


class StrategyConfig(BaseModel):
    """Configuration for copy trading strategy."""
    max_position_usd: float = Field(gt=0, le=100000)
    max_daily_trades: int = Field(ge=1, le=100)
    min_trader_success_rate: float = Field(ge=0, le=100)
    risk_tolerance: str = Field(pattern="^(low|medium|high)$")
    allowed_chains: List[str]
    enable_auto_copy: bool = False


class StrategyMetrics(BaseModel):
    """Metrics for strategy performance."""
    total_copies: int
    successful_copies: int
    total_pnl_usd: float
    win_rate: float
    avg_copy_size_usd: float
    best_trader: Optional[str]
    worst_trader: Optional[str]


@router.get("/config", summary="Get current strategy configuration")
async def get_strategy_config() -> Dict[str, Any]:
    """Get the current copy trading strategy configuration."""
    
    try:
        config = await copy_trading_strategy.get_configuration()
        
        return {
            "status": "ok",
            "config": config
        }
    except Exception as e:
        logger.error(f"Failed to get strategy config: {e}")
        raise HTTPException(500, f"Failed to get configuration: {str(e)}") from e


@router.put("/config", summary="Update strategy configuration")
async def update_strategy_config(config: StrategyConfig) -> Dict[str, Any]:
    """Update the copy trading strategy configuration."""
    
    try:
        # Update strategy configuration
        result = await copy_trading_strategy.update_configuration(
            max_position_usd=Decimal(str(config.max_position_usd)),
            max_daily_trades=config.max_daily_trades,
            min_trader_success_rate=config.min_trader_success_rate,
            risk_tolerance=config.risk_tolerance,
            allowed_chains=config.allowed_chains,
            enable_auto_copy=config.enable_auto_copy
        )
        
        # Emit configuration change to thought log
        await runtime_state.emit_thought_log({
            "event": "strategy_config_updated",
            "config": {
                "max_position_usd": config.max_position_usd,
                "risk_tolerance": config.risk_tolerance,
                "auto_copy": config.enable_auto_copy
            }
        })
        
        return {
            "status": "ok",
            "message": "Strategy configuration updated",
            "config": result
        }
    except Exception as e:
        logger.error(f"Failed to update strategy config: {e}")
        raise HTTPException(500, f"Failed to update configuration: {str(e)}") from e


@router.get("/metrics", summary="Get strategy performance metrics")
async def get_strategy_metrics(
    days: int = Query(30, ge=1, le=365)
) -> Dict[str, Any]:
    """Get performance metrics for the copy trading strategy."""
    
    try:
        metrics = await copy_trading_strategy.get_performance_metrics(days=days)
        
        return {
            "status": "ok",
            "period_days": days,
            "metrics": metrics
        }
    except Exception as e:
        logger.error(f"Failed to get strategy metrics: {e}")
        raise HTTPException(500, f"Failed to get metrics: {str(e)}") from e


@router.post("/analyze-trader", summary="Analyze a trader for copy trading")
async def analyze_trader(
    wallet_address: str = Body(...),
    chain: str = Body(...)
) -> Dict[str, Any]:
    """Analyze a trader's profile and suitability for copy trading."""
    
    try:
        # Validate address format
        if not wallet_address.startswith("0x") or len(wallet_address) != 42:
            raise HTTPException(400, "Invalid wallet address format")
        
        # Analyze trader
        profile = await copy_trading_engine.analyze_trader(
            wallet_address=wallet_address.lower(),
            chain=chain
        )
        
        # Get suitability assessment
        suitability = await copy_trading_strategy.assess_trader_suitability(profile)
        
        return {
            "status": "ok",
            "trader": {
                "wallet_address": profile.wallet_address,
                "chain": profile.chain,
                "success_rate": profile.success_rate,
                "total_profit_usd": float(profile.total_profit_usd),
                "trades_count": profile.trades_count,
                "risk_level": profile.risk_level,
                "verified": profile.verified
            },
            "suitability": suitability
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze trader: {e}")
        raise HTTPException(500, f"Failed to analyze trader: {str(e)}") from e


@router.post("/backtest", summary="Backtest strategy on historical data")
async def backtest_strategy(
    trader_address: str = Body(...),
    days: int = Body(30, ge=1, le=365),
    initial_capital: float = Body(10000, gt=0)
) -> Dict[str, Any]:
    """Backtest the copy trading strategy on historical data."""
    
    try:
        # This would run backtesting on historical data
        # For now, return a message that backtesting requires historical data
        
        return {
            "status": "ok",
            "message": "Backtesting requires historical blockchain data",
            "requirements": [
                "Historical transaction data for trader",
                "Historical price data for traded tokens",
                "Historical gas prices",
                "DEX liquidity snapshots"
            ],
            "trader_address": trader_address,
            "period_days": days,
            "initial_capital": initial_capital
        }
        
    except Exception as e:
        logger.error(f"Failed to run backtest: {e}")
        raise HTTPException(500, f"Failed to run backtest: {str(e)}") from e


@router.get("/recommendations", summary="Get trading recommendations")
async def get_recommendations() -> Dict[str, Any]:
    """Get current trading recommendations based on strategy analysis."""
    
    try:
        # Get active traders
        traders = await wallet_tracker.get_followed_traders()
        active_traders = [t for t in traders if t.get("status") == "active"]
        
        if not active_traders:
            return {
                "status": "ok",
                "recommendations": [],
                "message": "No active traders to analyze"
            }
        
        recommendations = []
        
        # Analyze each active trader
        for trader in active_traders:
            # Get trader profile from engine
            profile = copy_trading_engine.tracked_traders.get(trader["wallet_address"])
            
            if profile and profile.verified:
                rec = {
                    "trader_address": trader["wallet_address"],
                    "trader_name": trader.get("trader_name", "Unknown"),
                    "action": "monitor",
                    "confidence": profile.success_rate / 100,
                    "reason": f"Success rate: {profile.success_rate}%"
                }
                recommendations.append(rec)
        
        return {
            "status": "ok",
            "recommendations": recommendations,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(500, f"Failed to get recommendations: {str(e)}") from e


@router.post("/risk-assessment", summary="Assess risk for a potential trade")
async def assess_trade_risk(
    token_address: str = Body(...),
    amount_usd: float = Body(..., gt=0),
    chain: str = Body(...)
) -> Dict[str, Any]:
    """Assess the risk of a potential copy trade."""
    
    try:
        # Perform risk assessment
        risk_assessment = await copy_trading_strategy.assess_trade_risk(
            token_address=token_address,
            amount_usd=Decimal(str(amount_usd)),
            chain=chain
        )
        
        return {
            "status": "ok",
            "risk_assessment": risk_assessment
        }
        
    except Exception as e:
        logger.error(f"Failed to assess trade risk: {e}")
        raise HTTPException(500, f"Failed to assess risk: {str(e)}") from e


# Background task for strategy optimization
async def optimize_strategy_parameters() -> None:
    """Background task to optimize strategy parameters based on performance."""
    
    try:
        logger.info("Running strategy optimization...")
        
        # Get recent performance metrics
        metrics = await copy_trading_strategy.get_performance_metrics(days=7)
        
        # Analyze and adjust parameters
        if metrics["win_rate"] < 40:
            # Tighten criteria if win rate is low
            await copy_trading_strategy.update_configuration(
                min_trader_success_rate=70
            )
            logger.info("Increased minimum trader success rate due to low win rate")
        
        # Log optimization complete
        await runtime_state.emit_thought_log({
            "event": "strategy_optimization",
            "metrics": metrics,
            "adjustments_made": metrics["win_rate"] < 40
        })
        
    except Exception as e:
        logger.error(f"Strategy optimization failed: {e}")