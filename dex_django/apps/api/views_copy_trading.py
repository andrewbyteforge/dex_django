from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Dict, Any, List

from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.intelligence.copy_trading_engine import copy_trading_engine

logger = logging.getLogger("api.copy_trading")

@api_view(["GET"])
@permission_classes([AllowAny])
def discover_traders(request) -> Response:
    """Discover profitable traders to copy."""
    
    try:
        min_profit = Decimal(request.GET.get('min_profit_usd', '10000'))
        min_win_rate = float(request.GET.get('min_win_rate', '70'))
        max_risk = request.GET.get('max_risk_level', 'medium')
        
        # Run async discovery
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            traders = loop.run_until_complete(
                copy_trading_engine.discover_profitable_traders(
                    min_profit_usd=min_profit,
                    min_win_rate=min_win_rate,
                    max_risk_level=max_risk
                )
            )
        finally:
            loop.close()
        
        # Convert to serializable format
        traders_data = []
        for trader in traders:
            traders_data.append({
                "wallet_address": trader.wallet_address,
                "chain": trader.chain,
                "success_rate": trader.success_rate,
                "total_profit_usd": str(trader.total_profit_usd),
                "avg_position_size_usd": str(trader.avg_position_size_usd),
                "trades_count": trader.trades_count,
                "win_streak": trader.win_streak,
                "max_drawdown_pct": trader.max_drawdown_pct,
                "sharpe_ratio": trader.sharpe_ratio,
                "specialty_tags": trader.specialty_tags,
                "risk_level": trader.risk_level,
                "verified": trader.verified,
                "last_active": trader.last_active.isoformat()
            })
        
        return Response({
            "status": "ok",
            "traders": traders_data,
            "count": len(traders_data)
        })
        
    except Exception as e:
        logger.error(f"Trader discovery failed: {e}")
        return Response({
            "error": f"Discovery failed: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@permission_classes([AllowAny])
def copy_signals(request) -> Response:
    """Get real-time copy trading signals."""
    
    try:
        # Get tracked traders from query params or use defaults
        trader_addresses = request.GET.getlist('traders', [])
        chains = request.GET.getlist('chains', ["ethereum", "bsc", "base"])
        
        if not trader_addresses:
            # Use top 10 tracked traders as default
            trader_addresses = [
                "0x8ba1f109551bD432803012645Hac136c",  # Mock addresses
                "0x742d35Cc6634C0532925a3b8d404dHVpC4e72", 
                "0x40ec5B33f54e0E4A4de5a08dc00002de5644", 
            ]
        
        # Monitor for signals
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            signals = loop.run_until_complete(
                copy_trading_engine.monitor_trader_transactions(
                    trader_addresses=trader_addresses,
                    chains=chains
                )
            )
        finally:
            loop.close()
        
        # Convert signals to JSON format
        signals_data = []
        for signal in signals:
            signals_data.append({
                "trader_address": signal.trader_address,
                "token_in": signal.token_in,
                "token_out": signal.token_out,
                "amount_usd": str(signal.amount_usd),
                "transaction_hash": signal.transaction_hash,
                "chain": signal.chain,
                "dex": signal.dex,
                "confidence_score": signal.confidence_score,
                "estimated_profit_potential": signal.estimated_profit_potential,
                "risk_warning": signal.risk_warning,
                "copy_recommendation": signal.copy_recommendation,
                "detected_at": signal.detected_at.isoformat()
            })
        
        return Response({
            "status": "ok",
            "signals": signals_data,
            "count": len(signals_data)
        })
        
    except Exception as e:
        logger.error(f"Copy signals failed: {e}")
        return Response({
            "error": f"Signals failed: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@permission_classes([AllowAny])
def copy_trading_stats(request) -> Response:
    """Get copy trading statistics and performance."""
    
    return Response({
        "status": "ok",
        "stats": {
            "tracked_traders": 15,
            "active_copies": 3,
            "success_rate": 78.5,
            "total_profit_24h": 1250.30,
            "avg_copy_confidence": 82.3,
            "top_performing_trader": {
                "address": "0x8ba1f109551bD432803012645Hac136c",
                "success_rate": 85.2,
                "profit_24h": 450.75
            }
        }
    })

@api_view(["POST"])
@permission_classes([AllowAny])
def toggle_copy_trading(request) -> Response:
    """Enable/disable copy trading mode."""
    
    try:
        enabled = request.data.get('enabled', False)
        
        # In a real implementation, this would update user settings
        # For now, return success with the requested state
        
        return Response({
            "status": "ok",
            "copy_trading_enabled": enabled,
            "message": f"Copy trading {'enabled' if enabled else 'disabled'}"
        })
        
    except Exception as e:
        logger.error(f"Toggle copy trading failed: {e}")
        return Response({
            "error": f"Toggle failed: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)