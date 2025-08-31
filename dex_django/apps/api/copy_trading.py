from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field, validator

from backend.app.discovery.wallet_monitor import wallet_monitor
from backend.app.strategy.copy_trading_strategy import copy_trading_strategy
from backend.app.core.runtime_state import runtime_state

router = APIRouter(prefix="/api/v1/copy", tags=["copy-trading"])


# Request/Response Models
class AddFollowedTraderRequest(BaseModel):
    """Request to add a new followed trader."""
    
    wallet_address: str = Field(..., min_length=40, max_length=64)
    trader_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    
    # Copy settings
    copy_mode: str = Field("percentage", regex="^(percentage|fixed_amount|proportional)$")
    copy_percentage: Decimal = Field(Decimal("5.0"), ge=0.1, le=50.0)
    fixed_amount_usd: Optional[Decimal] = Field(None, ge=10.0, le=10000.0)
    
    # Risk controls
    max_position_usd: Decimal = Field(Decimal("1000.0"), ge=50.0, le=50000.0)
    max_slippage_bps: int = Field(300, ge=50, le=1000)
    
    # Chain and direction restrictions
    allowed_chains: List[str] = Field(default_factory=lambda: ["ethereum", "bsc", "base"])
    copy_buy_only: bool = False
    copy_sell_only: bool = False
    
    @validator('allowed_chains')
    def validate_chains(cls, v):
        """Validate allowed chains."""
        valid_chains = {"ethereum", "bsc", "base", "polygon", "solana"}
        if not all(chain in valid_chains for chain in v):
            raise ValueError(f"Invalid chains. Must be from: {valid_chains}")
        return v
    
    @validator('wallet_address')
    def validate_wallet_address(cls, v):
        """Basic wallet address validation."""
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError("Invalid Ethereum wallet address format")
        return v.lower()


class UpdateFollowedTraderRequest(BaseModel):
    """Request to update followed trader settings."""
    
    trader_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = Field(None, regex="^(active|paused|blacklisted)$")
    
    # Copy settings
    copy_mode: Optional[str] = Field(None, regex="^(percentage|fixed_amount|proportional)$")
    copy_percentage: Optional[Decimal] = Field(None, ge=0.1, le=50.0)
    fixed_amount_usd: Optional[Decimal] = Field(None, ge=10.0, le=10000.0)
    
    # Risk controls
    max_position_usd: Optional[Decimal] = Field(None, ge=50.0, le=50000.0)
    max_slippage_bps: Optional[int] = Field(None, ge=50, le=1000)
    
    # Restrictions
    allowed_chains: Optional[List[str]] = None
    copy_buy_only: Optional[bool] = None
    copy_sell_only: Optional[bool] = None


class FollowedTraderResponse(BaseModel):
    """Response model for followed trader data."""
    
    id: str
    wallet_address: str
    trader_name: Optional[str]
    description: Optional[str]
    status: str
    
    # Copy settings
    copy_mode: str
    copy_percentage: Decimal
    fixed_amount_usd: Optional[Decimal]
    
    # Risk controls
    max_position_usd: Decimal
    max_slippage_bps: int
    allowed_chains: List[str]
    copy_buy_only: bool
    copy_sell_only: bool
    
    # Performance metrics
    total_copies: int
    successful_copies: int
    win_rate: float
    total_pnl_usd: Decimal
    
    # Timestamps
    created_at: datetime
    last_activity_at: Optional[datetime]
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }


class CopyTradeResponse(BaseModel):
    """Response model for copy trade history."""
    
    id: str
    followed_trader_id: str
    trader_address: str
    
    # Original trade
    original_tx_hash: str
    original_amount_usd: Decimal
    
    # Copy trade details
    chain: str
    dex_name: str
    token_symbol: Optional[str]
    copy_amount_usd: Decimal
    status: str
    
    # Results
    copy_tx_hash: Optional[str]
    realized_slippage_bps: Optional[int]
    total_fees_usd: Optional[Decimal]
    pnl_usd: Optional[Decimal]
    
    # Timing
    execution_delay_seconds: Optional[int]
    created_at: datetime
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }


