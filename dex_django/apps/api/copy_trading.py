# APP: dex_django
# FILE: dex_django/apps/api/copy_trading.py
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from apps.discovery.wallet_tracker import wallet_tracker
from apps.discovery.wallet_monitor import WalletTransaction
from apps.copy_trading.copy_trading_strategy import copy_trading_strategy
from apps.storage.copy_trading_models import ChainType, WalletStatus, CopyMode
from apps.core.runtime_state import runtime_state
from apps.storage.copy_trading_repo import get_copy_trading_repositories

router = APIRouter(prefix="/api/v1/copy-trading", tags=["copy-trading"])
logger = logging.getLogger("api.copy_trading")


class TraderConfig(BaseModel):
    """Configuration for a trader to follow."""
    wallet_address: str
    trader_name: str
    chain: str
    copy_percentage: float = Field(ge=0.1, le=100.0)
    max_position_usd: float = Field(gt=0)
    min_trade_value_usd: float = Field(gt=0)
    allowed_chains: List[str] = ["ethereum", "bsc", "base"]
    status: str = "active"


class CopyTradeEvaluation(BaseModel):
    """Copy trade evaluation result."""
    should_copy: bool
    reason: str
    copy_amount_usd: float
    risk_score: float
    estimated_slippage_bps: int


