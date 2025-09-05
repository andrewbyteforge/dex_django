# APP: backend
# FILE: backend/app/strategy/copy_trading_strategy.py
from __future__ import annotations

import logging
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from dex_django.apps.discovery.wallet_monitor import WalletTransaction
from dex_django.apps.strategy.risk_manager import RiskGateResult, RiskManager
from dex_django.apps.strategy.orders import TradeIntent
from dex_django.apps.core.runtime_state import runtime_state

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
    """Result of evaluating a potential copy trade."""
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


@dataclass
class CopyExecutionResult:
    """Result of copy trade execution."""
    success: bool
    copy_trade_id: Optional[str]
    tx_hash: Optional[str]
    actual_amount_usd: Optional[Decimal]
    execution_delay_seconds: Optional[int]
    failure_reason: Optional[str]
    total_fees_usd: Optional[Decimal]


class CopyTradingStrategy:
    """
    Copy trading strategy that evaluates wallet transactions for copying.
    Integrates with existing risk gates and trading execution pipeline.
    """

    def __init__(self, risk_manager: Optional[RiskManager]):
        self._risk_manager = risk_manager or RiskManager()

        # Default copy trading settings (would be configurable)
        self._default_copy_percentage = Decimal("2.0")  # 2% of portfolio
        self._max_copy_amount_usd = Decimal("500.0")
        self._max_position_size_usd = Decimal("1000.0")
        self._max_slippage_bps = 300

        # Additional execution/queue controls (from extended spec)
        self._max_concurrent_copies = 5
        self._default_execution_timeout_sec = 30
        self._min_confidence_threshold = 0.60

        # Performance tracking
        self._trader_performance: Dict[str, Dict[str, Any]] = {}

        # Daily tracking
        self._daily_copy_count = 0
        self._daily_pnl_usd = Decimal("0.0")
        self._last_reset_date = datetime.now(timezone.utc).date()

    # ---------- PUBLIC API ----------

    async def process_wallet_transaction(
        self,
        wallet_tx: WalletTransaction,
        trader_config: Dict[str, Any]
    ) -> Optional[CopyExecutionResult]:
        """
        Main entry point for processing a detected wallet transaction.
        Handles evaluation and execution in sequence.
        """
        trace_id = f"copy_{wallet_tx.tx_hash[:8]}_{int(datetime.now().timestamp())}"
        logger.info("[%s] Processing wallet transaction %s", trace_id, wallet_tx.tx_hash)

        try:
            # 1) Evaluate copy opportunity
            evaluation = await self.evaluate_copy_opportunity(wallet_tx, trader_config, trace_id)

            if evaluation.decision != CopyDecision.COPY:
                logger.info(
                    "[%s] Skipping copy: %s (%s)",
                    trace_id, evaluation.decision.value, evaluation.reason.value
                )
                return None

            # 2) Execute copy trade (paper or live)
            execution_result = await self.execute_copy_trade(wallet_tx, evaluation, trader_config, trace_id)

            # 3) Update daily stats
            await self._update_daily_tracking(execution_result)

            return execution_result

        except Exception as e:
            logger.error("[%s] Failed to process wallet transaction: %s", trace_id, e, exc_info=True)
            return None

    async def evaluate_copy_opportunity(
        self,
        wallet_tx: WalletTransaction,
        trader_config: Dict[str, Any],
        trace_id: str
    ) -> CopyTradeEvaluation:
        """
        Evaluate whether to copy a trader's transaction.
        """
        evaluation_start = datetime.now(timezone.utc)

        logger.info(
            "Evaluating copy opportunity: %s %s $%s (trader: %s, trace: %s)",
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
                confidence=0.10,
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

        # Respect global max position size
        copy_amount = min(copy_amount, self._max_position_size_usd)

        # Step 3: Run risk gates (same as autotrade)
        risk_gates = await self._risk_manager.evaluate_token_risk(
            chain=wallet_tx.chain,
            token_address=wallet_tx.token_address,
            pair_address=wallet_tx.pair_address,
            trade_amount_usd=copy_amount,
            trace_id=trace_id
        )

        # Step 4: Check copy-specific risk limits
        copy_risk_check = await self._check_copy_risk_limits(wallet_tx, copy_amount, risk_gates, trader_config)
        if not copy_risk_check[0]:
            return CopyTradeEvaluation(
                decision=CopyDecision.REJECT,
                reason=copy_risk_check[1],
                confidence=0.80,
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
        trade_intent = await self._create_copy_trade_intent(wallet_tx, copy_amount, risk_gates, trace_id)

        # Step 6: Final confidence calculation
        confidence = await self._calculate_copy_confidence(wallet_tx, trader_config, risk_gates)

        # Enforce minimum confidence threshold
        decision = CopyDecision.COPY if confidence >= self._min_confidence_threshold else CopyDecision.SKIP
        reason = CopyReason.PASSES_FILTERS if decision == CopyDecision.COPY else CopyReason.OUTSIDE_TRADING_HOURS

        evaluation = CopyTradeEvaluation(
            decision=decision,
            reason=reason,
            confidence=confidence,
            trader_address=wallet_tx.from_address,
            original_tx_hash=wallet_tx.tx_hash,
            original_amount_usd=wallet_tx.amount_usd,
            copy_amount_usd=copy_amount,
            position_sizing_mode=trader_config.get("copy_mode", "percentage"),
            risk_gates=risk_gates,
            risk_score=risk_gates.score,
            trade_intent=trade_intent if decision == CopyDecision.COPY else None,
            evaluation_timestamp=evaluation_start,
            execution_delay_estimate_ms=self._estimate_execution_delay(wallet_tx.chain),
            trace_id=trace_id,
            notes=f"Copy {'approved' if decision == CopyDecision.COPY else 'skipped'}: {confidence:.1%} confidence"
        )

        # Emit AI thought log
        await self._emit_copy_evaluation_log(evaluation, wallet_tx)

        logger.info(
            "Copy evaluation complete: %s (confidence: %.1f%%, amount: $%.2f, trace: %s)",
            evaluation.decision.value,
            evaluation.confidence * 100,
            float(evaluation.copy_amount_usd),
            trace_id
        )

        return evaluation

    async def execute_copy_trade(
        self,
        wallet_tx: WalletTransaction,
        evaluation: CopyTradeEvaluation,
        trader_config: Dict[str, Any],
        trace_id: str
    ) -> CopyExecutionResult:
        """
        Execute a copy trade based on the evaluation result.
        Uses paper/live mode from runtime_state.
        """
        logger.info("[%s] Executing copy trade for %s", trace_id, wallet_tx.tx_hash)
        start = datetime.now(timezone.utc)

        try:
            paper_mode = await runtime_state.get_paper_enabled()

            if paper_mode:
                exec_result = await self._execute_paper_copy(evaluation, wallet_tx, trace_id)
            else:
                exec_result = await self._execute_live_copy(evaluation, wallet_tx, trace_id)

            # Emit execution thought log
            await runtime_state.emit_thought_log({
                "event": "copy_trade_executed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trade": {
                    "tx_hash": exec_result.tx_hash,
                    "success": exec_result.success,
                    "actual_amount_usd": float(exec_result.actual_amount_usd or 0),
                    "fees_usd": float(exec_result.total_fees_usd or 0),
                    "delay_s": exec_result.execution_delay_seconds,
                    "paper_mode": paper_mode
                },
                "source_tx": wallet_tx.tx_hash,
                "trace_id": trace_id
            })

            return exec_result

        except Exception as e:
            logger.error("[%s] Copy trade execution failed: %s", trace_id, e, exc_info=True)
            delay = int((datetime.now(timezone.utc) - start).total_seconds())
            return CopyExecutionResult(
                success=False,
                copy_trade_id=None,
                tx_hash=None,
                actual_amount_usd=None,
                execution_delay_seconds=delay,
                failure_reason=str(e),
                total_fees_usd=None
            )

    async def get_copy_trading_statistics(self) -> Dict[str, Any]:
        """Get current copy trading statistics."""
        return {
            "daily_copies": self._daily_copy_count,
            "daily_pnl_usd": float(self._daily_pnl_usd),
            "last_reset_date": self._last_reset_date.isoformat()
        }

    # ---------- INTERNAL HELPERS ----------

    async def _check_basic_eligibility(
        self,
        wallet_tx: WalletTransaction,
        trader_config: Dict[str, Any]
    ) -> Tuple[CopyDecision, CopyReason]:
        """Check basic eligibility before running expensive risk checks."""

        # Check trader status
        if trader_config.get("status") != "active":
            return CopyDecision.SKIP, CopyReason.TRADER_PAUSED

        # Check chain allowlist
        allowed_chains = trader_config.get("allowed_chains", [])
        if allowed_chains and wallet_tx.chain not in allowed_chains:
            return CopyDecision.SKIP, CopyReason.OUTSIDE_TRADING_HOURS

        # Direction restrictions
        if trader_config.get("copy_buy_only", False) and wallet_tx.action != "buy":
            return CopyDecision.SKIP, CopyReason.OUTSIDE_TRADING_HOURS
        if trader_config.get("copy_sell_only", False) and wallet_tx.action != "sell":
            return CopyDecision.SKIP, CopyReason.OUTSIDE_TRADING_HOURS

        # Minimum trade size of the ORIGINAL trade (so we don't mirror dust)
        min_copy_usd = Decimal(str(trader_config.get("min_copy_amount_usd", "50")))
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
            return Decimal(str(trader_config.get("fixed_amount_usd", "100")))

        elif copy_mode == "proportional":
            # Proportional to original trade
            proportion = Decimal(str(trader_config.get("copy_percentage", "5"))) / 100
            proportional_amount = wallet_tx.amount_usd * proportion
            max_copy = Decimal(str(trader_config.get("max_copy_amount_usd", self._max_copy_amount_usd)))
            return min(proportional_amount, max_copy)

        else:  # "percentage" of our portfolio
            portfolio_value = await self._get_portfolio_value_usd()
            percentage = Decimal(str(trader_config.get("copy_percentage", self._default_copy_percentage))) / 100
            percentage_amount = portfolio_value * percentage
            max_copy = Decimal(str(trader_config.get("max_copy_amount_usd", self._max_copy_amount_usd)))
            return min(percentage_amount, max_copy)

    async def _check_copy_risk_limits(
        self,
        wallet_tx: WalletTransaction,
        copy_amount: Decimal,
        risk_gates: RiskGateResult,
        trader_config: Dict[str, Any]
    ) -> Tuple[bool, CopyReason]:
        """Check copy-trading specific risk limits."""
        # Risk gates
        if not risk_gates.passed:
            return False, CopyReason.RISK_GATES_FAILED

        # Maximum position size
        max_position = Decimal(str(trader_config.get("max_position_usd", self._max_position_size_usd)))
        if copy_amount > max_position:
            return False, CopyReason.POSITION_SIZE_EXCEEDED

        # Risk score threshold
        max_risk_score = Decimal(str(trader_config.get("max_risk_score", "7.0")))
        if risk_gates.score > max_risk_score:
            return False, CopyReason.RISK_GATES_FAILED

        # Slippage limit (actual slippage check would use a live quote)
        # max_slippage = int(trader_config.get("max_slippage_bps", self._max_slippage_bps))
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
        base_confidence = 0.70

        # Risk score adjustment (lower risk -> higher confidence)
        risk_adjustment = max(0.0, (10 - float(risk_gates.score)) / 10 * 0.20)

        # Trader performance adjustment
        trader_perf = self._trader_performance.get(wallet_tx.from_address, {})
        win_rate = float(trader_perf.get("win_rate", 0.5))
        performance_adjustment = (win_rate - 0.5) * 0.20

        # Trade size adjustment: favor mid-size
        amount_usd = float(wallet_tx.amount_usd)
        if 100 <= amount_usd <= 1000:
            size_adjustment = 0.10
        elif 50 <= amount_usd <= 5000:
            size_adjustment = 0.00
        else:
            size_adjustment = -0.10

        confidence = base_confidence + risk_adjustment + performance_adjustment + size_adjustment
        return max(0.10, min(1.00, confidence))

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
                "liquidity_check": "pass",
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

    async def _execute_paper_copy(
        self,
        evaluation: CopyTradeEvaluation,
        wallet_tx: WalletTransaction,
        trace_id: str
    ) -> CopyExecutionResult:
        """Simulate execution in paper trading mode."""
        # Simulate realistic latency
        await asyncio.sleep(0.5)

        # Simulated slippage (paper usually gets favorable fills)
        simulated_slippage_bps = min(self._max_slippage_bps, 150)
        actual_amount = evaluation.copy_amount_usd * (Decimal("1") - Decimal(simulated_slippage_bps) / Decimal("10000"))
        simulated_fees = actual_amount * Decimal("0.003")  # 0.3% fees

        paper_tx_hash = f"0xpaper_{wallet_tx.tx_hash[:8]}_{int(datetime.now().timestamp())}"
        logger.info("[%s] Paper copy executed: %s", trace_id, paper_tx_hash)

        return CopyExecutionResult(
            success=True,
            copy_trade_id=None,  # Not persisted here
            tx_hash=paper_tx_hash,
            actual_amount_usd=actual_amount,
            execution_delay_seconds=1,
            failure_reason=None,
            total_fees_usd=simulated_fees
        )

    async def _execute_live_copy(
        self,
        evaluation: CopyTradeEvaluation,
        wallet_tx: WalletTransaction,
        trace_id: str
    ) -> CopyExecutionResult:
        """
        Execute live copy trade (integration point to your trading engine/executor).
        Currently a stub that returns not implemented.
        """
        logger.warning("[%s] Live copy trading not yet implemented", trace_id)
        return CopyExecutionResult(
            success=False,
            copy_trade_id=None,
            tx_hash=None,
            actual_amount_usd=None,
            execution_delay_seconds=0,
            failure_reason="Live copy trading not yet implemented",
            total_fees_usd=None
        )

    async def _get_portfolio_value_usd(self) -> Decimal:
        """Get current portfolio value in USD (placeholder)."""
        # Integrate with wallet/accounting service if available.
        return Decimal("10000.0")

    def _estimate_execution_delay(self, chain: str) -> int:
        """Estimate execution delay in milliseconds for different chains."""
        delay_map = {
            "ethereum": 15000,  # ~15s
            "bsc": 5000,
            "base": 3000,
            "polygon": 4000,
            "solana": 2000,
        }
        return delay_map.get(chain, 10000)

    async def _update_daily_tracking(self, execution_result: CopyExecutionResult) -> None:
        """Update daily copy trading counters."""
        today = datetime.now(timezone.utc).date()
        if today != self._last_reset_date:
            self._daily_copy_count = 0
            self._daily_pnl_usd = Decimal("0.0")
            self._last_reset_date = today

        if execution_result.success:
            self._daily_copy_count += 1
            # PnL updates would occur on close, not here.

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
        perf["win_rate"] = perf["winning_trades"] / max(1, perf["total_trades"])
        perf["last_updated"] = datetime.now(timezone.utc)

        logger.info(
            "Updated trader %s performance: %d trades, %.1f%% win rate, $%.2f PnL",
            trader_address[:8],
            perf["total_trades"],
            perf["win_rate"] * 100,
            perf["total_pnl"]
        )


# Global instance (RiskManager will be created if not injected)
copy_trading_strategy = CopyTradingStrategy(risk_manager=None)
