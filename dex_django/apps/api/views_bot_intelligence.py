from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, List
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone
from dex_django.apps.strategy import risk_manager
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.intelligence import (
    strategy_engine, 
    market_intelligence, 
    TradingMode,
    StrategyType
)

logger = logging.getLogger("api.intelligence")

@api_view(["POST"])
@permission_classes([AllowAny])
def analyze_opportunities(request) -> Response:
    """Analyze opportunities using advanced intelligence system."""
    
    trace_id = getattr(request, 'trace_id', 'unknown')
    
    try:
        data = request.data
        opportunities = data.get('opportunities', [])
        user_balance_usd = Decimal(str(data.get('balance_usd', '1000')))
        risk_mode_str = data.get('risk_mode', 'moderate')
        
        # Convert risk mode string to enum
        risk_mode = TradingMode(risk_mode_str)
        
        logger.info(f"[{trace_id}] Analyzing {len(opportunities)} opportunities with {risk_mode_str} risk")
        
        # Run analysis in async context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            signals = loop.run_until_complete(
                strategy_engine.generate_trading_signals(
                    opportunities, user_balance_usd, risk_mode
                )
            )
        finally:
            loop.close()
        
        # Convert signals to JSON-serializable format
        signals_data = []
        for signal in signals:
            signal_data = {
                "pair_address": signal.pair_address,
                "chain": signal.chain,
                "strategy_type": signal.strategy_type.value,
                "action": signal.action,
                "confidence": signal.confidence,
                "urgency": signal.urgency,
                "reasoning": signal.reasoning,
                "execution_deadline": signal.execution_deadline.isoformat(),
                "risk_warnings": signal.risk_warnings
            }
            
            # Add position sizing if available
            if signal.position_sizing:
                signal_data["position_sizing"] = {
                    "recommended_amount_usd": float(signal.position_sizing.recommended_amount_usd),
                    "max_safe_amount_usd": float(signal.position_sizing.max_safe_amount_usd),
                    "stop_loss_price": float(signal.position_sizing.stop_loss_price),
                    "take_profit_price": float(signal.position_sizing.take_profit_price),
                    "max_acceptable_slippage": float(signal.position_sizing.max_acceptable_slippage)
                }
            
            signals_data.append(signal_data)
        
        logger.info(f"[{trace_id}] Generated {len(signals_data)} trading signals")
        
        return Response({
            "status": "ok",
            "signals": signals_data,
            "count": len(signals_data),
            "risk_mode": risk_mode_str
        })
        
    except Exception as e:
        logger.error(f"[{trace_id}] Intelligence analysis failed: {e}", exc_info=True)
        return Response({
            "error": f"Analysis failed: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([AllowAny])
def detailed_analysis(request) -> Response:
    """Get detailed analysis for a specific opportunity."""
    
    trace_id = getattr(request, 'trace_id', 'unknown')
    
    try:
        data = request.data
        opportunity = data.get('opportunity', {})
        trade_amount_eth = Decimal(str(data.get('trade_amount_eth', '0.1')))
        
        if not opportunity:
            return Response({
                "error": "No opportunity provided"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"[{trace_id}] Detailed analysis for {opportunity.get('pair_address', 'unknown')}")
        
        # Run analysis in async context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            analysis = loop.run_until_complete(
                market_intelligence.analyze_opportunity(opportunity, trade_amount_eth)
            )
        finally:
            loop.close()
        
        # Convert analysis to JSON-serializable format
        analysis_data = {
            "pair_address": analysis.pair_address,
            "chain": analysis.chain,
            "liquidity_depth": analysis.liquidity_depth,
            "honeypot_probability": analysis.honeypot_probability,
            "ownership_analysis": analysis.ownership_analysis,
            "tax_analysis": analysis.tax_analysis,
            "momentum_score": analysis.momentum_score,
            "social_sentiment": analysis.social_sentiment,
            "whale_activity": analysis.whale_activity,
            "overall_risk_score": analysis.overall_risk_score,
            "recommendation": analysis.recommendation
        }
        
        # Add advanced analysis if available
        if analysis.advanced_risk_analysis:
            analysis_data["advanced_risk_analysis"] = analysis.advanced_risk_analysis
        
        if analysis.mempool_intelligence:
            analysis_data["mempool_intelligence"] = analysis.mempool_intelligence
        
        logger.info(f"[{trace_id}] Detailed analysis complete: {analysis.recommendation}")
        
        return Response({
            "status": "ok",
            "analysis": analysis_data
        })
        
    except Exception as e:
        logger.error(f"[{trace_id}] Detailed analysis failed: {e}", exc_info=True)
        return Response({
            "error": f"Analysis failed: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def risk_settings(request) -> Response:
    """Get or update risk management settings."""
    
    trace_id = getattr(request, 'trace_id', 'unknown')
    
    if request.method == "GET":
        try:
            # Return current risk profiles
            profiles = {}
            for mode in TradingMode:
                profile = risk_manager.risk_profiles[mode]
                profiles[mode.value] = {
                    "max_daily_loss_usd": float(profile.max_daily_loss_usd),
                    "max_position_size_usd": float(profile.max_position_size_usd),
                    "max_portfolio_allocation_pct": float(profile.max_portfolio_allocation_pct),
                    "max_slippage_pct": float(profile.max_slippage_pct),
                    "stop_loss_pct": float(profile.stop_loss_pct),
                    "take_profit_pct": float(profile.take_profit_pct),
                    "chains_enabled": profile.chains_enabled,
                    "min_liquidity_usd": float(profile.min_liquidity_usd)
                }
            
            return Response({
                "status": "ok",
                "risk_profiles": profiles,
                "circuit_breaker_active": risk_manager.circuit_breaker_active
            })
            
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to get risk settings: {e}")
            return Response({
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    else:  # POST
        try:
            # Update risk settings
            data = request.data
            risk_mode_str = data.get('risk_mode', 'moderate')
            risk_mode = TradingMode(risk_mode_str)
            
            # Update specific settings if provided
            profile = risk_manager.risk_profiles[risk_mode]
            
            if 'max_daily_loss_usd' in data:
                profile.max_daily_loss_usd = Decimal(str(data['max_daily_loss_usd']))
            
            if 'max_position_size_usd' in data:
                profile.max_position_size_usd = Decimal(str(data['max_position_size_usd']))
            
            if 'stop_loss_pct' in data:
                profile.stop_loss_pct = Decimal(str(data['stop_loss_pct']))
            
            if 'take_profit_pct' in data:
                profile.take_profit_pct = Decimal(str(data['take_profit_pct']))
            
            logger.info(f"[{trace_id}] Updated risk settings for {risk_mode_str}")
            
            return Response({
                "status": "ok",
                "message": f"Risk settings updated for {risk_mode_str} mode"
            })
            
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to update risk settings: {e}")
            return Response({
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([AllowAny])
def intelligence_status(request) -> Response:
    """Get status of intelligence system components."""
    
    try:
        status_data = {
            "market_intelligence": {
                "enabled": market_intelligence.advanced_features_enabled,
                "cached_analyses": len(market_intelligence.analysis_cache)
            },
            "risk_manager": {
                "circuit_breaker_active": risk_manager.circuit_breaker_active,
                "daily_losses_tracked": len(risk_manager.daily_losses)
            },
            "strategy_engine": {
                "active_strategies": [s.value for s in strategy_engine.active_strategies],
                "signal_history_count": len(strategy_engine.signal_history)
            },
            "system_health": "operational"
        }
        
        return Response({
            "status": "ok",
            "intelligence": status_data
        })
        
    except Exception as e:
        logger.error(f"Failed to get intelligence status: {e}")
        return Response({
            "error": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)