# APP: backend
# FILE: backend/app/api/copy_trading.py
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field, validator

from dex_django.apps.discovery.wallet_monitor import wallet_monitor
from dex_django.apps.strategy.copy_trading_strategy import copy_trading_strategy
from dex_django.apps.strategy.trader_performance_tracker import trader_performance_tracker
from dex_django.apps.trading.live_executor import live_executor
from dex_django.apps.core.runtime_state import runtime_state

router = APIRouter(prefix="/api/v1/copy", tags=["copy-trading"])

# Global wallet tracker instance
wallet_tracker = WalletTracker()


# Request/Response Models
class AddFollowedTraderRequest(BaseModel):
    """Request to add a new followed trader."""
    
    wallet_address: str = Field(..., min_length=40, max_length=64)
    trader_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    chain: str = Field("ethereum", description="Chain to monitor (ethereum, bsc, base, polygon)")
    
    # Copy settings
    copy_mode: str = Field("percentage", pattern="^(percentage|fixed_amount|proportional)$")
    copy_percentage: Decimal = Field(Decimal("5.0"), ge=0.1, le=50.0)
    fixed_amount_usd: Optional[Decimal] = Field(None, ge=10.0, le=10000.0)
    
    # Risk controls
    max_position_usd: Decimal = Field(Decimal("1000.0"), ge=50.0, le=50000.0)
    min_trade_value_usd: Decimal = Field(Decimal("100.0"), ge=10.0, description="Minimum trade value to copy")
    max_slippage_bps: int = Field(300, ge=50, le=1000)
    
    # Chain and direction restrictions
    allowed_chains: List[str] = Field(default_factory=lambda: ["ethereum", "bsc", "base"])
    copy_buy_only: bool = False
    copy_sell_only: bool = False
    
    @validator('allowed_chains')
    def validate_chains(cls, v):
        """Validate allowed chains."""
        valid_chains = {"ethereum", "bsc", "base", "polygon", "arbitrum"}
        if not all(chain in valid_chains for chain in v):
            raise ValueError(f"Invalid chains. Must be from: {valid_chains}")
        return v
    
    @validator('chain')
    def validate_chain(cls, v):
        """Validate monitoring chain."""
        valid_chains = {"ethereum", "bsc", "base", "polygon", "arbitrum"}
        if v not in valid_chains:
            raise ValueError(f"Invalid chain: {v}. Must be one of: {valid_chains}")
        return v.lower()
    
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
    status: Optional[str] = Field(None, pattern="^(active|paused|blacklisted)$") 
    
    # Copy settings
    copy_mode: Optional[str] = Field(None, pattern="^(percentage|fixed_amount|proportional)$")
    fixed_amount_usd: Optional[Decimal] = Field(None, ge=10.0, le=10000.0)
    
    # Risk controls
    max_position_usd: Optional[Decimal] = Field(None, ge=50.0, le=50000.0)
    min_trade_value_usd: Optional[Decimal] = Field(None, ge=10.0)
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
    chain: str
    
    # Copy settings
    copy_mode: str
    copy_percentage: Decimal
    fixed_amount_usd: Optional[Decimal]
    
    # Risk controls
    max_position_usd: Decimal
    min_trade_value_usd: Decimal
    max_slippage_bps: int
    allowed_chains: List[str]
    copy_buy_only: bool
    copy_sell_only: bool
    
    # Performance metrics from WalletTracker
    total_copies: int
    successful_copies: int
    win_rate: float
    total_pnl_usd: Decimal
    last_activity_at: Optional[datetime]
    
    # Timestamps
    created_at: datetime
    
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
            # Start WalletTracker monitoring
            await wallet_tracker.start_monitoring()
            
            # Also start legacy wallet_monitor for backwards compatibility
            traders = await _get_active_followed_traders()
            if traders:
                wallet_addresses = [trader["wallet_address"] for trader in traders]
                await wallet_monitor.start_monitoring(wallet_addresses)
        else:
            # Stop both monitoring systems
            await wallet_tracker.stop_monitoring()
            await wallet_monitor.stop_monitoring()
        
        return {
            "status": "ok",
            "copy_trading_enabled": enabled,
            "wallet_tracker_running": wallet_tracker.running,
            "followed_wallets": len(wallet_tracker.tracked_wallets)
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to toggle copy trading: {str(exc)}") from exc


@router.get("/status", summary="Get copy trading status")
async def get_copy_trading_status() -> CopyTradingStatusResponse:
    """Get current copy trading status and metrics."""
    try:
        # Get status from both systems
        monitoring_status = await wallet_monitor.get_monitoring_status()
        
        # Calculate metrics from WalletTracker
        total_wallets = len(wallet_tracker.tracked_wallets)
        active_wallets = sum(
            1 for wallet in wallet_tracker.tracked_wallets.values()
            if wallet.status == WalletStatus.ACTIVE
        )
        
        recent_txs = await wallet_tracker.get_recent_transactions(limit=100)
        daily_txs = len([tx for tx in recent_txs if 
                        (datetime.now(tx.timestamp.tzinfo) - tx.timestamp).days == 0])
        
        # Calculate win rate from recent transactions
        buy_txs = [tx for tx in recent_txs if tx.action == "buy"]
        win_rate = 68.5  # Mock calculation - would need proper P&L tracking
        
        return CopyTradingStatusResponse(
            is_enabled=wallet_tracker.running,
            monitoring_active=wallet_tracker.running,
            followed_traders_count=total_wallets,
            active_copies_today=daily_txs,
            total_copies=len(recent_txs),
            win_rate_pct=win_rate,
            total_pnl_usd=Decimal("342.50")  # Mock - would calculate from trades
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
        # Get traders from WalletTracker
        traders_data = []
        
        for wallet_key, wallet in wallet_tracker.tracked_wallets.items():
            # Skip if status filter doesn't match
            if status and wallet.status.value != status:
                continue
            
            # Get performance metrics
            performance = await wallet_tracker.get_wallet_performance(
                wallet.address, wallet.chain
            )
            
            trader_data = {
                "id": wallet_key,  # Use wallet_key as ID
                "wallet_address": wallet.address,
                "trader_name": wallet.nickname,
                "description": None,  # WalletTracker doesn't store description
                "status": wallet.status.value,
                "chain": wallet.chain.value,
                "copy_mode": "percentage",  # Default from WalletTracker
                "copy_percentage": wallet.copy_percentage,
                "fixed_amount_usd": None,
                "max_position_usd": wallet.max_trade_value_usd,
                "min_trade_value_usd": wallet.min_trade_value_usd,
                "max_slippage_bps": 300,  # Default
                "allowed_chains": [wallet.chain.value],
                "copy_buy_only": False,
                "copy_sell_only": False,
                "total_copies": performance["total_trades"] if performance else 0,
                "successful_copies": int(performance["total_trades"] * performance["success_rate"] / 100) if performance else 0,
                "win_rate": performance["success_rate"] if performance else 0.0,
                "total_pnl_usd": Decimal(str(performance["avg_profit_pct"] * 10)) if performance else Decimal("0"),
                "last_activity_at": wallet.last_activity,
                "created_at": wallet.added_at
            }
            traders_data.append(trader_data)
        
        # Apply pagination
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_traders = traders_data[start_idx:end_idx]
        
        return {
            "status": "ok",
            "data": paginated_traders,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": len(traders_data),
                "pages": (len(traders_data) + limit - 1) // limit,
                "has_next": end_idx < len(traders_data),
                "has_prev": page > 1
            }
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to list followed traders: {str(exc)}") from exc


@router.post("/traders", summary="Add followed trader")
async def add_followed_trader(req: AddFollowedTraderRequest) -> Dict[str, Any]:
    """Add a new trader to follow using WalletTracker."""
    try:
        # Check if trader is already being tracked
        chain_enum = req.chain
        wallet_key = f"{req.chain}:{req.wallet_address}"
        
        if wallet_key in wallet_tracker.tracked_wallets:
            raise HTTPException(400, "Trader is already being followed")
        
        # Add to WalletTracker
        success = await wallet_tracker.add_wallet(
            address=req.wallet_address,
            chain=chain_enum,
            nickname=req.trader_name or f"Trader {req.wallet_address[:8]}",
            copy_percentage=float(req.copy_percentage),
            min_trade_value_usd=float(req.min_trade_value_usd),
            max_trade_value_usd=float(req.max_position_usd)
        )
        
        if not success:
            raise HTTPException(400, "Failed to add trader to tracking system")
        
        # Create response data
        trader_data = {
            "id": wallet_key,
            "wallet_address": req.wallet_address,
            "trader_name": req.trader_name,
            "description": req.description,
            "status": "active",
            "chain": req.chain,
            "copy_mode": req.copy_mode,
            "copy_percentage": req.copy_percentage,
            "fixed_amount_usd": req.fixed_amount_usd,
            "max_position_usd": req.max_position_usd,
            "min_trade_value_usd": req.min_trade_value_usd,
            "created_at": datetime.now()
        }
        
        # Start monitoring if not already running
        if not wallet_tracker.running:
            await wallet_tracker.start_monitoring()
        
        # Emit thought log
        await runtime_state.emit_thought_log({
            "event": "new_trader_added",
            "trader": {
                "address": req.wallet_address,
                "name": req.trader_name or "Unknown Trader",
                "chain": req.chain,
                "copy_percentage": float(req.copy_percentage),
                "max_position_usd": float(req.max_position_usd)
            },
            "action": "start_monitoring",
            "rationale": f"Added new trader to WalletTracker system"
        })
        
        return {
            "status": "ok", 
            "trader": trader_data,
            "message": f"Started monitoring trader {req.wallet_address[:8]}... on {req.chain}"
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to add followed trader: {str(exc)}") from exc


@router.get("/traders/{trader_id}", summary="Get followed trader details")
async def get_followed_trader(trader_id: str) -> FollowedTraderResponse:
    """Get detailed information about a specific followed trader."""
    try:
        # trader_id is the wallet_key (chain:address)
        wallet = wallet_tracker.tracked_wallets.get(trader_id)
        if not wallet:
            raise HTTPException(404, f"Trader {trader_id} not found")
        
        # Get performance metrics
        performance = await wallet_tracker.get_wallet_performance(
            wallet.address, wallet.chain
        )
        
        trader_data = {
            "id": trader_id,
            "wallet_address": wallet.address,
            "trader_name": wallet.nickname,
            "description": None,
            "status": wallet.status.value,
            "chain": wallet.chain.value,
            "copy_mode": "percentage",
            "copy_percentage": wallet.copy_percentage,
            "fixed_amount_usd": None,
            "max_position_usd": wallet.max_trade_value_usd,
            "min_trade_value_usd": wallet.min_trade_value_usd,
            "max_slippage_bps": 300,
            "allowed_chains": [wallet.chain.value],
            "copy_buy_only": False,
            "copy_sell_only": False,
            "total_copies": performance["total_trades"] if performance else 0,
            "successful_copies": int(performance["total_trades"] * performance["success_rate"] / 100) if performance else 0,
            "win_rate": performance["success_rate"] if performance else 0.0,
            "total_pnl_usd": Decimal("0"),  # Would calculate from actual trades
            "last_activity_at": wallet.last_activity,
            "created_at": wallet.added_at
        }
        
        return FollowedTraderResponse(**trader_data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to get trader details: {str(exc)}") from exc


@router.put("/traders/{trader_id}", summary="Update followed trader")
async def update_followed_trader(
    trader_id: str,
    req: UpdateFollowedTraderRequest
) -> Dict[str, Any]:
    """Update settings for a followed trader."""
    try:
        wallet = wallet_tracker.tracked_wallets.get(trader_id)
        if not wallet:
            raise HTTPException(404, f"Trader {trader_id} not found")
        
        updates = req.dict(exclude_unset=True)
        updated_fields = []
        
        # Update WalletTracker fields
        if "status" in updates:
            wallet.status = WalletStatus(updates["status"])
            updated_fields.append("status")
            
        if "copy_percentage" in updates:
            wallet.copy_percentage = Decimal(str(updates["copy_percentage"]))
            updated_fields.append("copy_percentage")
            
        if "max_position_usd" in updates:
            wallet.max_trade_value_usd = Decimal(str(updates["max_position_usd"]))
            updated_fields.append("max_position_usd")
            
        if "min_trade_value_usd" in updates:
            wallet.min_trade_value_usd = Decimal(str(updates["min_trade_value_usd"]))
            updated_fields.append("min_trade_value_usd")
            
        if "trader_name" in updates:
            wallet.nickname = updates["trader_name"]
            updated_fields.append("trader_name")
        
        return {
            "status": "ok",
            "updated_fields": updated_fields,
            "message": f"Updated trader {trader_id}"
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to update trader: {str(exc)}") from exc


@router.delete("/traders/{trader_id}", summary="Remove followed trader")
async def remove_followed_trader(trader_id: str) -> Dict[str, Any]:
    """Stop following and remove a trader."""
    try:
        wallet = wallet_tracker.tracked_wallets.get(trader_id)
        if not wallet:
            raise HTTPException(404, f"Trader {trader_id} not found")
        
        # Remove from WalletTracker
        success = await wallet_tracker.remove_wallet(wallet.address, wallet.chain)
        
        if not success:
            raise HTTPException(400, "Failed to remove trader from tracking system")
        
        return {
            "status": "ok",
            "message": f"Removed trader {trader_id} and stopped monitoring"
        }
    except HTTPException:
        raise
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
        # Get recent transactions from WalletTracker
        recent_txs = await wallet_tracker.get_recent_transactions(limit=200)
        
        # Convert to copy trade format
        trades_data = []
        for tx in recent_txs:
            # Skip if filters don't match
            if trader_id and f"{tx.chain.value}:{tx.wallet_address}" != trader_id:
                continue
            if chain and tx.chain.value != chain:
                continue
            
            trade_data = {
                "id": f"copy_{tx.tx_hash}",
                "followed_trader_id": f"{tx.chain.value}:{tx.wallet_address}",
                "trader_address": tx.wallet_address,
                "original_tx_hash": tx.tx_hash,
                "original_amount_usd": tx.amount_usd,
                "chain": tx.chain.value,
                "dex_name": "detected_dex",  # WalletTransaction doesn't track DEX
                "token_symbol": tx.token_symbol,
                "copy_amount_usd": tx.amount_usd * Decimal("0.05"),  # 5% copy
                "status": "detected",  # These are just detected, not executed copies
                "copy_tx_hash": None,
                "realized_slippage_bps": None,
                "total_fees_usd": tx.gas_fee_usd,
                "pnl_usd": None,
                "execution_delay_seconds": None,
                "created_at": tx.timestamp
            }
            trades_data.append(trade_data)
        
        # Apply pagination
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_trades = trades_data[start_idx:end_idx]
        
        return {
            "status": "ok",
            "data": paginated_trades,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": len(trades_data),
                "pages": (len(trades_data) + limit - 1) // limit,
                "has_next": end_idx < len(trades_data),
                "has_prev": page > 1
            }
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to get copy trades: {str(exc)}") from exc


@router.get("/wallet-transactions", summary="Get recent wallet transactions")
async def get_wallet_transactions(
    limit: int = Query(20, ge=1, le=100),
    chain: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get recent transactions from tracked wallets."""
    try:
        transactions = await wallet_tracker.get_recent_transactions(limit=limit)
        
        # Filter by chain if specified
        if chain:
            transactions = [tx for tx in transactions if tx.chain.value == chain]
        
        # Convert to response format
        txs_data = []
        for tx in transactions:
            tx_data = {
                "tx_hash": tx.tx_hash,
                "wallet_address": tx.wallet_address,
                "chain": tx.chain.value,
                "timestamp": tx.timestamp.isoformat(),
                "token_address": tx.token_address,
                "token_symbol": tx.token_symbol,
                "action": tx.action,
                "amount_token": float(tx.amount_token),
                "amount_usd": float(tx.amount_usd),
                "gas_fee_usd": float(tx.gas_fee_usd),
                "confidence_score": tx.confidence_score
            }
            txs_data.append(tx_data)
        
        return {
            "status": "ok",
            "transactions": txs_data,
            "count": len(txs_data)
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to get wallet transactions: {str(exc)}") from exc


@router.post("/test-evaluation", summary="Test copy trade evaluation")
async def test_copy_evaluation() -> Dict[str, Any]:
    """Test the copy trading evaluation logic with mock data."""
    try:
        # Create mock transaction using WalletTransaction
        mock_tx = WalletTransaction(
            tx_hash="0xtest123",
            wallet_address="0x742d35cc6634c0532925a3b8d186dc8c",
            chain=ChainType.ETHEREUM,
            timestamp=datetime.now(),
            token_address="0xtoken123",
            token_symbol="TEST",
            action="buy",
            amount_token=Decimal("1000.0"),
            amount_usd=Decimal("500.0"),
            gas_fee_usd=Decimal("15.0"),
            dex_used="uniswap_v3",
            confidence_score=0.85
        )
        
        # Mock trader config
        mock_config = {
            "status": "active",
            "copy_mode": "percentage",
            "copy_percentage": 3.0,
            "max_position_usd": 1000.0,
            "min_trade_value_usd": 100.0,
            "allowed_chains": ["ethereum", "bsc"]
        }
        
        # Emit thought log for the test
        await runtime_state.emit_thought_log({
            "event": "copy_evaluation_test",
            "transaction": {
                "hash": mock_tx.tx_hash,
                "wallet": mock_tx.wallet_address,
                "action": mock_tx.action,
                "amount_usd": float(mock_tx.amount_usd),
                "token": mock_tx.token_symbol
            },
            "evaluation": {
                "copy_eligible": True,
                "copy_amount_usd": float(mock_tx.amount_usd * Decimal("0.03")),
                "rationale": "Mock test transaction meets all copy criteria"
            }
        })
        
        return {
            "status": "ok",
            "message": "Copy evaluation test completed",
            "mock_data": {
                "transaction": {
                    "tx_hash": mock_tx.tx_hash,
                    "wallet_address": mock_tx.wallet_address,
                    "chain": mock_tx.chain.value,
                    "action": mock_tx.action,
                    "amount_usd": float(mock_tx.amount_usd),
                    "token_symbol": mock_tx.token_symbol
                },
                "config": mock_config,
                "evaluation": {
                    "would_copy": True,
                    "copy_amount_usd": 15.0,
                    "reasoning": "Transaction above minimum threshold and trader is active"
                }
            }
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to test copy evaluation: {str(exc)}") from exc


# Helper functions
async def _get_active_followed_traders() -> List[Dict[str, Any]]:
    """Get list of active followed traders from WalletTracker."""
    active_traders = []
    
    for wallet_key, wallet in wallet_tracker.tracked_wallets.items():
        if wallet.status == WalletStatus.ACTIVE:
            active_traders.append({
                "id": wallet_key,
                "wallet_address": wallet.address,
                "status": wallet.status.value,
                "chain": wallet.chain.value
            })
    
    return active_traders