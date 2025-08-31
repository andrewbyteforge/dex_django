from __future__ import annotations

from typing import Any, Dict, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from django.db import models
from django.core.paginator import Paginator
from django.db.models import Q, F, Count, Avg, Max

# Import Django models
from apps.storage.models import Token, Pair, Trade

router = APIRouter(prefix="/api/v1")


class OpportunityResponse(BaseModel):
    """Opportunity response model for token pair data."""
    id: int
    base_symbol: str
    quote_symbol: str
    address: str
    chain: str
    dex: str
    source: str
    liquidity_usd: Optional[float] = None
    score: float
    time_ago: str
    created_at: str
    risk_flags: List[str] = []


@router.get("/opportunities/")
async def get_opportunities(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    score_min: float = Query(0, ge=0, le=30, description="Minimum score filter"),
    score_max: float = Query(30, ge=0, le=30, description="Maximum score filter"),
    liquidity_min: float = Query(0, ge=0, description="Minimum liquidity USD"),
    liquidity_max: float = Query(1000000, ge=0, description="Maximum liquidity USD"),
    chains: Optional[str] = Query(None, description="Comma-separated chain filter"),
    sources: Optional[str] = Query(None, description="Comma-separated source filter"),
    sort_by: str = Query("discovered_at", description="Sort field: discovered_at, dex, chain"),
    sort_order: str = Query("desc", description="Sort order: asc, desc")
) -> Dict[str, Any]:
    """Get paginated opportunities with filtering and sorting from real database."""
    
    try:
        # Initialize Django if needed
        import django
        from django.conf import settings
        if not settings.configured:
            django.setup()
        
        # Base query with related data
        query = Pair.objects.select_related(
            'base_token', 
            'quote_token'
        ).all()
        
        # Chain filter
        if chains:
            chain_list = [c.strip().lower() for c in chains.split(",")]
            query = query.filter(chain__in=chain_list)
        
        # Source/DEX filter 
        if sources:
            source_list = [s.strip().lower() for s in sources.split(",")]
            query = query.filter(dex__in=source_list)
        
        # For now, we'll calculate a simple score based on recent activity
        # In production, you'd have a proper scoring mechanism
        query = query.annotate(
            recent_trades=Count(
                'trade',
                filter=models.Q(
                    trade__created_at__gte=datetime.now() - timedelta(hours=24)
                )
            ),
            calculated_score=models.Case(
                models.When(recent_trades__gt=10, then=5.0),
                models.When(recent_trades__gt=5, then=4.0),
                models.When(recent_trades__gt=1, then=3.0),
                default=2.0,
                output_field=models.FloatField()
            )
        )
        
        # Score filter (using calculated score)
        query = query.filter(
            calculated_score__gte=score_min,
            calculated_score__lte=score_max
        )
        
        # Sorting
        sort_field = sort_by
        if sort_by == "score":
            sort_field = "calculated_score"
        elif sort_by == "liquidity":
            # For now, sort by recent trades as proxy for liquidity
            sort_field = "recent_trades"
        elif sort_by == "time":
            sort_field = "discovered_at"
        
        if sort_order.lower() == "desc":
            sort_field = f"-{sort_field}"
        
        query = query.order_by(sort_field)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * limit
        pairs = query[offset:offset + limit]
        
        # Build response data
        opportunities = []
        for pair in pairs:
            # Calculate time_ago
            time_diff = datetime.now(pair.discovered_at.tzinfo) - pair.discovered_at
            if time_diff.total_seconds() < 60:
                time_ago = f"{int(time_diff.total_seconds())}s ago"
            elif time_diff.total_seconds() < 3600:
                time_ago = f"{int(time_diff.total_seconds() // 60)}m ago"
            else:
                time_ago = f"{int(time_diff.total_seconds() // 3600)}h ago"
            
            # Calculate mock liquidity based on trading activity
            mock_liquidity = None
            if hasattr(pair, 'recent_trades') and pair.recent_trades > 0:
                mock_liquidity = float(pair.recent_trades * 15000 + 30000)  # Mock calculation
            
            # Determine risk flags based on pair characteristics
            risk_flags = []
            if pair.dex in ['jupiter', 'pancake']:
                risk_flags.append("high_volatility")
            if pair.base_token.fee_on_transfer or pair.quote_token.fee_on_transfer:
                risk_flags.append("fee_on_transfer")
            
            opportunity = {
                "id": pair.id,
                "base_symbol": pair.base_token.symbol,
                "quote_symbol": pair.quote_token.symbol,
                "address": pair.address,
                "chain": pair.chain,
                "dex": pair.dex,
                "source": pair.dex,  # Use DEX name as source
                "liquidity_usd": mock_liquidity,
                "score": float(getattr(pair, 'calculated_score', 2.0)),
                "time_ago": time_ago,
                "created_at": pair.discovered_at.isoformat(),
                "risk_flags": risk_flags
            }
            opportunities.append(opportunity)
        
        # Calculate statistics
        high_liquidity_count = len([
            opp for opp in opportunities 
            if opp.get("liquidity_usd", 0) > 100000
        ])
        
        active_chains = len(set(opp["chain"] for opp in opportunities))
        
        avg_score = sum(opp["score"] for opp in opportunities) / len(opportunities) if opportunities else 0
        
        return {
            "status": "ok",
            "data": opportunities,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            },
            "stats": {
                "showing": len(opportunities),
                "filtered": total_count,
                "high_liquidity": high_liquidity_count,
                "active_chains": active_chains,
                "avg_score": round(avg_score, 1)
            },
            "filters": {
                "score_range": [score_min, score_max],
                "liquidity_range": [liquidity_min, liquidity_max],
                "chains": chains.split(",") if chains else None,
                "sources": sources.split(",") if sources else None,
                "sort_by": sort_by,
                "sort_order": sort_order
            }
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to get opportunities: {str(e)}") from e


@router.get("/opportunities/{opportunity_id}")
async def get_opportunity_details(opportunity_id: int) -> Dict[str, Any]:
    """Get detailed analysis for a specific opportunity from real database."""
    
    try:
        # Initialize Django if needed
        import django
        from django.conf import settings
        if not settings.configured:
            django.setup()
        
        # Get pair with related data
        try:
            pair = Pair.objects.select_related(
                'base_token', 
                'quote_token'
            ).get(id=opportunity_id)
        except Pair.DoesNotExist:
            raise HTTPException(404, f"Opportunity {opportunity_id} not found")
        
        # Get recent trading activity
        recent_trades = Trade.objects.filter(
            pair=pair,
            created_at__gte=datetime.now() - timedelta(days=7)
        ).order_by('-created_at')[:10]
        
        # Calculate metrics from actual trade data
        total_volume_24h = Trade.objects.filter(
            pair=pair,
            created_at__gte=datetime.now() - timedelta(hours=24)
        ).aggregate(
            total_volume=models.Sum('amount_in')
        )['total_volume'] or Decimal('0')
        
        # Build detailed response
        opportunity_detail = {
            "id": pair.id,
            "base_symbol": pair.base_token.symbol,
            "quote_symbol": pair.quote_token.symbol,
            "base_address": pair.base_token.address,
            "quote_address": pair.quote_token.address,
            "pair_address": pair.address,
            "chain": pair.chain,
            "dex": pair.dex,
            "fee_bps": pair.fee_bps,
            "discovered_at": pair.discovered_at.isoformat(),
            "last_updated": pair.updated_at.isoformat(),
            "volume_24h": float(total_volume_24h),
            "trade_count_7d": recent_trades.count(),
            "token_info": {
                "base_token": {
                    "symbol": pair.base_token.symbol,
                    "name": pair.base_token.name,
                    "decimals": pair.base_token.decimals,
                    "fee_on_transfer": pair.base_token.fee_on_transfer,
                },
                "quote_token": {
                    "symbol": pair.quote_token.symbol,
                    "name": pair.quote_token.name,
                    "decimals": pair.quote_token.decimals,
                    "fee_on_transfer": pair.quote_token.fee_on_transfer,
                }
            },
            "recent_trades": [
                {
                    "id": trade.id,
                    "side": trade.side,
                    "amount_in": str(trade.amount_in),
                    "amount_out": str(trade.amount_out),
                    "price": str(trade.exec_price) if trade.exec_price else None,
                    "gas_cost": str(trade.gas_native),
                    "tx_hash": trade.tx_hash,
                    "status": trade.status,
                    "created_at": trade.created_at.isoformat()
                } for trade in recent_trades
            ],
            "risk_analysis": {
                "fee_on_transfer_risk": "high" if (pair.base_token.fee_on_transfer or pair.quote_token.fee_on_transfer) else "none",
                "liquidity_risk": "medium" if recent_trades.count() < 5 else "low",
                "dex_risk": "low" if pair.dex in ['uniswap_v2', 'uniswap_v3'] else "medium",
                "chain_risk": "low" if pair.chain in ['ethereum', 'base'] else "medium"
            }
        }
        
        return {
            "status": "ok",
            "data": opportunity_detail
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to get opportunity details: {str(e)}") from e