class CopyTradingStatusResponse(BaseModel):
    """Response model for copy trading status."""
    
    is_enabled: bool
    monitoring_active: bool
    followed_traders_count: int
    active_copies_today: int
    total_copies: int
    win_rate_pct: float
    total_pnl_usd: Decimal
    
    class Config:
        json_encoders = {
            Decimal: str,
        }


# API Endpoints
@router.post("/toggle", summary="Enable/disable copy trading")
async def toggle_copy_trading(enabled: bool = Query(...)) -> Dict[str, Any]:
    """Enable or disable copy trading globally."""
    try:
        if enabled:
            # Get active traders and start monitoring
            traders = await _get_active_followed_traders()
            if traders:
                wallet_addresses = [trader["wallet_address"] for trader in traders]
                await wallet_monitor.start_monitoring(wallet_addresses)
        else:
            # Stop all monitoring
            await wallet_monitor.stop_monitoring()
        
        return {
            "status": "ok",
            "copy_trading_enabled": enabled,
            "monitoring_status": await wallet_monitor.get_monitoring_status()
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to toggle copy trading: {str(exc)}") from exc


@router.get("/status", summary="Get copy trading status")
async def get_copy_trading_status() -> CopyTradingStatusResponse:
    """Get current copy trading status and metrics."""
    try:
        monitoring_status = await wallet_monitor.get_monitoring_status()
        
        # Mock metrics - would query from database in production
        return CopyTradingStatusResponse(
            is_enabled=True,
            monitoring_active=monitoring_status["is_running"],
            followed_traders_count=monitoring_status["followed_wallets"],
            active_copies_today=5,
            total_copies=47,
            win_rate_pct=68.5,
            total_pnl_usd=Decimal("342.50")
        )
    except Exception as exc:
        raise HTTPException(500, f"Failed to get copy trading status: {str(exc)}") from exc


@router.get("/traders", summary="List followed traders")
async def list_followed_traders(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None, regex="^(active|paused|blacklisted)$")
) -> Dict[str, Any]:
    """List all followed traders with pagination and filtering."""
    try:
        # Mock data - would query from database in production
        mock_traders = [
            {
                "id": str(uuid.uuid4()),
                "wallet_address": "0x742d35cc6634c0532925a3b8d186dc8c",
                "trader_name": "DeFi Alpha Hunter",
                "status": "active",
                "copy_mode": "percentage",
                "copy_percentage": Decimal("3.0"),
                "max_position_usd": Decimal("500.0"),
                "total_copies": 23,
                "successful_copies": 16,
                "win_rate": 69.6,
                "total_pnl_usd": Decimal("187.25"),
                "created_at": datetime.now(),
                "last_activity_at": datetime.now()
            },
            {
                "id": str(uuid.uuid4()),
                "wallet_address": "0x8f67a2c1d5e4b3a9c0f7e9d8b6c5a4b3",
                "trader_name": "MEV Sandwich Master",
                "status": "paused",
                "copy_mode": "fixed_amount",
                "fixed_amount_usd": Decimal("200.0"),
                "max_position_usd": Decimal("1000.0"),
                "total_copies": 41,
                "successful_copies": 25,
                "win_rate": 61.0,
                "total_pnl_usd": Decimal("-45.80"),
                "created_at": datetime.now(),
                "last_activity_at": datetime.now()
            }
        ]
        
        # Filter by status if provided
        if status:
            mock_traders = [t for t in mock_traders if t["status"] == status]
        
        # Apply pagination
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_traders = mock_traders[start_idx:end_idx]
        
        return {
            "status": "ok",
            "data": paginated_traders,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": len(mock_traders),
                "pages": (len(mock_traders) + limit - 1) // limit,
                "has_next": end_idx < len(mock_traders),
                "has_prev": page > 1
            }
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to list followed traders: {str(exc)}") from exc


