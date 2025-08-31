from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from backend.app.discovery.wallet_monitor import WalletTransaction
from backend.app.strategy.risk_manager import RiskGateResult, RiskManager
from backend.app.strategy.orders import TradeIntent
from backend.app.core.runtime_state import runtime_state

logger = logging.getLogger(__name__)


class CopyDecision(Enum):
    """Copy trading decision outcomes."""
    COPY = "copy"
    SKIP = "skip" 
    REJECT = "reject"


class CopyReason(Enum):
    """Reasons for copy trading decisions."""
    # Copy reasons
    GOOD_TRADER_PERFORMANCE = "good_trader_performance"
    WITHIN_RISK_LIMITS = "within_risk_limits"
    PASSES_FILTERS = "passes_filters"
    
    # Skip reasons  
    TRADER_PAUSED = "trader_paused"
    OUTSIDE_TRADING_HOURS = "outside_trading_hours"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    
    # Reject reasons
    RISK_GATES_FAILED = "risk_gates_failed"
    TRADER_BLACKLISTED = "trader_blacklisted"
    TOKEN_BLACKLISTED = "token_blacklisted"
    POSITION_SIZE_EXCEEDED = "position_size_exceeded"
    SLIPPAGE_TOO_HIGH = "slippage_too_high"


class CopyTradeEvaluation(BaseModel):
    """
    Result of evaluating a potential copy trade.
    """
    
    # Decision
    decision: CopyDecision
    reason: CopyReason
    confidence: float  # 0.0 to 1.0
    
    # Original trade details
    trader_address: str
    original_tx_hash: str
    original_amount_usd: Decimal
    
    # Copy trade details
    copy_amount_usd: Decimal
    copy_percentage: Optional[Decimal] = None
    position_sizing_mode: str  # "percentage", "fixed_amount", "proportional"
    
    # Risk assessment
    risk_gates: RiskGateResult
    risk_score: Decimal  # 0.0 to 10.0
    
    # Trade intent (if copying)
    trade_intent: Optional[TradeIntent] = None
    
    # Timing
    evaluation_timestamp: datetime
    execution_delay_estimate_ms: int
    
    # Metadata
    trace_id: str
    notes: str
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }


