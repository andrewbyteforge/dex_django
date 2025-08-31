from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
import requests
import web3
from dataclasses import dataclass

logger = logging.getLogger("intelligence")

@dataclass
class MarketAnalysis:
    """Market analysis result for a token pair."""
    pair_address: str
    chain: str
    liquidity_depth: Dict[str, float]
    honeypot_probability: float
    ownership_analysis: Dict[str, Any]
    tax_analysis: Dict[str, float]
    momentum_score: float
    social_sentiment: float
    whale_activity: Dict[str, Any]
    overall_risk_score: float  # 0-100, lower is better
    recommendation: str  # BUY, SELL, HOLD, AVOID
    # Enhanced fields
    advanced_risk_analysis: Optional[Dict[str, Any]] = None
    mempool_intelligence: Optional[Dict[str, Any]] = None

class MarketIntelligence:
    """Advanced market analysis and intelligence system."""
    
    def __init__(self):
        self.web3_connections = {}
        self.token_cache = {}
        self.analysis_cache = {}
        # Will be set to True once advanced modules are created
        self.advanced_features_enabled = False
    
    async def analyze_opportunity(
        self, 
        token_pair: Dict[str, Any], 
        trade_amount_eth: Decimal
    ) -> MarketAnalysis:
        """Comprehensive analysis of a trading opportunity."""
        
        pair_address = token_pair.get("pair_address", "")
        chain = token_pair.get("chain", "ethereum")
        
        logger.info(f"Analyzing opportunity: {pair_address} on {chain}")
        
        try:
            # Core analysis components (always run)
            liquidity_analysis = await self._analyze_liquidity_depth(token_pair, trade_amount_eth)
            honeypot_risk = await self._detect_honeypot_risk(token_pair)
            ownership_data = await self._analyze_token_ownership(token_pair)
            tax_data = await self._calculate_taxes(token_pair)
            momentum = await self._calculate_momentum(token_pair)
            sentiment = await self._analyze_social_sentiment(token_pair)
            whale_data = await self._detect_whale_activity(token_pair)
            
            # Advanced analysis components (if available)
            advanced_risk_data = None
            mempool_data = None
            
            if self.advanced_features_enabled:
                try:
                    # Import here to avoid circular imports and handle missing modules gracefully
                    from .advanced_risk_detection import advanced_risk_detector
                    from .mempool_analyzer import mempool_intelligence
                    
                    advanced_risk_data = await advanced_risk_detector.analyze_contract_bytecode(
                        pair_address, chain
                    )
                    mempool_data = await mempool_intelligence.analyze_pending_transactions(chain)
                    
                except ImportError as e:
                    logger.warning(f"Advanced features not available: {e}")
                    self.advanced_features_enabled = False
            
            # Calculate risk score (enhanced if advanced data available)
            if advanced_risk_data and mempool_data:
                risk_score = self._calculate_enhanced_risk_score({
                    'advanced_risk': advanced_risk_data,
                    'mempool': mempool_data,
                    'ownership': ownership_data,
                    'taxes': tax_data,
                    'liquidity': liquidity_analysis,
                    'momentum': momentum
                })
                
                recommendation = self._generate_enhanced_recommendation(
                    risk_score, liquidity_analysis, momentum, mempool_data
                )
            else:
                # Fall back to basic analysis
                risk_score = self._calculate_risk_score({
                    'honeypot': honeypot_risk,
                    'ownership': ownership_data,
                    'taxes': tax_data,
                    'liquidity': liquidity_analysis,
                    'momentum': momentum
                })
                
                recommendation = self._generate_recommendation(
                    risk_score, liquidity_analysis, momentum
                )
            
            analysis = MarketAnalysis(
                pair_address=pair_address,
                chain=chain,
                liquidity_depth=liquidity_analysis,
                honeypot_probability=honeypot_risk,
                ownership_analysis=ownership_data,
                tax_analysis=tax_data,
                momentum_score=momentum,
                social_sentiment=sentiment,
                whale_activity=whale_data,
                overall_risk_score=risk_score,
                recommendation=recommendation,
                advanced_risk_analysis=advanced_risk_data.__dict__ if advanced_risk_data else None,
                mempool_intelligence=mempool_data
            )
            
            logger.info(f"Analysis complete: {recommendation} (risk: {risk_score:.1f})")
            return analysis
            
        except Exception as e:
            logger.error(f"Analysis failed for {pair_address}: {e}")
            raise
    
    async def _analyze_liquidity_depth(
        self, 
        token_pair: Dict[str, Any], 
        trade_amount: Decimal
    ) -> Dict[str, float]:
        """Analyze liquidity depth and slippage for given trade size."""
        
        try:
            # Simulate the trade impact on price
            base_liquidity = token_pair.get("estimated_liquidity_usd", 0)
            
            # Calculate slippage estimates based on liquidity
            trade_usd = float(trade_amount) * 2000  # Rough ETH price
            
            if base_liquidity > 0:
                impact_ratio = trade_usd / base_liquidity
                
                # Slippage estimation formula (simplified)
                slippage_5pct = min(impact_ratio * 2.5, 0.5)  # Cap at 50%
                slippage_10pct = min(impact_ratio * 5.0, 0.8)  # Cap at 80%
                
                return {
                    "base_liquidity_usd": base_liquidity,
                    "trade_impact_ratio": impact_ratio,
                    "estimated_slippage_5pct": slippage_5pct,
                    "estimated_slippage_10pct": slippage_10pct,
                    "liquidity_rating": self._rate_liquidity(base_liquidity)
                }
            else:
                return {
                    "base_liquidity_usd": 0,
                    "trade_impact_ratio": 1.0,
                    "estimated_slippage_5pct": 0.5,
                    "estimated_slippage_10pct": 0.8,
                    "liquidity_rating": 0
                }
                
        except Exception as e:
            logger.error(f"Liquidity analysis failed: {e}")
            return {"error": str(e)}
    
    async def _detect_honeypot_risk(self, token_pair: Dict[str, Any]) -> float:
        """Detect honeypot/scam probability (0.0 = safe, 1.0 = definite scam)."""
        
        risk_factors = 0
        
        try:
            token0_symbol = token_pair.get("token0_symbol", "").upper()
            token1_symbol = token_pair.get("token1_symbol", "").upper()
            
            # Check 1: Suspicious token names
            suspicious_words = [
                "SAFE", "MOON", "ROCKET", "DIAMOND", "HANDS", "HODL", 
                "PUMP", "LAMBO", "RICH", "MILLIONAIRE", "BILLION"
            ]
            
            for word in suspicious_words:
                if word in token0_symbol or word in token1_symbol:
                    risk_factors += 0.3
                    break
            
            # Check 2: Very low liquidity
            liquidity = token_pair.get("estimated_liquidity_usd", 0)
            if liquidity < 1000:
                risk_factors += 0.4
            elif liquidity < 5000:
                risk_factors += 0.2
            
            # Check 3: New pair age (if available)
            try:
                timestamp = token_pair.get("timestamp", "")
                if timestamp:
                    pair_age = datetime.now() - datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    if pair_age < timedelta(minutes=30):
                        risk_factors += 0.2  # Very new pairs are riskier
            except:
                pass
            
            # Check 4: Source reliability
            source = token_pair.get("source", "")
            if source == "mock":
                risk_factors += 0.5
            elif source not in ["dexscreener", "uniswap_v3", "jupiter"]:
                risk_factors += 0.1
            
            # Normalize to 0-1 scale
            honeypot_risk = min(risk_factors, 1.0)
            
            logger.debug(f"Honeypot risk assessment: {honeypot_risk:.2f}")
            return honeypot_risk
            
        except Exception as e:
            logger.error(f"Honeypot detection failed: {e}")
            return 0.8  # Assume high risk on error
    
    async def _analyze_token_ownership(self, token_pair: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze token ownership distribution and contract properties."""
        
        # Mock implementation - in production, would analyze on-chain data
        return {
            "contract_verified": True,
            "ownership_renounced": False,
            "top_10_holders_percent": 45.2,
            "dev_wallet_balance_percent": 15.3,
            "locked_liquidity_percent": 80.0,
            "lock_duration_days": 365,
            "mint_function_present": False,
            "pause_function_present": False,
            "blacklist_function_present": False
        }
    
    async def _calculate_taxes(self, token_pair: Dict[str, Any]) -> Dict[str, float]:
        """Calculate buy/sell taxes for the token."""
        
        # Mock implementation - would simulate transactions to detect taxes
        return {
            "buy_tax_percent": 2.0,
            "sell_tax_percent": 3.0,
            "max_transaction_percent": 100.0,
            "max_wallet_percent": 100.0,
            "cooldown_period_seconds": 0,
            "anti_whale_mechanisms": False
        }
    
    async def _calculate_momentum(self, token_pair: Dict[str, Any]) -> float:
        """Calculate price momentum score (0-10)."""
        
        try:
            volume_24h = token_pair.get("volume_24h", 0)
            price_change_24h = token_pair.get("price_change_24h", 0)
            liquidity = token_pair.get("estimated_liquidity_usd", 0)
            
            momentum_score = 5.0  # Base score
            
            # Volume momentum
            if liquidity > 0:
                volume_ratio = volume_24h / liquidity
                if volume_ratio > 2.0:
                    momentum_score += 2.0
                elif volume_ratio > 1.0:
                    momentum_score += 1.0
                elif volume_ratio > 0.5:
                    momentum_score += 0.5
                else:
                    momentum_score -= 1.0
            
            # Price momentum
            if price_change_24h > 50:
                momentum_score += 2.0
            elif price_change_24h > 20:
                momentum_score += 1.0
            elif price_change_24h > 5:
                momentum_score += 0.5
            elif price_change_24h < -20:
                momentum_score -= 2.0
            elif price_change_24h < -10:
                momentum_score -= 1.0
            
            return max(0, min(10, momentum_score))
            
        except Exception as e:
            logger.error(f"Momentum calculation failed: {e}")
            return 5.0
    
    async def _analyze_social_sentiment(self, token_pair: Dict[str, Any]) -> float:
        """Analyze social media sentiment (0-10)."""
        return 6.0  # Mock neutral positive sentiment
    
    async def _detect_whale_activity(self, token_pair: Dict[str, Any]) -> Dict[str, Any]:
        """Detect large holder movements and whale activity."""
        return {
            "large_buys_24h": 2,
            "large_sells_24h": 1,
            "whale_accumulation_trend": "neutral",
            "average_large_transaction_usd": 25000,
            "whale_wallet_count": 5
        }
    
    def _calculate_risk_score(self, analysis_data: Dict[str, Any]) -> float:
        """Calculate basic risk score (0-100, lower is better)."""
        
        risk_score = 0.0
        
        # Honeypot risk (0-40 points)
        risk_score += analysis_data.get('honeypot', 0) * 40
        
        # Tax risk (0-20 points)
        taxes = analysis_data.get('taxes', {})
        total_tax = taxes.get('buy_tax_percent', 0) + taxes.get('sell_tax_percent', 0)
        risk_score += min(total_tax * 2, 20)
        
        # Liquidity risk (0-20 points)
        liquidity_data = analysis_data.get('liquidity', {})
        liquidity_rating = liquidity_data.get('liquidity_rating', 0)
        risk_score += (5 - liquidity_rating) * 4
        
        # Ownership risk (0-20 points)
        ownership = analysis_data.get('ownership', {})
        if not ownership.get('ownership_renounced', False):
            risk_score += 10
        if ownership.get('top_10_holders_percent', 0) > 70:
            risk_score += 10
        
        return min(risk_score, 100)
    
    def _calculate_enhanced_risk_score(self, analysis_data: Dict[str, Any]) -> float:
        """Calculate enhanced risk score using advanced intelligence."""
        
        # Start with basic risk score
        basic_risk = self._calculate_risk_score(analysis_data)
        
        # Add advanced risk factors
        advanced_risk = analysis_data.get('advanced_risk')
        if advanced_risk and hasattr(advanced_risk, 'risk_score'):
            # Weight: 60% basic analysis, 40% advanced analysis
            enhanced_score = (basic_risk * 0.6) + (advanced_risk.risk_score * 0.4)
        else:
            enhanced_score = basic_risk
        
        # Mempool intelligence adjustments
        mempool_data = analysis_data.get('mempool', {})
        if mempool_data:
            # High MEV activity increases risk
            mev_data = mempool_data.get('sandwich_attack_detection', {})
            if isinstance(mev_data, dict):
                competition_level = mev_data.get('mev_competition_level', 'low')
                if competition_level == 'high':
                    enhanced_score += 5
                elif competition_level == 'medium':
                    enhanced_score += 2
        
        return min(enhanced_score, 100)
    
    def _generate_recommendation(
        self, 
        risk_score: float, 
        liquidity_analysis: Dict[str, Any], 
        momentum: float
    ) -> str:
        """Generate basic trading recommendation."""
        
        if risk_score > 70:
            return "AVOID"
        elif risk_score > 50:
            return "HIGH_RISK"
        elif risk_score > 30:
            if momentum > 7 and liquidity_analysis.get('liquidity_rating', 0) >= 3:
                return "MODERATE_BUY"
            else:
                return "HOLD"
        else:
            if momentum > 6:
                return "BUY"
            else:
                return "HOLD"
    
    def _generate_enhanced_recommendation(
        self, 
        risk_score: float, 
        liquidity_analysis: Dict[str, Any], 
        momentum: float,
        mempool_data: Dict[str, Any]
    ) -> str:
        """Generate enhanced trading recommendation using mempool intelligence."""
        
        # Start with basic recommendation
        basic_rec = self._generate_recommendation(risk_score, liquidity_analysis, momentum)
        
        # Adjust based on mempool intelligence
        if basic_rec in ["BUY", "MODERATE_BUY"]:
            # Check for high bot competition
            bot_competition = mempool_data.get('bot_competition', [])
            if len(bot_competition) > 5:  # High competition
                if basic_rec == "BUY":
                    return "MODERATE_BUY"
                elif basic_rec == "MODERATE_BUY":
                    return "HOLD"
            
            # Check for upcoming liquidity events
            liquidity_events = mempool_data.get('large_liquidity_additions', [])
            if len(liquidity_events) > 0:
                return "STRONG_BUY"  # Enhanced recommendation
        
        return basic_rec
    
    def _rate_liquidity(self, liquidity_usd: float) -> int:
        """Rate liquidity on scale of 1-5."""
        if liquidity_usd >= 500000:
            return 5
        elif liquidity_usd >= 100000:
            return 4  
        elif liquidity_usd >= 50000:
            return 3
        elif liquidity_usd >= 10000:
            return 2
        else:
            return 1


# Global intelligence instance
market_intelligence = MarketIntelligence()