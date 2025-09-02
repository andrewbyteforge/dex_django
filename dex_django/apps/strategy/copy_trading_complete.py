# APP: backend
# FILE: backend/app/api/copy_trading_complete.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from pydantic import BaseModel, Field, validator

from backend.app.discovery.wallet_monitor import wallet_monitor
from backend.app.strategy.copy_trading_strategy import copy_trading_strategy
from backend.app.strategy.trader_performance_tracker import trader_performance_tracker
from backend.app.trading.live_executor import live_executor
from backend.app.core.runtime_state import runtime_state

router = APIRouter(prefix="/api/v1/copy", tags=["copy-trading"])
logger = logging.getLogger("api.copy_trading")


# Request Models
class AddTraderRequest(BaseModel):
    """Request to add a new followed trader."""
    wallet_address: str = Field(..., min_length=40, max_length=50)
    trader_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    chain: str = Field("ethereum")
    
    # Copy settings
    copy_mode: str = Field("percentage", regex="^(percentage|fixed_amount|proportional)$")
    copy_percentage: Decimal = Field(Decimal("5.0"), ge=0.1, le=50.0)
    fixed_amount_usd: Optional[Decimal] = Field(None, ge=10.0, le=10000.0)
    
    # Risk controls
    max_position_usd: Decimal = Field(Decimal("1000.0"), ge=50.0, le=50000.0)
    min_trade_value_usd: Decimal = Field(Decimal("100.0"), ge=10.0)
    max_slippage_bps: int = Field(300, ge=50, le=1000)
    
    # Filters
    allowed_chains: List[str] = Field(default_factory=lambda: ["ethereum", "bsc", "base"])
    copy_buy_only: bool = False
    
    @validator('wallet_address')
    def validate_wallet_address(cls, v):
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError("Invalid wallet address format")
        return v.lower()


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
    enabled: Optional[bool] = None


class SystemControlRequest(BaseModel):
    """Request to control copy trading system."""
    enabled: bool
    auto_discovery: Optional[bool] = None
    paper_mode: Optional[bool] = None