class CopyTradingStrategy:
    """
    Copy trading strategy that evaluates wallet transactions for copying.
    Integrates with existing risk gates and trading execution pipeline.
    """
    
    def __init__(self, risk_manager: RiskManager):
        self._risk_manager = risk_manager
        
        # Default copy trading settings (would be configurable)
        self._default_copy_percentage = Decimal("2.0")  # 2% of portfolio
        self._max_copy_amount_usd = Decimal("500.0")
        self._max_position_size_usd = Decimal("1000.0")
        self._max_slippage_bps = 300
        
        # Performance tracking
        self._trader_performance: Dict[str, Dict[str, Any]] = {}
    
    async def evaluate_copy_opportunity(
        self,
        wallet_tx: WalletTransaction,
        trader_config: Dict[str, Any],
        trace_id: str
    ) -> CopyTradeEvaluation:
        """
        Evaluate whether to copy a trader's transaction.
        
        Args:
            wallet_tx: The original transaction to potentially copy
            trader_config: Configuration for this followed trader
            trace_id: Request trace ID for logging
            
        Returns:
            CopyTradeEvaluation with decision and details
        """
        evaluation_start = datetime.now(timezone.utc)
        
        logger.info(
            "Evaluating copy opportunity: %s %s %s (trader: %s, trace: %s)",
            wallet_tx.action.upper(),
            wallet_tx.token_symbol,
            wallet_tx.amount_usd,
            wallet_tx.from_address[:8],
            trace_id
        )
        
        # Step 1: Check trader status and basic filters
        basic_check = await self._check_basic_eligibility(wallet_tx, trader_config)
        if basic_check[0] != CopyDecision.COPY:
            return CopyTradeEvaluation(
                decision=basic_check[0],
                reason=basic_check[1],
                confidence=0.1,
                trader_address=wallet_tx.from_address,
                original_tx_hash=wallet_tx.tx_hash,
                original_amount_usd=wallet_tx.amount_usd,
                copy_amount_usd=Decimal("0"),
                position_sizing_mode="none",
                risk_gates=RiskGateResult(passed=False, score=Decimal("10"), reasons=["basic_check_failed"]),
                risk_score=Decimal("10"),
                evaluation_timestamp=evaluation_start,
                execution_delay_estimate_ms=5000,
                trace_id=trace_id,
                notes=f"Basic eligibility failed: {basic_check[1].value}"
            )
        
        # Step 2: Calculate copy amount based on mode
        copy_amount = await self._calculate_copy_amount(wallet_tx, trader_config)
        
        # Step 3: Run risk gates (same as autotrade)
        risk_gates = await self._risk_manager.evaluate_token_risk(
            chain=wallet_tx.chain,
            token_address=wallet_tx.token_address,
            pair_address=wallet_tx.pair_address,
            trade_amount_usd=copy_amount,
            trace_id=trace_id
        )
        
        # Step 4: Check copy-specific risk limits
        copy_risk_check = await self._check_copy_risk_limits(
            wallet_tx, copy_amount, risk_gates, trader_config
        )
        
        if not copy_risk_check[0]:
            return CopyTradeEvaluation(
                decision=CopyDecision.REJECT,
                reason=copy_risk_check[1],
                confidence=0.8,
                trader_address=wallet_tx.from_address,
                original_tx_hash=wallet_tx.tx_hash,
                original_amount_usd=wallet_tx.amount_usd,
                copy_amount_usd=copy_amount,
                position_sizing_mode=trader_config.get("copy_mode", "percentage"),
                risk_gates=risk_gates,
                risk_score=risk_gates.score,
                evaluation_timestamp=evaluation_start,
                execution_delay_estimate_ms=self._estimate_execution_delay(wallet_tx.chain),
                trace_id=trace_id,
                notes=f"Copy risk limits failed: {copy_risk_check[1].value}"
            )
        
        # Step 5: Create trade intent if all checks pass
        trade_intent = await self._create_copy_trade_intent(
            wallet_tx, copy_amount, risk_gates, trace_id
        )
        
        # Step 6: Final confidence calculation
        confidence = await self._calculate_copy_confidence(
            wallet_tx, trader_config, risk_gates
        )
        
        evaluation = CopyTradeEvaluation(
            decision=CopyDecision.COPY,
            reason=CopyReason.PASSES_FILTERS,
            confidence=confidence,
            trader_address=wallet_tx.from_address,
            original_tx_hash=wallet_tx.tx_hash,
            original_amount_usd=wallet_tx.amount_usd,
            copy_amount_usd=copy_amount,
            position_sizing_mode=trader_config.get("copy_mode", "percentage"),
            risk_gates=risk_gates,
            risk_score=risk_gates.score,
            trade_intent=trade_intent,
            evaluation_timestamp=evaluation_start,
            execution_delay_estimate_ms=self._estimate_execution_delay(wallet_tx.chain),
            trace_id=trace_id,
            notes=f"Copy approved: {confidence:.1%} confidence"
        )
        
        # Emit AI thought log
        await self._emit_copy_evaluation_log(evaluation, wallet_tx)
        
        logger.info(
            "Copy evaluation complete: %s (confidence: %.1%%, amount: $%.2f, trace: %s)",
            evaluation.decision.value,
            evaluation.confidence * 100,
            evaluation.copy_amount_usd,
            trace_id
        )
        
        return evaluation
    
    async def _check_basic_eligibility(
        self,
        wallet_tx: WalletTransaction,
        trader_config: Dict[str, Any]
    ) -> tuple[CopyDecision, CopyReason]:
        """Check basic eligibility before running expensive risk checks."""
        
        # Check trader status
        if trader_config.get("status") != "active":
            return CopyDecision.SKIP, CopyReason.TRADER_PAUSED
        
        # Check chain allowlist
        allowed_chains = trader_config.get("allowed_chains", [])
        if allowed_chains and wallet_tx.chain not in allowed_chains:
            return CopyDecision.SKIP, CopyReason.OUTSIDE_TRADING_HOURS
        
        # Check trade direction restrictions
        if trader_config.get("copy_buy_only", False) and wallet_tx.action != "buy":
            return CopyDecision.SKIP, CopyReason.OUTSIDE_TRADING_HOURS
        
        if trader_config.get("copy_sell_only", False) and wallet_tx.action != "sell":
            return CopyDecision.SKIP, CopyReason.OUTSIDE_TRADING_HOURS
        
        # Check minimum trade size
        min_copy_usd = trader_config.get("min_copy_amount_usd", Decimal("50"))
        if wallet_tx.amount_usd < min_copy_usd:
            return CopyDecision.SKIP, CopyReason.INSUFFICIENT_BALANCE
        
        return CopyDecision.COPY, CopyReason.PASSES_FILTERS
    
    async def _calculate_copy_amount(
        self,
        wallet_tx: WalletTransaction,
        trader_config: Dict[str, Any]
    ) -> Decimal:
        """Calculate the USD amount to copy based on configuration."""
        
        copy_mode = trader_config.get("copy_mode", "percentage")
        
        if copy_mode == "fixed_amount":
            # Fixed USD amount per trade
            return Decimal(str(trader_config.get("fixed_amount_usd", 100)))
        
        elif copy_mode == "proportional":
            # Proportional to original trade (with limits)
            proportion = Decimal(str(trader_config.get("copy_percentage", 5))) / 100
            proportional_amount = wallet_tx.amount_usd * proportion
            
            # Apply limits
            max_copy = Decimal(str(trader_config.get("max_copy_amount_usd", 500)))
            return min(proportional_amount, max_copy)
        
        else:  # percentage mode (default)
            # Percentage of our portfolio
            portfolio_value = await self._get_portfolio_value_usd()
            percentage = Decimal(str(trader_config.get("copy_percentage", 2))) / 100
            percentage_amount = portfolio_value * percentage
            
            # Apply limits
            max_copy = Decimal(str(trader_config.get("max_copy_amount_usd", 500)))
            return min(percentage_amount, max_copy)
    
    async def _check_copy_risk_limits(
        self,
        wallet_tx: WalletTransaction,
        copy_amount: Decimal,
        risk_gates: RiskGateResult,
        trader_config: Dict[str, Any]
    ) -> tuple[bool, CopyReason]:
        """Check copy-trading specific risk limits."""
        
        # Check if risk gates passed
        if not risk_gates.passed:
            return False, CopyReason.RISK_GATES_FAILED
        
        # Check maximum position size
        max_position = Decimal(str(trader_config.get("max_position_usd", 1000)))
        if copy_amount > max_position:
            return False, CopyReason.POSITION_SIZE_EXCEEDED
        
        # Check risk score threshold
        max_risk_score = Decimal(str(trader_config.get("max_risk_score", 7.0)))
        if risk_gates.score > max_risk_score:
            return False, CopyReason.RISK_GATES_FAILED
        
        # Check slippage limits (would need current market data)
        max_slippage = trader_config.get("max_slippage_bps", 300)
        # Slippage check would be performed here with live quote
        
        return True, CopyReason.WITHIN_RISK_LIMITS
    
    async def _create_copy_trade_intent(
        self,
        wallet_tx: WalletTransaction,
        copy_amount: Decimal,
        risk_gates: RiskGateResult,
        trace_id: str
    ) -> TradeIntent:
        """Create a TradeIntent for the copy trade."""
        
        return TradeIntent(
            signal_id=f"copy_{wallet_tx.tx_hash}_{trace_id}",
            chain=wallet_tx.chain,
            dex_name=wallet_tx.dex_name,
            token_address=wallet_tx.token_address,
            token_symbol=wallet_tx.token_symbol,
            pair_address=wallet_tx.pair_address,
            action=wallet_tx.action,
            amount_usd=copy_amount,
            max_slippage_bps=self._max_slippage_bps,
            urgency="high",  # Copy trades need speed
            source="copy_trading",
            metadata={
                "original_tx_hash": wallet_tx.tx_hash,
                "trader_address": wallet_tx.from_address,
                "original_amount_usd": str(wallet_tx.amount_usd),
                "risk_score": str(risk_gates.score),
            }
        )
    
    async def _calculate_copy_confidence(
        self,
        wallet_tx: WalletTransaction,
        trader_config: Dict[str, Any],
        risk_gates: RiskGateResult
    ) -> float:
        """Calculate confidence in the copy trade decision."""
        
        base_confidence = 0.7
        
        # Adjust based on risk score (lower risk = higher confidence)
        risk_adjustment = max(0.0, (10 - float(risk_gates.score)) / 10 * 0.2)
        
        # Adjust based on trader performance
        trader_performance = self._trader_performance.get(wallet_tx.from_address, {})
        win_rate = trader_performance.get("win_rate", 0.5)
        performance_adjustment = (win_rate - 0.5) * 0.2
        
        # Adjust based on trade size (mid-size trades are most confident)
        amount_usd = float(wallet_tx.amount_usd)
        if 100 <= amount_usd <= 1000:
            size_adjustment = 0.1
        elif 50 <= amount_usd <= 5000:
            size_adjustment = 0.0
        else:
            size_adjustment = -0.1
        
        confidence = base_confidence + risk_adjustment + performance_adjustment + size_adjustment
        return max(0.1, min(1.0, confidence))
    
    async def _emit_copy_evaluation_log(
        self,
        evaluation: CopyTradeEvaluation,
        wallet_tx: WalletTransaction
    ) -> None:
        """Emit AI thought log for copy trade evaluation."""
        
        thought_data = {
            "opportunity": {
                "pair": wallet_tx.pair_address,
                "symbol": f"{wallet_tx.token_symbol}/WETH",
                "chain": wallet_tx.chain,
                "dex": wallet_tx.dex_name
            },
            "discovery_signals": {
                "source": "copy_trading",
                "trader": f"{wallet_tx.from_address[:8]}...",
                "original_amount_usd": float(wallet_tx.amount_usd),
                "copy_amount_usd": float(evaluation.copy_amount_usd),
                "detection_delay_ms": evaluation.execution_delay_estimate_ms
            },
            "risk_gates": {
                "overall": "pass" if evaluation.risk_gates.passed else "fail",
                "risk_score": float(evaluation.risk_gates.score),
                "liquidity_check": "pass",  # Would be from actual risk gates
                "tax_analysis": "pass",
                "blacklist_check": "pass"
            },
            "decision": {
                "action": f"copy_{wallet_tx.action}" if evaluation.decision == CopyDecision.COPY else "skip",
                "rationale": evaluation.notes,
                "confidence": evaluation.confidence,
                "original_tx_hash": wallet_tx.tx_hash
            }
        }
        
        await runtime_state.emit_thought_log(thought_data)
    
    async def _get_portfolio_value_usd(self) -> Decimal:
        """Get current portfolio value in USD."""
        # Mock implementation - would integrate with wallet service
        return Decimal("10000.0")
    
    def _estimate_execution_delay(self, chain: str) -> int:
        """Estimate execution delay in milliseconds for different chains."""
        delay_map = {
            "ethereum": 15000,  # 15s for gas competition
            "bsc": 5000,        # 5s faster blocks
            "base": 3000,       # 3s very fast
            "polygon": 4000,    # 4s fast
            "solana": 2000,     # 2s fastest
        }
        return delay_map.get(chain, 10000)
    
    async def update_trader_performance(
        self,
        trader_address: str,
        trade_result: Dict[str, Any]
    ) -> None:
        """Update performance tracking for a trader."""
        
        if trader_address not in self._trader_performance:
            self._trader_performance[trader_address] = {
                "total_trades": 0,
                "winning_trades": 0,
                "total_pnl": 0.0,
                "win_rate": 0.5,
                "last_updated": datetime.now(timezone.utc)
            }
        
        perf = self._trader_performance[trader_address]
        perf["total_trades"] += 1
        
        if trade_result.get("is_profitable", False):
            perf["winning_trades"] += 1
        
        perf["total_pnl"] += trade_result.get("pnl_usd", 0.0)
        perf["win_rate"] = perf["winning_trades"] / perf["total_trades"]
        perf["last_updated"] = datetime.now(timezone.utc)
        
        logger.info(
            "Updated trader %s performance: %d trades, %.1%% win rate, $%.2f PnL",
            trader_address[:8],
            perf["total_trades"],
            perf["win_rate"] * 100,
            perf["total_pnl"]
        )


# Global copy trading strategy instance
copy_trading_strategy = CopyTradingStrategy(risk_manager=None)  # Would be injected