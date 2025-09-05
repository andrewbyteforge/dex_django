from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("intelligence.risk")

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    EXTREME = "extreme"

class TradingMode(Enum):
    PAPER = "paper"
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"

@dataclass
class RiskProfile:
    """User's risk tolerance and trading parameters."""
    max_daily_loss_usd: Decimal
    max_position_size_usd: Decimal
    max_portfolio_allocation_pct: Decimal
    max_slippage_pct: Decimal
    stop_loss_pct: Decimal
    take_profit_pct: Decimal
    trading_mode: TradingMode
    chains_enabled: List[str]
    min_liquidity_usd: Decimal

@dataclass
class PositionSizing:
    """Calculated position sizing for a trade."""
    recommended_amount_usd: Decimal
    max_safe_amount_usd: Decimal
    risk_adjusted_amount_usd: Decimal
    stop_loss_price: Decimal
    take_profit_price: Decimal
    max_acceptable_slippage: Decimal
    confidence_score: float
    risk_warnings: List[str]



@dataclass
class RiskGateResult:
    """Result of risk gate evaluation for copy trading."""
    passed: bool
    score: float  # 0.0 to 10.0, lower is safer
    reasons: List[str]
    warnings: List[str]
    max_position_usd: Decimal
    recommended_position_usd: Decimal
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    
    @property
    def risk_level(self) -> RiskLevel:
        """Convert numeric score to risk level enum."""
        if self.score <= 3.0:
            return RiskLevel.LOW
        elif self.score <= 5.0:
            return RiskLevel.MEDIUM
        elif self.score <= 7.0:
            return RiskLevel.HIGH
        else:
            return RiskLevel.EXTREME



