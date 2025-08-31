from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.chains.providers import web3_manager
from apps.dex.routers import dex_manager

router = APIRouter()


class QuoteRequest(BaseModel):
    """Request model for getting trading quotes."""
    chain: str = Field(..., description="Blockchain name (ethereum, bsc, base)")
    token_in: str = Field(..., description="Input token contract address")
    token_out: str = Field(..., description="Output token contract address")
    amount_in: str = Field(..., description="Amount to trade (in token units)")
    slippage_bps: int = Field(default=300, description="Slippage tolerance in basis points")


class QuoteResponse(BaseModel):
    """Response model for trading quotes."""
    amount_in: str
    amount_out: str
    amount_out_min: str
    path: list[str]
    gas_estimate: int
    gas_price: int
    slippage_bps: int
    price_impact_bps: int
    router_address: str
    dex: str
    estimated_gas_cost_usd: Optional[str] = None


@router.post("/quotes", summary="Get trading quote")
async def get_quote(request: QuoteRequest) -> Dict[str, Any]:
    """
    Get best trading quote across all available DEXes on the specified chain.
    Returns quote with lowest price impact and highest output amount.
    """
    try:
        # Validate chain
        if request.chain not in ["ethereum", "bsc", "base"]:
            raise HTTPException(400, f"Unsupported chain: {request.chain}")
        
        # Validate slippage
        if not 10 <= request.slippage_bps <= 5000:  # 0.1% to 50%
            raise HTTPException(400, "Slippage must be between 10 and 5000 basis points")
        
        # Convert amount to Decimal
        try:
            amount_in = Decimal(request.amount_in)
            if amount_in <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError) as e:
            raise HTTPException(400, f"Invalid amount_in: {e}") from e
        
        # Get quote
        quote = await dex_manager.get_best_quote(
            chain=request.chain,
            token_in=request.token_in,
            token_out=request.token_out,
            amount_in=amount_in,
            slippage_bps=request.slippage_bps
        )
        
        if not quote:
            raise HTTPException(404, "No quote available for this trading pair")
        
        # Estimate gas cost in USD (simplified)
        estimated_gas_cost_usd = None
        if quote.gas_estimate and quote.gas_price:
            # This is a simplified calculation - in production you'd get accurate gas prices
            gas_cost_eth = (quote.gas_estimate * quote.gas_price) / 1e18
            # Assume ETH = $2000 for estimation (you'd get this from price feeds)
            estimated_gas_cost_usd = f"{gas_cost_eth * 2000:.2f}"
        
        return {
            "status": "ok",
            "quote": {
                "amount_in": str(quote.amount_in),
                "amount_out": str(quote.amount_out),
                "amount_out_min": str(quote.amount_out_min),
                "path": quote.path,
                "gas_estimate": quote.gas_estimate,
                "gas_price": quote.gas_price,
                "slippage_bps": quote.slippage_bps,
                "price_impact_bps": quote.price_impact_bps,
                "router_address": quote.router_address,
                "dex": quote.dex,
                "estimated_gas_cost_usd": estimated_gas_cost_usd
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to get quote: {str(e)}") from e


class BalanceRequest(BaseModel):
    """Request model for checking wallet balance."""
    chain: str = Field(..., description="Blockchain name")
    address: str = Field(..., description="Wallet address to check")


@router.post("/balance", summary="Get wallet balance")
async def get_balance(request: BalanceRequest) -> Dict[str, Any]:
    """
    Get native token balance for a wallet address on the specified chain.
    Returns balance in both wei and human-readable format.
    """
    try:
        # Validate chain
        if request.chain not in ["ethereum", "bsc", "base"]:
            raise HTTPException(400, f"Unsupported chain: {request.chain}")
        
        # Get balance
        balance = await web3_manager.get_balance(request.chain, request.address)
        
        if balance is None:
            raise HTTPException(503, f"Unable to fetch balance for {request.chain}")
        
        # Get chain config for symbol
        chain_config = web3_manager.get_chain_config(request.chain)
        symbol = chain_config.native_symbol if chain_config else "TOKEN"
        
        return {
            "status": "ok",
            "balance": {
                "address": request.address,
                "chain": request.chain,
                "balance": str(balance),
                "symbol": symbol,
                "balance_wei": str(int(balance * Decimal(10 ** 18)))
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to get balance: {str(e)}") from e


@router.get("/chains", summary="Get supported chains")
async def get_supported_chains() -> Dict[str, Any]:
    """Get list of supported blockchain networks with their configurations."""
    try:
        chains = []
        
        for chain_name, config in web3_manager.CHAIN_CONFIGS.items():
            chains.append({
                "name": config.name,
                "chain_id": config.chain_id,
                "native_symbol": config.native_symbol,
                "native_decimals": config.native_decimals,
                "block_time_ms": config.block_time_ms,
                "weth_address": config.weth_address,
                "usdc_address": config.usdc_address
            })
        
        return {
            "status": "ok",
            "chains": chains
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to get chains: {str(e)}") from e