from __future__ import annotations

import logging
from typing import Any, Dict
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger("api")


@api_view(["POST"])
@permission_classes([AllowAny])
def wallet_balances(request) -> Response:
    """Get wallet balances for a specific chain and address."""
    trace_id = getattr(request, 'trace_id', 'unknown')
    
    try:
        data = request.data
        chain = data.get('chain')
        address = data.get('address')
        
        if not chain or not address:
            return Response({
                "error": "Missing required fields: chain, address"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"[{trace_id}] Fetching balances for {chain}/{address[:8]}...")
        
        # Mock balance response for now - replace with real implementation
        mock_balance = {
            "chain": chain,
            "address": address,
            "native_balance": "1.5",
            "native_symbol": _get_native_symbol(chain),
            "token_balances": {
                "USDC": "1000.50",
                "WETH": "0.75" if chain != "solana" else "0",
                "USDT": "500.25"
            },
            "last_updated": timezone.now().isoformat()
        }
        
        logger.info(f"[{trace_id}] Mock balance returned for {chain}")
        
        return Response({
            "status": "ok",
            "balance": mock_balance,
            "cached": False
        })
        
    except Exception as e:
        logger.error(f"[{trace_id}] Failed to fetch wallet balances: {e}", exc_info=True)
        return Response({
            "error": f"Failed to fetch balances: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([AllowAny])
def prepare_transaction(request) -> Response:
    """Prepare a transaction for manual wallet approval."""
    trace_id = getattr(request, 'trace_id', 'unknown')
    
    try:
        data = request.data
        chain = data.get('chain')
        from_address = data.get('from_address')
        token_in = data.get('token_in')
        token_out = data.get('token_out')
        amount_in = data.get('amount_in')
        slippage_bps = data.get('slippage_bps', 300)
        
        if not all([chain, from_address, token_in, token_out, amount_in]):
            return Response({
                "error": "Missing required fields: chain, from_address, token_in, token_out, amount_in"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(
            f"[{trace_id}] Preparing transaction: {amount_in} {token_in} → {token_out} "
            f"on {chain}"
        )
        
        # Mock transaction preparation
        mock_transaction = {
            "transaction_id": f"tx_{trace_id}",
            "chain": chain,
            "from_address": from_address,
            "to_address": _get_router_address(chain),
            "value": "0" if token_in != _get_native_symbol(chain) else str(amount_in),
            "data": "0x" + "00" * 100,
            "gas_limit": 150000,
            "gas_price": "20000000000",
            "estimated_cost": "0.02",
            "trade_summary": {
                "token_in": token_in,
                "token_out": token_out,
                "amount_in": str(amount_in),
                "estimated_amount_out": str(float(amount_in) * 0.99),
                "slippage_bps": slippage_bps,
                "route": f"{token_in} → {token_out}",
                "dex": "uniswap_v3"
            }
        }
        
        logger.info(f"[{trace_id}] Mock transaction prepared")
        
        return Response({
            "status": "ok",
            "transaction": mock_transaction
        })
        
    except Exception as e:
        logger.error(f"[{trace_id}] Failed to prepare transaction: {e}", exc_info=True)
        return Response({
            "error": f"Failed to prepare transaction: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([AllowAny])
def supported_chains(request) -> Response:
    """Get list of supported chains for wallet connections."""
    trace_id = getattr(request, 'trace_id', 'unknown')
    
    try:
        supported_chains_list = [
            {
                "id": "ethereum",
                "name": "Ethereum",
                "chain_id": 1,
                "symbol": "ETH",
                "type": "evm"
            },
            {
                "id": "base", 
                "name": "Base",
                "chain_id": 8453,
                "symbol": "ETH",
                "type": "evm"
            },
            {
                "id": "polygon",
                "name": "Polygon",
                "chain_id": 137,
                "symbol": "MATIC",
                "type": "evm"
            },
            {
                "id": "bsc",
                "name": "BSC",
                "chain_id": 56,
                "symbol": "BNB",
                "type": "evm"
            },
            {
                "id": "solana",
                "name": "Solana", 
                "chain_id": None,
                "symbol": "SOL",
                "type": "solana"
            }
        ]
        
        logger.info(f"[{trace_id}] Returning {len(supported_chains_list)} supported chains")
        
        return Response({
            "status": "ok",
            "chains": supported_chains_list
        })
        
    except Exception as e:
        logger.error(f"[{trace_id}] Failed to get supported chains: {e}")
        return Response({
            "error": f"Failed to get supported chains: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_native_symbol(chain: str) -> str:
    """Get native token symbol for chain."""
    symbols = {
        "ethereum": "ETH",
        "base": "ETH", 
        "polygon": "MATIC",
        "bsc": "BNB",
        "solana": "SOL"
    }
    return symbols.get(chain, "ETH")


def _get_router_address(chain: str) -> str:
    """Get DEX router address for chain."""
    routers = {
        "ethereum": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
        "base": "0x2626664c2603336E57B271c5C0b26F421741e481",
        "polygon": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45", 
        "bsc": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
        "solana": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
    }
    return routers.get(chain, "0x0000000000000000000000000000000000000000")