class RiskManager:
    """Advanced risk management system for automated trading."""
    
    def __init__(self):
        self.daily_losses = {}
        self.active_positions = {}
        self.risk_events = []
        self.circuit_breaker_active = False
        
        # Default risk profiles
        self.risk_profiles = {
            TradingMode.PAPER: RiskProfile(
                max_daily_loss_usd=Decimal("0"),
                max_position_size_usd=Decimal("10000"),
                max_portfolio_allocation_pct=Decimal("5"),
                max_slippage_pct=Decimal("5"),
                stop_loss_pct=Decimal("10"),
                take_profit_pct=Decimal("25"),
                trading_mode=TradingMode.PAPER,
                chains_enabled=["ethereum", "bsc", "polygon", "base"],
                min_liquidity_usd=Decimal("10000")
            ),
            TradingMode.CONSERVATIVE: RiskProfile(
                max_daily_loss_usd=Decimal("100"),
                max_position_size_usd=Decimal("500"),
                max_portfolio_allocation_pct=Decimal("2"),
                max_slippage_pct=Decimal("3"),
                stop_loss_pct=Decimal("5"),
                take_profit_pct=Decimal("15"),
                trading_mode=TradingMode.CONSERVATIVE,
                chains_enabled=["ethereum", "base"],
                min_liquidity_usd=Decimal("50000")
            ),
            TradingMode.MODERATE: RiskProfile(
                max_daily_loss_usd=Decimal("500"),
                max_position_size_usd=Decimal("2000"),
                max_portfolio_allocation_pct=Decimal("5"),
                max_slippage_pct=Decimal("5"),
                stop_loss_pct=Decimal("8"),
                take_profit_pct=Decimal("20"),
                trading_mode=TradingMode.MODERATE,
                chains_enabled=["ethereum", "bsc", "polygon", "base"],
                min_liquidity_usd=Decimal("25000")
            ),
            TradingMode.AGGRESSIVE: RiskProfile(
                max_daily_loss_usd=Decimal("2000"),
                max_position_size_usd=Decimal("10000"),
                max_portfolio_allocation_pct=Decimal("10"),
                max_slippage_pct=Decimal("8"),
                stop_loss_pct=Decimal("12"),
                take_profit_pct=Decimal("30"),
                trading_mode=TradingMode.AGGRESSIVE,
                chains_enabled=["ethereum", "bsc", "polygon", "base", "arbitrum"],
                min_liquidity_usd=Decimal("10000")
            )
        }
    
    async def calculate_position_size(
        self,
        opportunity: Dict[str, Any],
        market_analysis: Any,
        user_balance_usd: Decimal,
        risk_mode: TradingMode = TradingMode.MODERATE
    ) -> PositionSizing:
        """Calculate optimal position size with comprehensive risk management."""
        
        logger.info(f"Calculating position size for {opportunity.get('pair_address', 'unknown')}")
        
        try:
            profile = self.risk_profiles[risk_mode]
            
            # Base position sizing calculations
            base_amount = await self._calculate_base_position_size(
                opportunity, market_analysis, user_balance_usd, profile
            )
            
            # Risk adjustments
            risk_adjusted_amount = await self._apply_risk_adjustments(
                base_amount, opportunity, market_analysis, profile
            )
            
            # Liquidity constraints
            liquidity_adjusted_amount = await self._apply_liquidity_constraints(
                risk_adjusted_amount, opportunity, profile
            )
            
            # Daily loss limits
            loss_limit_adjusted_amount = await self._apply_daily_loss_limits(
                liquidity_adjusted_amount, profile, risk_mode
            )
            
            # Calculate stop loss and take profit
            entry_price = Decimal(str(opportunity.get("price_usd", 1)))
            stop_loss_price = entry_price * (1 - profile.stop_loss_pct / 100)
            take_profit_price = entry_price * (1 + profile.take_profit_pct / 100)
            
            # Collect warnings
            warnings = await self._generate_risk_warnings(
                opportunity, market_analysis, loss_limit_adjusted_amount, profile
            )
            
            # Calculate confidence based on analysis quality
            confidence = self._calculate_confidence_score(market_analysis, opportunity)
            
            return PositionSizing(
                recommended_amount_usd=loss_limit_adjusted_amount,
                max_safe_amount_usd=base_amount,
                risk_adjusted_amount_usd=risk_adjusted_amount,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                max_acceptable_slippage=profile.max_slippage_pct,
                confidence_score=confidence,
                risk_warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"Position sizing calculation failed: {e}")
            # Return minimal position on error
            return PositionSizing(
                recommended_amount_usd=Decimal("10"),
                max_safe_amount_usd=Decimal("10"),
                risk_adjusted_amount_usd=Decimal("10"),
                stop_loss_price=Decimal("0"),
                take_profit_price=Decimal("0"),
                max_acceptable_slippage=Decimal("1"),
                confidence_score=0.1,
                risk_warnings=["Risk calculation failed - using minimal position"]
            )
        
    async def evaluate_risk_gates(
        self,
        opportunity: Dict[str, Any],
        trader_config: Dict[str, Any],
        market_analysis: Any = None
    ) -> RiskGateResult:
        """Evaluate if trade passes risk gates for copy trading."""
        
        reasons = []
        warnings = []
        score = 0.0
        
        # Basic validation
        if not opportunity.get("estimated_liquidity_usd", 0):
            return RiskGateResult(
                passed=False,
                score=10.0,
                reasons=["No liquidity data available"],
                warnings=[],
                max_position_usd=Decimal("0"),
                recommended_position_usd=Decimal("0")
            )
        
        # Calculate position sizing
        risk_mode = TradingMode.MODERATE  # Default
        user_balance = Decimal("10000")  # Mock balance
        
        position_sizing = await self.calculate_position_size(
            opportunity, market_analysis, user_balance, risk_mode
        )
        
        # Determine if trade passes
        passed = (
            position_sizing.recommended_amount_usd > 0 and
            position_sizing.confidence_score > 0.3 and
            len(position_sizing.risk_warnings) < 3
        )
        
        return RiskGateResult(
            passed=passed,
            score=max(0.0, 10.0 - position_sizing.confidence_score * 10),
            reasons=reasons,
            warnings=position_sizing.risk_warnings,
            max_position_usd=position_sizing.max_safe_amount_usd,
            recommended_position_usd=position_sizing.recommended_amount_usd,
            stop_loss_price=position_sizing.stop_loss_price,
            take_profit_price=position_sizing.take_profit_price
        )
    
    async def _calculate_base_position_size(
        self,
        opportunity: Dict[str, Any],
        market_analysis: Any,
        user_balance_usd: Decimal,
        profile: RiskProfile
    ) -> Decimal:
        """Calculate base position size before risk adjustments."""
        
        # Start with maximum allowed position size
        max_position = min(
            profile.max_position_size_usd,
            user_balance_usd * profile.max_portfolio_allocation_pct / 100
        )
        
        # Adjust based on liquidity available
        liquidity_usd = Decimal(str(opportunity.get("estimated_liquidity_usd", 0)))
        
        if liquidity_usd > 0:
            # Never trade more than 10% of available liquidity to minimize slippage
            liquidity_limit = liquidity_usd * Decimal("0.1")
            max_position = min(max_position, liquidity_limit)
        
        return max_position
    
    async def _apply_risk_adjustments(
        self,
        base_amount: Decimal,
        opportunity: Dict[str, Any],
        market_analysis: Any,
        profile: RiskProfile
    ) -> Decimal:
        """Apply risk-based position size adjustments."""
        
        risk_multiplier = Decimal("1.0")
        
        # Adjust based on overall risk score
        if hasattr(market_analysis, 'overall_risk_score'):
            risk_score = market_analysis.overall_risk_score
            
            if risk_score > 70:  # High risk
                risk_multiplier *= Decimal("0.3")
            elif risk_score > 50:  # Medium risk
                risk_multiplier *= Decimal("0.6")
            elif risk_score > 30:  # Low-medium risk
                risk_multiplier *= Decimal("0.8")
            # Low risk (<=30) keeps full multiplier
        
        # Adjust based on momentum
        if hasattr(market_analysis, 'momentum_score'):
            momentum = market_analysis.momentum_score
            
            if momentum > 8:  # Very bullish
                risk_multiplier *= Decimal("1.2")
            elif momentum > 6:  # Bullish
                risk_multiplier *= Decimal("1.1")
            elif momentum < 3:  # Very bearish
                risk_multiplier *= Decimal("0.5")
            elif momentum < 5:  # Bearish
                risk_multiplier *= Decimal("0.7")
        
        # Adjust based on chain risk
        chain = opportunity.get("chain", "ethereum")
        chain_multipliers = {
            "ethereum": Decimal("1.0"),
            "base": Decimal("0.9"),
            "polygon": Decimal("0.8"),
            "bsc": Decimal("0.7"),
            "arbitrum": Decimal("0.8")
        }
        risk_multiplier *= chain_multipliers.get(chain, Decimal("0.6"))
        
        return (base_amount * risk_multiplier).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    
    async def _apply_liquidity_constraints(
        self,
        amount: Decimal,
        opportunity: Dict[str, Any],
        profile: RiskProfile
    ) -> Decimal:
        """Ensure position size doesn't exceed liquidity constraints."""
        
        liquidity_usd = Decimal(str(opportunity.get("estimated_liquidity_usd", 0)))
        
        # Check minimum liquidity requirement
        if liquidity_usd < profile.min_liquidity_usd:
            logger.warning(f"Liquidity ${liquidity_usd} below minimum ${profile.min_liquidity_usd}")
            return Decimal("0")  # Don't trade
        
        # Limit to percentage of available liquidity to control slippage
        max_liquidity_usage = liquidity_usd * Decimal("0.05")  # Max 5% of liquidity
        
        return min(amount, max_liquidity_usage)
    
    async def _apply_daily_loss_limits(
        self,
        amount: Decimal,
        profile: RiskProfile,
        risk_mode: TradingMode
    ) -> Decimal:
        """Apply daily loss limits and circuit breakers."""
        
        today = datetime.now().date()
        daily_loss = self.daily_losses.get((today, risk_mode), Decimal("0"))
        
        # Check if daily loss limit exceeded
        if daily_loss >= profile.max_daily_loss_usd:
            logger.warning(f"Daily loss limit exceeded: ${daily_loss}")
            return Decimal("0")  # Don't trade
        
        # Reduce position size based on existing losses
        remaining_budget = profile.max_daily_loss_usd - daily_loss
        potential_loss = amount * profile.stop_loss_pct / 100
        
        if potential_loss > remaining_budget:
            # Scale down position to fit remaining budget
            adjusted_amount = remaining_budget * 100 / profile.stop_loss_pct
            logger.info(f"Position scaled down due to daily loss limits: ${amount} -> ${adjusted_amount}")
            return adjusted_amount
        
        return amount
    
    async def _generate_risk_warnings(
        self,
        opportunity: Dict[str, Any],
        market_analysis: Any,
        position_size: Decimal,
        profile: RiskProfile
    ) -> List[str]:
        """Generate risk warnings for the trade."""
        
        warnings = []
        
        # Risk score warnings
        if hasattr(market_analysis, 'overall_risk_score'):
            risk_score = market_analysis.overall_risk_score
            
            if risk_score > 70:
                warnings.append("HIGH RISK: Overall risk score above 70")
            elif risk_score > 50:
                warnings.append("MEDIUM RISK: Elevated risk factors detected")
        
        # Liquidity warnings
        liquidity_usd = Decimal(str(opportunity.get("estimated_liquidity_usd", 0)))
        if position_size > liquidity_usd * Decimal("0.1"):
            warnings.append("HIGH SLIPPAGE: Position size large relative to liquidity")
        
        # New token warnings
        try:
            timestamp = opportunity.get("timestamp", "")
            if timestamp:
                pair_age = datetime.now() - datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if pair_age < timedelta(hours=24):
                    warnings.append("NEW TOKEN: Less than 24 hours old")
        except:
            pass
        
        # Chain-specific warnings
        chain = opportunity.get("chain", "ethereum")
        if chain not in profile.chains_enabled:
            warnings.append(f"CHAIN WARNING: {chain} not in enabled chains")
        
        # Advanced risk warnings from bytecode analysis
        if hasattr(market_analysis, 'advanced_risk_analysis') and market_analysis.advanced_risk_analysis:
            advanced_risk = market_analysis.advanced_risk_analysis
            
            if advanced_risk.get('bytecode_analysis', {}).get('has_selfdestruct', False):
                warnings.append("CONTRACT RISK: Self-destruct function detected")
            
            if advanced_risk.get('social_patterns', {}).get('fake_volume_patterns', 0) > 0.5:
                warnings.append("MANIPULATION: Potential wash trading detected")
        
        return warnings
    
    def _calculate_confidence_score(self, market_analysis: Any, opportunity: Dict[str, Any]) -> float:
        """Calculate confidence score for the trade recommendation."""
        
        confidence = 0.5  # Base confidence
        
        # Boost confidence for verified contracts and good liquidity
        if hasattr(market_analysis, 'ownership_analysis'):
            ownership = market_analysis.ownership_analysis
            if ownership.get('contract_verified', False):
                confidence += 0.1
            if ownership.get('ownership_renounced', False):
                confidence += 0.1
        
        # Boost for good liquidity
        liquidity = opportunity.get("estimated_liquidity_usd", 0)
        if liquidity > 100000:
            confidence += 0.15
        elif liquidity > 50000:
            confidence += 0.1
        elif liquidity > 10000:
            confidence += 0.05
        
        # Reduce confidence for high risk
        if hasattr(market_analysis, 'overall_risk_score'):
            risk_score = market_analysis.overall_risk_score
            if risk_score > 70:
                confidence -= 0.3
            elif risk_score > 50:
                confidence -= 0.2
            elif risk_score > 30:
                confidence -= 0.1
        
        # Boost for reliable data sources
        source = opportunity.get("source", "")
        if source in ["dexscreener", "uniswap_v3", "jupiter"]:
            confidence += 0.05
        
        return max(0.1, min(0.95, confidence))  # Clamp between 10% and 95%
    
    async def record_trade_result(
        self,
        risk_mode: TradingMode,
        amount_usd: Decimal,
        pnl_usd: Decimal
    ) -> None:
        """Record trade result for daily loss tracking."""
        
        today = datetime.now().date()
        
        if pnl_usd < 0:  # Only track losses
            current_loss = self.daily_losses.get((today, risk_mode), Decimal("0"))
            self.daily_losses[(today, risk_mode)] = current_loss + abs(pnl_usd)
            
            logger.info(f"Recorded loss: ${abs(pnl_usd)}, Daily total: ${self.daily_losses[(today, risk_mode)]}")
    
    async def check_circuit_breaker(self, risk_mode: TradingMode) -> bool:
        """Check if circuit breaker should halt trading."""
        
        profile = self.risk_profiles[risk_mode]
        today = datetime.now().date()
        daily_loss = self.daily_losses.get((today, risk_mode), Decimal("0"))
        
        # Halt if daily loss limit exceeded
        if daily_loss >= profile.max_daily_loss_usd:
            self.circuit_breaker_active = True
            logger.warning(f"Circuit breaker activated: Daily loss ${daily_loss} >= limit ${profile.max_daily_loss_usd}")
            return True
        
        # Check for rapid consecutive losses (additional safety)
        recent_losses = [event for event in self.risk_events 
                        if event.get('timestamp', datetime.min) > datetime.now() - timedelta(hours=1)
                        and event.get('pnl', 0) < 0]
        
        if len(recent_losses) >= 5:  # 5 losses in 1 hour
            self.circuit_breaker_active = True
            logger.warning("Circuit breaker activated: 5 consecutive losses in 1 hour")
            return True
        
        return False


# Global risk manager instance
risk_manager = RiskManager()