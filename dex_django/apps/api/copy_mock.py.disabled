# APP: FastAPI  
# FILE: apps/api/copy_mock.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Create FastAPI router
router = APIRouter(prefix="/api/v1/copy", tags=["copy-trading-mock"])

# Temporary in-memory storage for testing
MOCK_TRADERS = []
MOCK_TRADES = []

class AddTraderRequest(BaseModel):
    wallet_address: str
    trader_name: str = ""
    description: str = ""
    chain: str = "ethereum"
    copy_mode: str = "percentage"
    copy_percentage: float = 3.0
    fixed_amount_usd: float = None
    max_position_usd: float = 1000.0
    min_trade_value_usd: float = 50.0
    max_slippage_bps: int = 300
    allowed_chains: List[str] = ["ethereum"]
    copy_buy_only: bool = False
    copy_sell_only: bool = False

@router.get("/status")
async def copy_status() -> Dict[str, Any]:
    """Get copy trading status - MOCK VERSION"""
    return {
        "is_enabled": True,
        "monitoring_active": False,
        "followed_traders_count": len(MOCK_TRADERS),
        "active_copies_today": 0,
        "total_copies": len(MOCK_TRADES),
        "win_rate_pct": 65.5,
        "total_pnl_usd": "245.50"
    }

@router.get("/traders")
async def list_traders() -> Dict[str, Any]:
    """List all traders - MOCK VERSION"""
    return {
        "status": "ok",
        "data": MOCK_TRADERS,
        "count": len(MOCK_TRADERS)
    }

@router.post("/traders")
async def add_trader(req: AddTraderRequest) -> Dict[str, Any]:
    """Add trader - MOCK VERSION"""
    
    # Basic validation
    if not req.wallet_address or not req.wallet_address.startswith('0x'):
        raise HTTPException(400, "Invalid wallet address")
    
    if len(req.wallet_address) != 42:
        raise HTTPException(400, "Wallet address must be 42 characters")
    
    # Check if trader already exists
    for trader in MOCK_TRADERS:
        if trader['wallet_address'] == req.wallet_address.lower():
            raise HTTPException(400, "Trader already exists")
    
    # Create trader
    trader = {
        "id": str(uuid.uuid4()),
        "wallet_address": req.wallet_address.lower(),
        "trader_name": req.trader_name or f"Trader {req.wallet_address[:8]}",
        "description": req.description,
        "chain": req.chain,
        "status": "active",
        "copy_mode": req.copy_mode,
        "copy_percentage": req.copy_percentage,
        "fixed_amount_usd": req.fixed_amount_usd,
        "max_position_usd": req.max_position_usd,
        "min_trade_value_usd": req.min_trade_value_usd,
        "max_slippage_bps": req.max_slippage_bps,
        "allowed_chains": req.allowed_chains,
        "copy_buy_only": req.copy_buy_only,
        "copy_sell_only": req.copy_sell_only,
        "total_copies": 0,
        "successful_copies": 0,
        "win_rate": 0.0,
        "total_pnl_usd": "0.00",
        "created_at": datetime.now().isoformat(),
        "last_activity_at": None
    }
    
    MOCK_TRADERS.append(trader)
    
    return {
        "status": "ok",
        "trader": trader,
        "message": f"Added trader {trader['trader_name']}"
    }

@router.get("/trades")
async def list_trades() -> Dict[str, Any]:
    """List copy trades - MOCK VERSION"""
    return {
        "status": "ok",
        "data": MOCK_TRADES,
        "count": len(MOCK_TRADES)
    }

# Discovery endpoints
discovery_router = APIRouter(prefix="/api/v1/discovery", tags=["discovery-mock"])

@discovery_router.get("/discovery-status")
async def get_discovery_status() -> Dict[str, Any]:
    """Get discovery status - MOCK VERSION"""
    return {
        "status": "success",
        "discovery_running": False,
        "total_discovered": 0,
        "discovered_by_chain": {
            "ethereum": 0,
            "bsc": 0,
            "base": 0,
            "polygon": 0
        },
        "high_confidence_candidates": 0,
        "recent_discoveries": []
    }