@router.get("/traders", summary="Get all followed traders")
async def get_followed_traders(
    status: Optional[str] = Query(None, description="Filter by status"),
    chain: Optional[str] = Query(None, description="Filter by chain")
) -> Dict[str, Any]:
    """Get list of all followed traders with their configurations."""
    
    try:
        traders = await wallet_tracker.get_followed_traders()
        
        # Apply filters
        if status:
            traders = [t for t in traders if t.get("status") == status]
        if chain:
            traders = [t for t in traders if t.get("chain") == chain]
        
        return {
            "status": "ok",
            "traders": traders,
            "count": len(traders)
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to get traders: {str(exc)}") from exc


@router.post("/traders", summary="Add a new trader to follow")
async def add_trader(trader: TraderConfig) -> Dict[str, Any]:
    """Add a new trader to the copy trading system."""
    
    try:
        # Validate address format
        if not trader.wallet_address.startswith("0x") or len(trader.wallet_address) != 42:
            raise HTTPException(400, "Invalid wallet address format")
        
        # Add to wallet tracker
        result = await wallet_tracker.add_trader(
            wallet_address=trader.wallet_address.lower(),
            trader_name=trader.trader_name,
            chain=trader.chain,
            copy_percentage=trader.copy_percentage,
            max_position_usd=trader.max_position_usd,
            min_trade_value_usd=trader.min_trade_value_usd,
            allowed_chains=trader.allowed_chains,
            status=trader.status
        )
        
        # Emit thought log
        await runtime_state.emit_thought_log({
            "event": "trader_added",
            "trader": {
                "address": trader.wallet_address,
                "name": trader.trader_name,
                "chain": trader.chain,
                "copy_percentage": trader.copy_percentage
            }
        })
        
        return {
            "status": "ok",
            "message": f"Trader {trader.trader_name} added successfully",
            "trader_id": result.get("trader_id")
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to add trader: {str(exc)}") from exc


@router.put("/traders/{wallet_address}", summary="Update trader configuration")
async def update_trader(
    wallet_address: str,
    updates: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """Update configuration for an existing trader."""
    
    try:
        # Validate address
        wallet_address = wallet_address.lower()
        
        # Update trader
        result = await wallet_tracker.update_trader(wallet_address, updates)
        
        if not result:
            raise HTTPException(404, f"Trader {wallet_address} not found")
        
        # Emit thought log
        await runtime_state.emit_thought_log({
            "event": "trader_updated",
            "wallet_address": wallet_address,
            "updates": updates
        })
        
        return {
            "status": "ok",
            "message": f"Trader {wallet_address} updated successfully"
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to update trader: {str(exc)}") from exc


@router.delete("/traders/{wallet_address}", summary="Remove a trader")
async def remove_trader(wallet_address: str) -> Dict[str, Any]:
    """Remove a trader from the copy trading system."""
    
    try:
        # Validate and normalize address
        wallet_address = wallet_address.lower()
        
        # Remove trader
        result = await wallet_tracker.remove_trader(wallet_address)
        
        if not result:
            raise HTTPException(404, f"Trader {wallet_address} not found")
        
        # Emit thought log
        await runtime_state.emit_thought_log({
            "event": "trader_removed",
            "wallet_address": wallet_address
        })
        
        return {
            "status": "ok",
            "message": f"Trader {wallet_address} removed successfully"
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to remove trader: {str(exc)}") from exc


@router.get("/transactions", summary="Get recent wallet transactions")
async def get_wallet_transactions(
    limit: int = Query(50, ge=1, le=200),
    chain: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get recent transactions from followed wallets."""
    
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


@router.get("/performance/{wallet_address}", summary="Get trader performance")
async def get_trader_performance(
    wallet_address: str,
    days: int = Query(30, ge=1, le=365)
) -> Dict[str, Any]:
    """Get performance metrics for a specific trader."""
    
    try:
        # Validate address
        wallet_address = wallet_address.lower()
        
        # Get performance data
        performance = await wallet_tracker.get_trader_performance(
            wallet_address=wallet_address,
            days=days
        )
        
        if not performance:
            raise HTTPException(404, f"Trader {wallet_address} not found")
        
        return {
            "status": "ok",
            "wallet_address": wallet_address,
            "period_days": days,
            "performance": performance
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to get trader performance: {str(exc)}") from exc


@router.post("/evaluate", summary="Evaluate a potential copy trade")
async def evaluate_copy_trade(
    transaction: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """Evaluate whether a transaction should be copied based on strategy."""
    
    try:
        # Create WalletTransaction from input
        tx = WalletTransaction(
            tx_hash=transaction["tx_hash"],
            wallet_address=transaction["wallet_address"],
            chain=ChainType(transaction["chain"]),
            timestamp=datetime.fromisoformat(transaction["timestamp"]),
            token_address=transaction["token_address"],
            token_symbol=transaction.get("token_symbol", "UNKNOWN"),
            action=transaction["action"],
            amount_token=Decimal(str(transaction["amount_token"])),
            amount_usd=Decimal(str(transaction["amount_usd"])),
            gas_fee_usd=Decimal(str(transaction.get("gas_fee_usd", "0"))),
            dex_used=transaction.get("dex_used", "unknown"),
            confidence_score=transaction.get("confidence_score", 0.5)
        )
        
        # Get trader config
        trader_config = await wallet_tracker.get_trader_config(tx.wallet_address)
        if not trader_config:
            raise HTTPException(404, f"Trader {tx.wallet_address} not found")
        
        # Evaluate with strategy
        evaluation = await copy_trading_strategy.evaluate_copy_opportunity(
            tx, trader_config, "manual_evaluation"
        )
        
        return {
            "status": "ok",
            "evaluation": {
                "should_copy": evaluation.decision.value == "copy",
                "reason": evaluation.reason.value,
                "copy_amount_usd": float(evaluation.copy_amount_usd),
                "risk_score": float(evaluation.risk_score),
                "confidence": evaluation.confidence,
                "notes": evaluation.notes
            }
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to evaluate copy trade: {str(exc)}") from exc


# Helper functions
async def _get_active_followed_traders() -> List[Dict[str, Any]]:
    """Get list of active followed traders from WalletTracker."""
    
    traders = await wallet_tracker.get_followed_traders()
    active_traders = [t for t in traders if t.get("status") == "active"]
    return active_traders


async def _get_trader_statistics(wallet_address: str) -> Dict[str, Any]:
    """Get detailed statistics for a specific trader."""
    
    stats = await wallet_tracker.get_trader_performance(
        wallet_address=wallet_address,
        days=30
    )
    
    return stats or {
        "total_trades": 0,
        "win_rate": 0.0,
        "total_pnl_usd": 0.0,
        "avg_trade_size_usd": 0.0
    }