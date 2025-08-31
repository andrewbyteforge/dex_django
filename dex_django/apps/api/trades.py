from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from django.db import models

router = APIRouter(prefix="/api/v1")


class TradeResponse(BaseModel):
    """Trade response model."""
    id: int
    trade_id: str
    tx_hash: Optional[str]
    chain: str
    pair_symbol: str
    side: str
    mode: str
    status: str
    amount_in: str
    amount_out: str
    price_executed: Optional[str]
    slippage_bps: Optional[int]
    gas_cost_usd: Optional[str]
    pnl_usd: Optional[str]
    created_at: str
    confirmed_at: Optional[str]


@router.get("/trades/")
async def get_trades(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, le=100, description="Results per page"),
    mode: Optional[str] = Query(None, description="Filter by trade mode (paper, auto, manual)"),
    status: Optional[str] = Query(None, description="Filter by status (pending, filled, failed)"),
    chain: Optional[str] = Query(None, description="Filter by chain name")
) -> Dict[str, Any]:
    """Get paginated list of trades with filtering options."""
    try:
        from apps.storage.models import Trade
        
        # Build query
        query = Trade.objects.select_related('chain', 'pair', 'pair__base_token', 'pair__quote_token').all()
        
        # Apply filters
        if mode:
            query = query.filter(mode=mode)
        
        if status:
            query = query.filter(status=status)
        
        if chain:
            query = query.filter(chain__name__iexact=chain)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        offset = (page - 1) * limit
        db_trades = query.order_by('-created_at')[offset:offset + limit]
        
        # Build response
        trades = []
        for trade in db_trades:
            # Build pair symbol
            pair_symbol = f"{trade.pair.base_token.symbol}/{trade.pair.quote_token.symbol}"
            
            trade_data = TradeResponse(
                id=trade.id,
                trade_id=trade.trade_id,
                tx_hash=trade.tx_hash,
                chain=trade.chain.name,
                pair_symbol=pair_symbol,
                side=trade.side.value if hasattr(trade.side, 'value') else str(trade.side),
                mode=trade.mode.value if hasattr(trade.mode, 'value') else str(trade.mode),
                status=trade.status.value if hasattr(trade.status, 'value') else str(trade.status),
                amount_in=str(trade.amount_in),
                amount_out=str(trade.amount_out),
                price_executed=str(trade.price_executed) if trade.price_executed else None,
                slippage_bps=trade.slippage_bps,
                gas_cost_usd=str(trade.gas_cost_usd) if trade.gas_cost_usd else None,
                pnl_usd=str(trade.pnl_usd) if trade.pnl_usd else None,
                created_at=trade.created_at.isoformat(),
                confirmed_at=trade.confirmed_at.isoformat() if trade.confirmed_at else None
            )
            trades.append(trade_data)
        
        return {
            "status": "ok",
            "data": [t.dict() for t in trades],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            },
            "filters": {
                "mode": mode,
                "status": status,
                "chain": chain
            }
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to get trades: {str(e)}") from e


@router.get("/trades/{trade_id}")
async def get_trade_details(trade_id: int) -> Dict[str, Any]:
    """Get detailed information about a specific trade."""
    try:
        from apps.storage.models import Trade
        
        trade = Trade.objects.select_related(
            'chain', 'pair', 'pair__base_token', 'pair__quote_token'
        ).get(id=trade_id)
        
        trade_details = {
            "id": trade.id,
            "trade_id": trade.trade_id,
            "tx_hash": trade.tx_hash,
            "block_number": trade.block_number,
            "chain": {
                "name": trade.chain.name,
                "chain_id": trade.chain.chain_id
            },
            "pair": {
                "address": trade.pair.address,
                "dex": trade.pair.dex,
                "base_token": {
                    "symbol": trade.pair.base_token.symbol,
                    "address": trade.pair.base_token.address
                },
                "quote_token": {
                    "symbol": trade.pair.quote_token.symbol,
                    "address": trade.pair.quote_token.address
                }
            },
            "trade_details": {
                "side": trade.side.value if hasattr(trade.side, 'value') else str(trade.side),
                "mode": trade.mode.value if hasattr(trade.mode, 'value') else str(trade.mode),
                "status": trade.status.value if hasattr(trade.status, 'value') else str(trade.status),
                "strategy": trade.strategy,
                "signal_strength": float(trade.signal_strength) if trade.signal_strength else None,
                "confidence_score": float(trade.confidence_score) if trade.confidence_score else None
            },
            "amounts": {
                "amount_in": str(trade.amount_in),
                "amount_out": str(trade.amount_out),
                "amount_out_min": str(trade.amount_out_min),
                "price_executed": str(trade.price_executed) if trade.price_executed else None,
                "price_expected": str(trade.price_expected) if trade.price_expected else None,
                "slippage_bps": trade.slippage_bps,
                "price_impact_bps": trade.price_impact_bps
            },
            "gas_and_fees": {
                "gas_limit": trade.gas_limit,
                "gas_used": trade.gas_used,
                "gas_price_gwei": str(trade.gas_price_gwei) if trade.gas_price_gwei else None,
                "gas_cost_native": str(trade.gas_cost_native) if trade.gas_cost_native else None,
                "gas_cost_usd": str(trade.gas_cost_usd) if trade.gas_cost_usd else None
            },
            "performance": {
                "pnl_native": str(trade.pnl_native) if trade.pnl_native else None,
                "pnl_usd": str(trade.pnl_usd) if trade.pnl_usd else None,
                "roi_pct": str(trade.roi_pct) if trade.roi_pct else None
            },
            "risk_assessment": {
                "liquidity_at_trade": str(trade.liquidity_at_trade) if trade.liquidity_at_trade else None,
                "risk_score": float(trade.risk_score) if trade.risk_score else None
            },
            "timestamps": {
                "created_at": trade.created_at.isoformat(),
                "submitted_at": trade.submitted_at.isoformat() if trade.submitted_at else None,
                "confirmed_at": trade.confirmed_at.isoformat() if trade.confirmed_at else None
            },
            "error_info": {
                "error_message": trade.error_message,
                "retry_count": trade.retry_count
            }
        }
        
        return {
            "status": "ok",
            "data": trade_details
        }
        
    except Trade.DoesNotExist:
        raise HTTPException(404, f"Trade {trade_id} not found")
    except Exception as e:
        raise HTTPException(500, f"Failed to get trade details: {str(e)}") from e