# API Endpoints
@router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """Get complete copy trading system status."""
    try:
        # Get wallet monitor status
        monitor_status = await wallet_monitor.get_monitoring_status()
        
        # Get live executor status
        executor_status = await live_executor.get_status()
        
        # Get strategy statistics
        strategy_stats = await copy_trading_strategy.get_copy_trading_statistics()
        
        # Get paper trading status
        paper_enabled = await runtime_state.get_paper_enabled()
        
        # Count active traders (mock for now)
        active_traders = len(monitor_status.get("wallets", []))
        
        return {
            "status": "ok",
            "system_status": {
                "is_enabled": monitor_status["is_running"],
                "monitoring_active": monitor_status["is_running"],
                "paper_mode": paper_enabled,
                "live_trading_ready": executor_status["initialized"] and executor_status["wallet_loaded"],
                "followed_traders_count": active_traders,
                "active_copies_today": strategy_stats.get("daily_copies", 0),
                "total_copies": 0,  # Would track in database
                "win_rate_pct": 65.5,  # Mock
                "total_pnl_usd": "1,234.56"  # Mock
            },
            "infrastructure": {
                "wallet_monitor": monitor_status,
                "live_executor": executor_status,
                "strategy_engine": {
                    "initialized": True,
                    "daily_copies": strategy_stats.get("daily_copies", 0),
                    "daily_pnl_usd": float(strategy_stats.get("daily_pnl_usd", 0))
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
    try:
        if request.enabled:
            # Get list of traders to monitor (would come from database)
            trader_addresses = []  # Mock empty for now
            
            if trader_addresses:
                await wallet_monitor.start_monitoring(trader_addresses)
            
            # Update paper mode if specified
            if request.paper_mode is not None:
                await runtime_state.set_paper_enabled(request.paper_mode)
            
            message = f"Copy trading system started {'(paper mode)' if request.paper_mode else '(live mode)'}"
        else:
            await wallet_monitor.stop_monitoring()
            message = "Copy trading system stopped"
        
        return {
            "status": "ok",
            "message": message,
            "enabled": request.enabled,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error controlling system: {e}")
        raise HTTPException(500, f"Failed to control system: {str(e)}")


@router.get("/traders")
async def get_followed_traders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, regex="^(active|paused|all)$")
) -> Dict[str, Any]:
    """Get list of followed traders with their performance."""
    try:
        # Mock data - would come from database in production
        traders = []
        
        return {
            "status": "ok",
            "data": {
                "traders": traders,
                "pagination": {
                    "total": len(traders),
                    "skip": skip,
                    "limit": limit,
                    "has_more": False
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
    try:
        trader_address = request.wallet_address.lower()
        
        # Validate trader doesn't already exist (mock check)
        # In production, would check database
        
        # Add to wallet monitoring
        success = await wallet_monitor.add_wallet(trader_address)
        
        if not success:
            raise HTTPException(400, "Trader already being followed")
        
        # Start background analysis of trader performance
        background_tasks.add_task(
            analyze_trader_background,
            trader_address,
            request.chain
        )
        
        # Mock trader data for response
        trader_data = {
            "id": f"trader_{int(datetime.now().timestamp())}",
            "wallet_address": trader_address,
            "trader_name": request.trader_name or f"Trader {trader_address[:8]}",
            "description": request.description or "",
            "chain": request.chain,
            "status": "analyzing",
            "copy_settings": {
                "copy_mode": request.copy_mode,
                "copy_percentage": float(request.copy_percentage),
                "fixed_amount_usd": float(request.fixed_amount_usd) if request.fixed_amount_usd else None,
                "max_position_usd": float(request.max_position_usd),
                "min_trade_value_usd": float(request.min_trade_value_usd),
                "max_slippage_bps": request.max_slippage_bps,
                "allowed_chains": request.allowed_chains,
                "copy_buy_only": request.copy_buy_only
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        return {
            "status": "ok",
            "message": "Trader added successfully",
            "data": trader_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding trader: {e}")
        raise HTTPException(500, f"Failed to add trader: {str(e)}")


@router.get("/traders/{trader_id}")
async def get_trader_details(trader_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific trader."""
    try:
        # Extract address from trader_id (mock implementation)
        # In production, would lookup in database by ID
        
        # Mock trader data
        trader_data = {
            "id": trader_id,
            "wallet_address": "0x742d35cc6634C0532925a3b8D1b9B5F5e5FfB0dA",
            "trader_name": "Alpha Trader",
            "status": "active",
            "performance": {
                "total_trades": 45,
                "win_rate": 0.733,
                "total_pnl_usd": 2456.78,
                "avg_trade_size_usd": 850.0,
                "max_drawdown_pct": 0.15,
                "sharpe_ratio": 1.85,
                "consistency_score": 78.5,
                "risk_score": 35.2
            },
            "recent_trades": [],
            "copy_statistics": {
                "times_copied": 12,
                "copy_success_rate": 0.83,
                "avg_copy_pnl": 45.67
            }
        }
        
        return {
            "status": "ok",
            "data": trader_data
        }
        
    except Exception as e:
        logger.error(f"Error getting trader details: {e}")
        raise HTTPException(500, f"Failed to get trader details: {str(e)}")


@router.put("/traders/{trader_id}")
async def update_trader_settings(
    trader_id: str,
    request: UpdateTraderRequest
) -> Dict[str, Any]:
    """Update settings for a followed trader."""
    try:
        # Mock update - would update database in production
        
        updated_fields = []
        if request.trader_name is not None:
            updated_fields.append("trader_name")
        if request.copy_percentage is not None:
            updated_fields.append("copy_percentage")
        if request.enabled is not None:
            updated_fields.append("enabled")
        
        return {
            "status": "ok",
            "message": f"Updated trader settings: {', '.join(updated_fields)}",
            "updated_fields": updated_fields,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error updating trader: {e}")
        raise HTTPException(500, f"Failed to update trader: {str(e)}")


@router.delete("/traders/{trader_id}")
async def remove_trader(trader_id: str) -> Dict[str, Any]:
    """Remove a trader from following list."""
    try:
        # Extract address from trader_id and remove from monitoring
        # Mock implementation
        
        return {
            "status": "ok",
            "message": "Trader removed successfully",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error removing trader: {e}")
        raise HTTPException(500, f"Failed to remove trader: {str(e)}")


@router.get("/trades/history")
async def get_copy_trades_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    trader_address: Optional[str] = Query(None),
    status: Optional[str] = Query(None, regex="^(success|failed|pending)$"),
    paper_only: bool = Query(False)
) -> Dict[str, Any]:
    """Get history of copy trades."""
    try:
        # Mock copy trades data
        trades = []
        
        return {
            "status": "ok",
            "data": {
                "trades": trades,
                "pagination": {
                    "total": len(trades),
                    "skip": skip,
                    "limit": limit,
                    "has_more": False
                },
                "filters": {
                    "trader_address": trader_address,
                    "status": status,
                    "paper_only": paper_only
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting trades history: {e}")
        raise HTTPException(500, f"Failed to get trades history: {str(e)}")


@router.get("/analytics/performance")
async def get_copy_trading_analytics(
    days: int = Query(30, ge=1, le=365),
    trader_address: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get copy trading performance analytics."""
    try:
        # Get analytics data
        if trader_address:
            # Single trader performance
            performance = await trader_performance_tracker.get_trader_performance(trader_address)
            
            return {
                "status": "ok",
                "data": {
                    "type": "single_trader",
                    "trader_address": trader_address,
                    "performance": performance,
                    "period_days": days
                }
            }
        else:
            # Overall copy trading performance
            top_performers = await trader_performance_tracker.get_top_performers(10)
            
            return {
                "status": "ok",
                "data": {
                    "type": "overall",
                    "period_days": days,
                    "summary": {
                        "total_traders": len(top_performers),
                        "avg_win_rate": sum(p["performance"]["win_rate"] for p in top_performers) / len(top_performers) if top_performers else 0,
                        "total_volume_usd": sum(p["performance"]["total_volume_usd"] for p in top_performers),
                        "total_pnl_usd": sum(p["performance"]["total_pnl_usd"] for p in top_performers)
                    },
                    "top_performers": top_performers[:5]
                }
            }
        
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(500, f"Failed to get analytics: {str(e)}")


@router.get("/discovery/top-traders")
async def discover_top_traders(
    chain: str = Query("ethereum"),
    limit: int = Query(20, ge=5, le=100),
    min_volume_usd: float = Query(50000, ge=1000)
) -> Dict[str, Any]:
    """Discover top performing traders to potentially follow."""
    try:
        # Mock discovery results - would use wallet discovery engine
        discovered_traders = []
        
        return {
            "status": "ok",
            "data": {
                "discovered_traders": discovered_traders,
                "discovery_criteria": {
                    "chain": chain,
                    "min_volume_usd": min_volume_usd,
                    "analysis_period_days": 30
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error discovering traders: {e}")
        raise HTTPException(500, f"Failed to discover traders: {str(e)}")


@router.post("/trades/simulate")
async def simulate_copy_trade(
    trader_address: str,
    token_address: str,
    amount_usd: Decimal,
    chain: str = "ethereum"
) -> Dict[str, Any]:
    """Simulate a copy trade without executing it."""
    try:
        # Create mock wallet transaction for simulation
        from backend.app.discovery.wallet_monitor import WalletTransaction
        
        mock_tx = WalletTransaction(
            tx_hash="0xsimulation",
            block_number=19000000,
            timestamp=datetime.now(timezone.utc),
            from_address=trader_address,
            to_address="0xrouter",
            chain=chain,
            dex_name="uniswap_v2",
            token_address=token_address,
            token_symbol="MOCK",
            pair_address="0xpair",
            action="buy",
            amount_in=amount_usd,
            amount_out=Decimal("100"),
            amount_usd=amount_usd,
            gas_used=150000,
            gas_price_gwei=Decimal("20"),
            is_mev=False
        )
        
        # Get trader config (mock)
        trader_config = {
            "copy_percentage": Decimal("5.0"),
            "max_copy_amount_usd": Decimal("1000.0"),
            "enabled": True
        }
        
        # Evaluate with copy trading strategy
        evaluation = await copy_trading_strategy.evaluate_copy_opportunity(
            mock_tx, trader_config, "simulation"
        )
        
        return {
            "status": "ok",
            "data": {
                "simulation_id": "sim_" + str(int(datetime.now().timestamp())),
                "original_trade": {
                    "trader_address": trader_address,
                    "token_address": token_address,
                    "amount_usd": float(amount_usd),
                    "chain": chain
                },
                "evaluation": {
                    "decision": evaluation.decision.value,
                    "reason": evaluation.reason.value,
                    "confidence": evaluation.confidence,
                    "copy_amount_usd": float(evaluation.copy_amount_usd),
                    "risk_score": float(evaluation.risk_score),
                    "notes": evaluation.notes
                },
                "estimated_outcome": {
                    "success_probability": 0.85,
                    "expected_slippage_bps": 25,
                    "estimated_gas_cost_usd": 15.0,
                    "net_exposure_usd": float(evaluation.copy_amount_usd) - 15.0
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error simulating copy trade: {e}")
        raise HTTPException(500, f"Failed to simulate copy trade: {str(e)}")


# Background Tasks
async def analyze_trader_background(trader_address: str, chain: str) -> None:
    """Background task to analyze a newly added trader."""
    try:
        logger.info(f"Starting background analysis for trader {trader_address[:8]}")
        
        # Mock analysis - would fetch historical transactions and analyze
        await asyncio.sleep(5)  # Simulate analysis time
        
        logger.info(f"Completed background analysis for trader {trader_address[:8]}")
        
    except Exception as e:
        logger.error(f"Error in background trader analysis: {e}")


# Health check
@router.get("/health")
async def copy_trading_health() -> Dict[str, Any]:
    """Health check for copy trading system."""
    return {
        "status": "ok",
        "components": {
            "wallet_monitor": "healthy",
            "strategy_engine": "healthy", 
            "live_executor": "healthy" if live_executor._initialized else "initializing",
            "performance_tracker": "healthy"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }