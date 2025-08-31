from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from django.db import models

router = APIRouter(prefix="/api/v1")


class TokenResponse(BaseModel):
    """Token response model."""
    id: int
    address: str
    symbol: str
    name: str
    decimals: int
    chain: str
    is_verified: bool = False
    is_honeypot: bool = False
    is_blacklisted: bool = False
    total_supply: Optional[str] = None
    discovered_at: Optional[str] = None
    price_usd: Optional[float] = None


@router.get("/tokens/")
async def get_tokens(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, le=100, description="Results per page"),
    chain: Optional[str] = Query(None, description="Filter by chain name"),
    search: Optional[str] = Query(None, description="Search by symbol, name, or address"),
    verified_only: bool = Query(False, description="Only show verified tokens"),
    exclude_honeypots: bool = Query(True, description="Exclude known honeypots")
) -> Dict[str, Any]:
    """Get paginated list of tokens with filtering options."""
    try:
        from apps.storage.models import Token, Chain
        
        # Build query
        query = Token.objects.select_related('chain').all()
        
        # Apply filters
        if chain:
            query = query.filter(chain__name__iexact=chain)
        
        if search:
            query = query.filter(
                models.Q(symbol__icontains=search) |
                models.Q(name__icontains=search) |
                models.Q(address__icontains=search)
            )
        
        if verified_only:
            query = query.filter(is_verified=True)
        
        if exclude_honeypots:
            query = query.filter(is_honeypot=False)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * limit
        db_tokens = query.order_by('-discovered_at')[offset:offset + limit]
        
        # Build response
        tokens = []
        for token in db_tokens:
            token_data = TokenResponse(
                id=token.id,
                address=token.address,
                symbol=token.symbol,
                name=token.name or token.symbol,
                decimals=token.decimals,
                chain=token.chain.name,
                is_verified=token.is_verified,
                is_honeypot=token.is_honeypot,
                is_blacklisted=token.is_blacklisted,
                total_supply=str(token.total_supply) if token.total_supply else None,
                discovered_at=token.discovered_at.isoformat() if token.discovered_at else None,
                price_usd=None  # You'd fetch this from price feeds
            )
            tokens.append(token_data)
        
        return {
            "status": "ok",
            "data": [t.dict() for t in tokens],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            },
            "filters": {
                "chain": chain,
                "search": search,
                "verified_only": verified_only,
                "exclude_honeypots": exclude_honeypots
            }
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to get tokens: {str(e)}") from e


@router.get("/tokens/{token_id}")
async def get_token_details(token_id: int) -> Dict[str, Any]:
    """Get detailed information about a specific token."""
    try:
        from apps.storage.models import Token, Pair
        
        token = Token.objects.select_related('chain').get(id=token_id)
        
        # Get trading pairs for this token
        pairs = Pair.objects.filter(
            models.Q(base_token=token) | models.Q(quote_token=token)
        ).select_related('base_token', 'quote_token', 'chain')[:10]
        
        pair_data = []
        for pair in pairs:
            pair_info = {
                "id": pair.id,
                "address": pair.address,
                "dex": pair.dex,
                "base_token": pair.base_token.symbol,
                "quote_token": pair.quote_token.symbol,
                "liquidity_usd": float(pair.liquidity_usd) if pair.liquidity_usd else 0,
                "volume_24h_usd": float(pair.volume_24h_usd) if pair.volume_24h_usd else 0
            }
            pair_data.append(pair_info)
        
        token_details = {
            "id": token.id,
            "address": token.address,
            "symbol": token.symbol,
            "name": token.name,
            "decimals": token.decimals,
            "chain": token.chain.name,
            "is_verified": token.is_verified,
            "is_honeypot": token.is_honeypot,
            "is_blacklisted": token.is_blacklisted,
            "is_mintable": token.is_mintable,
            "is_burnable": token.is_burnable,
            "fee_on_transfer": token.fee_on_transfer,
            "total_supply": str(token.total_supply) if token.total_supply else None,
            "discovered_at": token.discovered_at.isoformat() if token.discovered_at else None,
            "first_seen_block": token.first_seen_block,
            "trading_pairs": pair_data
        }
        
        return {
            "status": "ok",
            "data": token_details
        }
        
    except Token.DoesNotExist:
        raise HTTPException(404, f"Token {token_id} not found")
    except Exception as e:
        raise HTTPException(500, f"Failed to get token details: {str(e)}") from e