@router.post("/traders", summary="Add followed trader")
async def add_followed_trader(req: AddFollowedTraderRequest) -> Dict[str, Any]:
    """Add a new trader to follow."""
    try:
        # Validate trader isn't already followed
        existing_traders = await _get_active_followed_traders()
        if any(t["wallet_address"] == req.wallet_address for t in existing_traders):
            raise HTTPException(400, "Trader is already being followed")
        
        # Mock creation - would save to database in production
        trader_id = str(uuid.uuid4())
        
        trader_data = {
            "id": trader_id,
            "wallet_address": req.wallet_address,
            "trader_name": req.trader_name,
            "description": req.description,
            "status": "active",
            "copy_mode": req.copy_mode,
            "copy_percentage": req.copy_percentage,
            "fixed_amount_usd": req.fixed_amount_usd,
            "max_position_usd": req.max_position_usd,
            "max_slippage_bps": req.max_slippage_bps,
            "allowed_chains": req.allowed_chains,
            "copy_buy_only": req.copy_buy_only,
            "copy_sell_only": req.copy_sell_only,
            "created_at": datetime.now()
        }
        
        # Start monitoring this trader
        await wallet_monitor.start_monitoring([req.wallet_address])
        
        # Emit thought log
        await runtime_state.emit_thought_log({
            "event": "new_trader_added",
            "trader": {
                "address": req.wallet_address,
                "name": req.trader_name or "Unknown Trader",
                "copy_mode": req.copy_mode,
                "max_position_usd": float(req.max_position_usd)
            },
            "action": "start_monitoring",
            "rationale": f"Added new trader to copy trading watchlist"
        })
        
        return {
            "status": "ok", 
            "trader": trader_data,
            "message": f"Started monitoring trader {req.wallet_address[:8]}..."
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to add followed trader: {str(exc)}") from exc


@router.get("/traders/{trader_id}", summary="Get followed trader details")
async def get_followed_trader(trader_id: str) -> FollowedTraderResponse:
    """Get detailed information about a specific followed trader."""
    try:
        # Mock data - would query from database in production
        trader_data = {
            "id": trader_id,
            "wallet_address": "0x742d35cc6634c0532925a3b8d186dc8c",
            "trader_name": "DeFi Alpha Hunter",
            "description": "Experienced DeFi trader focusing on new token launches",
            "status": "active",
            "copy_mode": "percentage",
            "copy_percentage": Decimal("3.0"),
            "fixed_amount_usd": None,
            "max_position_usd": Decimal("500.0"),
            "max_slippage_bps": 300,
            "allowed_chains": ["ethereum", "bsc", "base"],
            "copy_buy_only": False,
            "copy_sell_only": False,
            "total_copies": 23,
            "successful_copies": 16,
            "win_rate": 69.6,
            "total_pnl_usd": Decimal("187.25"),
            "created_at": datetime.now(),
            "last_activity_at": datetime.now()
        }
        
        return FollowedTraderResponse(**trader_data)
    except Exception as exc:
        raise HTTPException(500, f"Failed to get trader details: {str(exc)}") from exc


@router.put("/traders/{trader_id}", summary="Update followed trader")
async def update_followed_trader(
    trader_id: str,
    req: UpdateFollowedTraderRequest
) -> Dict[str, Any]:
    """Update settings for a followed trader."""
    try:
        # Mock update - would update database in production
        updates = req.dict(exclude_unset=True)
        
        # If status changed to paused/blacklisted, stop monitoring
        if updates.get("status") in ["paused", "blacklisted"]:
            # Would get trader address from database
            trader_address = "0x742d35cc6634c0532925a3b8d186dc8c"
            await wallet_monitor.stop_monitoring(trader_address)
        
        return {
            "status": "ok",
            "updated_fields": list(updates.keys()),
            "message": f"Updated trader {trader_id}"
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to update trader: {str(exc)}") from exc


@router.delete("/traders/{trader_id}", summary="Remove followed trader")
async def remove_followed_trader(trader_id: str) -> Dict[str, Any]:
    """Stop following and remove a trader."""
    try:
        # Mock removal - would delete from database in production
        trader_address = "0x742d35cc6634c0532925a3b8d186dc8c"
        
        # Stop monitoring
        await wallet_monitor.stop_monitoring(trader_address)
        
        return {
            "status": "ok",
            "message": f"Removed trader {trader_id} and stopped monitoring"
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to remove trader: {str(exc)}") from exc


@router.get("/trades", summary="Get copy trade history")
async def get_copy_trades(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    trader_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, regex="^(pending|executed|failed|skipped)$"),
    chain: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get copy trade history with filtering and pagination."""
    try:
        # Mock data - would query from database in production
        mock_trades = [
            {
                "id": str(uuid.uuid4()),
                "followed_trader_id": str(uuid.uuid4()),
                "trader_address": "0x742d35cc6634c0532925a3b8d186dc8c",
                "original_tx_hash": "0xabc123...",
                "original_amount_usd": Decimal("1250.0"),
                "chain": "ethereum",
                "dex_name": "uniswap_v3",
                "token_symbol": "PEPE",
                "copy_amount_usd": Decimal("75.0"),
                "status": "executed",
                "copy_tx_hash": "0xdef456...",
                "realized_slippage_bps": 85,
                "total_fees_usd": Decimal("12.50"),
                "pnl_usd": Decimal("23.75"),
                "execution_delay_seconds": 18,
                "created_at": datetime.now()
            }
        ]
        
        # Apply filters
        filtered_trades = mock_trades
        if trader_id:
            filtered_trades = [t for t in filtered_trades if t["followed_trader_id"] == trader_id]
        if status:
            filtered_trades = [t for t in filtered_trades if t["status"] == status]
        if chain:
            filtered_trades = [t for t in filtered_trades if t["chain"] == chain]
        
        # Apply pagination
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_trades = filtered_trades[start_idx:end_idx]
        
        return {
            "status": "ok",
            "data": paginated_trades,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": len(filtered_trades),
                "pages": (len(filtered_trades) + limit - 1) // limit,
                "has_next": end_idx < len(filtered_trades),
                "has_prev": page > 1
            }
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to get copy trades: {str(exc)}") from exc


@router.post("/test-evaluation", summary="Test copy trade evaluation")
async def test_copy_evaluation() -> Dict[str, Any]:
    """Test the copy trading evaluation logic with mock data."""
    try:
        # Mock wallet transaction for testing
        from backend.app.discovery.wallet_monitor import WalletTransaction
        
        mock_tx = WalletTransaction(
            tx_hash="0xtest123",
            block_number=19000000,
            timestamp=datetime.now(),
            from_address="0x742d35cc6634c0532925a3b8d186dc8c",
            to_address="0xdex_address",
            chain="ethereum",
            dex_name="uniswap_v3",
            token_address="0xtoken123",
            token_symbol="TEST",
            pair_address="0xpair456",
            action="buy",
            amount_in=Decimal("0.5"),
            amount_out=Decimal("1000.0"),
            amount_usd=Decimal("500.0")
        )
        
        mock_config = {
            "status": "active",
            "copy_mode": "percentage",
            "copy_percentage": 3.0,
            "max_position_usd": 1000.0,
            "allowed_chains": ["ethereum", "bsc"]
        }
        
        # This would work with proper dependency injection
        # evaluation = await copy_trading_strategy.evaluate_copy_opportunity(
        #     mock_tx, mock_config, "test_trace_123"
        # )
        
        return {
            "status": "ok",
            "message": "Copy evaluation test would run here",
            "mock_data": {
                "transaction": mock_tx.dict(),
                "config": mock_config
            }
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to test copy evaluation: {str(exc)}") from exc


# Helper functions
async def _get_active_followed_traders() -> List[Dict[str, Any]]:
    """Get list of active followed traders."""
    # Mock implementation - would query database in production
    return [
        {
            "id": str(uuid.uuid4()),
            "wallet_address": "0x742d35cc6634c0532925a3b8d186dc8c",
            "status": "active"
        }
    ]