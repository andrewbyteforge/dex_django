# APP: backend
# FILE: dex_django/apps/api/views_paper.py
from __future__ import annotations

import json
from typing import Any, Dict

from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


@api_view(["POST"])
@permission_classes([AllowAny])
def paper_toggle(request) -> Response:
    """Enable/disable Paper Trading and broadcast status via WebSocket."""
    try:
        enabled = request.data.get("enabled", False)
        
        # Store paper trading state in Django cache
        cache.set("paper_enabled", enabled, timeout=None)
        
        # Broadcast status to WebSocket clients
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "paper_trading",
                {
                    "type": "paper_status",
                    "message": {
                        "type": "status",
                        "timestamp": timezone.now().isoformat(),
                        "payload": {"paper_enabled": enabled},
                    },
                },
            )
        
        return Response({
            "status": "ok", 
            "paper_enabled": enabled
        })
        
    except Exception as exc:
        return Response(
            {"error": str(exc)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def paper_metrics(request) -> Response:
    """Get current Paper Trading metrics."""
    try:
        # Get metrics from Django cache or initialize defaults
        metrics = cache.get("paper_metrics", {
            "session_pnl_gbp": 0.0,
            "session_trades": 0,
            "win_rate": 0.0,
            "max_drawdown_gbp": 0.0,
            "last_update": timezone.now().isoformat(),
        })
        
        return Response({"status": "ok", "metrics": metrics})
        
    except Exception as exc:
        return Response(
            {"error": str(exc)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def paper_thought_log_test(request) -> Response:
    """Emit a sample AI Thought Log for UI testing."""
    try:
        test_payload = {
            "opportunity": {
                "pair": "0xDEADBEEF",
                "chain": "bsc",
                "dex": "pancake_v2",
                "symbol": "TEST"
            },
            "discovery_signals": {
                "liquidity_usd": 42000,
                "trend_score": 0.68
            },
            "risk_gates": {
                "owner_controls": "pass",
                "buy_tax": 0.03,
                "sell_tax": 0.03,
                "blacklist_check": "pass"
            },
            "pricing": {
                "quote_in": "0.25 BNB",
                "expected_out": "12345 TKN",
                "expected_slippage_bps": 75
            },
            "decision": {
                "action": "paper_buy",
                "rationale": "trend>0.6, taxes<=3%"
            },
        }
        
        # Broadcast thought log to WebSocket clients
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "paper_trading",
                {
                    "type": "thought_log",
                    "message": {
                        "type": "thought_log",
                        "timestamp": timezone.now().isoformat(),
                        "payload": test_payload,
                    },
                },
            )
        
        return Response({"status": "ok"})
        
    except Exception as exc:
        return Response(
            {"error": str(exc)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def update_paper_metrics(**fields: Any) -> None:
    """Update paper trading metrics and broadcast to WebSocket clients."""
    try:
        # Get current metrics from cache
        current_metrics = cache.get("paper_metrics", {
            "session_pnl_gbp": 0.0,
            "session_trades": 0,
            "win_rate": 0.0,
            "max_drawdown_gbp": 0.0,
            "last_update": timezone.now().isoformat(),
        })
        
        # Update with new fields
        for key, value in fields.items():
            if key in current_metrics:
                current_metrics[key] = value
        
        current_metrics["last_update"] = timezone.now().isoformat()
        
        # Save back to cache
        cache.set("paper_metrics", current_metrics, timeout=None)
        
        # Broadcast to WebSocket clients
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "paper_trading",
                {
                    "type": "paper_metrics",
                    "message": {
                        "type": "paper_metrics",
                        "timestamp": timezone.now().isoformat(),
                        "payload": current_metrics,
                    },
                },
            )
            
    except Exception as e:
        print(f"Error updating paper metrics: {e}")