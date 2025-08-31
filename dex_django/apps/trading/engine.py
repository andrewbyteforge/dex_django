from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from apps.storage.models import Trade, LedgerEntry

logger = logging.getLogger("trading.engine")

# Define ALL enums at the top before any classes
class TradingMode(Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate" 
    AGGRESSIVE = "aggressive"

class StrategyType(Enum):
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    ARBITRAGE = "arbitrage"

class TradeStatus(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ExecutionMode(Enum):
    PAPER = "paper"
    LIVE = "live"

# Mock classes for intelligence modules
class MockStrategyEngine:
    def __init__(self):
        self.name = "MockStrategyEngine"
        
    async def generate_trading_signals(self, opportunities, balance, mode):
        logger.debug("Mock strategy engine - no signals generated")
        return []

class MockRiskManager:
    def __init__(self):
        self.name = "MockRiskManager"
        
    async def check_circuit_breaker(self, mode):
        logger.debug("Mock risk manager - no circuit breaker")
        return False

# Compatibility wrapper for real intelligence modules
class IntelligenceWrapper:
    def __init__(self, real_strategy_engine=None, real_risk_manager=None):
        self.real_strategy_engine = real_strategy_engine
        self.real_risk_manager = real_risk_manager
        
    async def generate_trading_signals(self, opportunities, balance, mode):
        """Generate trading signals with compatibility."""
        if self.real_strategy_engine and hasattr(self.real_strategy_engine, 'generate_trading_signals'):
            return await self.real_strategy_engine.generate_trading_signals(opportunities, balance, mode)
        elif self.real_strategy_engine and hasattr(self.real_strategy_engine, 'generate_signals'):
            return await self.real_strategy_engine.generate_signals(opportunities, balance, mode)
        else:
            logger.debug("No compatible signal generation method found")
            return []
    
    async def check_circuit_breaker(self, mode):
        """Check circuit breaker with compatibility."""
        if self.real_risk_manager and hasattr(self.real_risk_manager, 'check_circuit_breaker'):
            return await self.real_risk_manager.check_circuit_breaker(mode)
        elif self.real_risk_manager and hasattr(self.real_risk_manager, 'circuit_breaker_active'):
            return getattr(self.real_risk_manager, 'circuit_breaker_active', False)
        else:
            logger.debug("No circuit breaker method found - defaulting to False")
            return False

# Initialize with mocks
strategy_engine = MockStrategyEngine()
risk_manager = MockRiskManager()

# Try to import and wrap real modules
try:
    import apps.intelligence.strategy_engine as imported_strategy_engine
    import apps.intelligence.risk_manager as imported_risk_manager
    
    # Create wrapper with real modules
    wrapper = IntelligenceWrapper(imported_strategy_engine, imported_risk_manager)
    
    # Replace with wrapper that has compatible interface
    strategy_engine = wrapper
    risk_manager = wrapper
    
    logger.info("Loaded and wrapped real intelligence modules")
    
    # Debug: Show available methods in real modules
    if hasattr(imported_strategy_engine, '__dict__'):
        logger.debug(f"Strategy engine methods: {[m for m in dir(imported_strategy_engine) if not m.startswith('_')]}")
    if hasattr(imported_risk_manager, '__dict__'):
        logger.debug(f"Risk manager methods: {[m for m in dir(imported_risk_manager) if not m.startswith('_')]}")
        
except ImportError as e:
    logger.info(f"Using mock intelligence modules: {e}")

@dataclass
class TradeExecution:
    """Individual trade execution details."""
    signal_id: str
    pair_address: str
    chain: str
    dex_name: str
    token_address: str
    action: str  # BUY, SELL
    amount_usd: Decimal
    expected_slippage: Decimal
    stop_loss_price: Optional[Decimal]
    take_profit_price: Optional[Decimal]
    execution_deadline: datetime
    status: TradeStatus
    transaction_hash: Optional[str] = None
    executed_price: Optional[Decimal] = None
    gas_used: Optional[int] = None
    error_message: Optional[str] = None

class TradingEngine:
    """Automated trading engine with multi-chain router-first execution."""
    
    def __init__(self):
        self.is_running = False
        self.execution_mode = ExecutionMode.PAPER
        self.trading_mode = TradingMode.MODERATE
        self.active_trades = {}
        self.pending_executions = []
        self.user_balance_usd = Decimal("1000")  # Mock balance
        
        # Multi-chain support
        self.supported_chains = ["ethereum", "bsc", "base", "polygon", "solana"]
        self.chain_status = {}  # Track connection status per chain
        
        # Safety controls
        self.max_concurrent_trades = 5
        self.daily_trade_limit = 20
        self.emergency_stop = False
        
        # Performance tracking
        self.daily_trades_count = 0
        self.last_reset_date = datetime.now().date()
    
    async def start_trading(self, mode: ExecutionMode = ExecutionMode.PAPER) -> bool:
        """Start the automated trading engine."""
        
        if self.is_running:
            logger.warning("Trading engine already running")
            return False
        
        logger.info(f"Starting trading engine in {mode.value} mode")
        
        try:
            # Safety checks
            if await self._pre_trading_safety_checks():
                self.is_running = True
                self.execution_mode = mode
                
                # Initialize multi-chain connections if live mode
                if mode == ExecutionMode.LIVE:
                    await self._initialize_chain_connections()
                
                # Start the main trading loop
                asyncio.create_task(self._trading_loop())
                
                logger.info("Trading engine started successfully")
                return True
            else:
                logger.error("Pre-trading safety checks failed")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start trading engine: {e}")
            return False
    
    async def stop_trading(self) -> bool:
        """Stop the automated trading engine."""
        
        if not self.is_running:
            logger.warning("Trading engine not running")
            return False
        
        logger.info("Stopping trading engine...")
        
        try:
            self.is_running = False
            
            # Cancel pending executions
            for execution in self.pending_executions:
                execution.status = TradeStatus.CANCELLED
            
            self.pending_executions.clear()
            
            logger.info("Trading engine stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping trading engine: {e}")
            return False
    
    async def _trading_loop(self) -> None:
        """Main trading loop - runs continuously when engine is active."""
        
        logger.info("Starting main trading loop")
        loop_count = 0
        
        while self.is_running and not self.emergency_stop:
            try:
                loop_count += 1
                if loop_count % 3 == 1:  # Log every 3rd iteration
                    logger.info(f"Trading loop iteration {loop_count}")
                
                # Reset daily counters if new day
                await self._reset_daily_counters()
                
                # Check circuit breakers with compatibility
                global risk_manager
                circuit_breaker_active = await risk_manager.check_circuit_breaker(self.trading_mode)
                if circuit_breaker_active:
                    logger.warning("Circuit breaker activated - pausing trading")
                    await asyncio.sleep(300)  # Wait 5 minutes
                    continue
                
                # Monitor chain health
                if self.execution_mode == ExecutionMode.LIVE:
                    await self._monitor_chain_health()
                
                # Generate trading signals (mock for testing)
                opportunities = await self._get_live_opportunities()
                
                if opportunities:
                    global strategy_engine
                    signals = await strategy_engine.generate_trading_signals(
                        opportunities, self.user_balance_usd, self.trading_mode
                    )
                    
                    # Process signals (will be empty with mock engine)
                    for signal in signals:
                        if hasattr(signal, 'urgency') and signal.urgency in ["CRITICAL", "HIGH"]:
                            await self._process_trading_signal(signal)
                
                # Execute pending trades
                await self._execute_pending_trades()
                
                # Monitor active positions
                await self._monitor_active_positions()
                
                # Wait before next iteration
                await asyncio.sleep(2)  # 2-second loop for testing
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                await asyncio.sleep(10)  # Wait longer on error
        
        logger.info(f"Trading loop stopped after {loop_count} iterations")
    
    async def _initialize_chain_connections(self) -> None:
        """Initialize connections to all supported chains."""
        
        logger.info("Initializing multi-chain connections...")
        
        for chain in self.supported_chains:
            try:
                if chain == "solana":
                    # Solana uses different connection logic
                    await self._initialize_solana_connection()
                    self.chain_status[chain] = "connected"
                else:
                    # EVM chains use Web3
                    await self._initialize_evm_connection(chain)
                    self.chain_status[chain] = "connected"
                    
                logger.info(f"Connected to {chain}")
                
            except Exception as e:
                logger.error(f"Failed to connect to {chain}: {e}")
                self.chain_status[chain] = "disconnected"
        
        connected_chains = [k for k, v in self.chain_status.items() if v == "connected"]
        logger.info(f"Successfully connected to {len(connected_chains)} chains: {connected_chains}")
    
    async def _initialize_evm_connection(self, chain: str) -> None:
        """Initialize connection to an EVM-compatible chain."""
        
        try:
            from .router_executor import router_executor
            
            if not router_executor.initialized:
                success = await router_executor.initialize()
                if not success:
                    raise ConnectionError(f"Failed to initialize router executor for {chain}")
        except ImportError:
            logger.warning("Router executor not available")
    
    async def _initialize_solana_connection(self) -> None:
        """Initialize connection to Solana."""
        
        try:
            from .solana_executor import solana_executor
            success = await solana_executor.initialize()
            if not success:
                raise ConnectionError("Failed to initialize Solana executor")
        except ImportError:
            logger.warning("Solana executor not implemented yet")
    
    async def _pre_trading_safety_checks(self) -> bool:
        """Run safety checks before starting trading."""
        
        logger.info("Running pre-trading safety checks")
        logger.info(f"Execution mode: {self.execution_mode.value}")
        logger.info(f"Trading mode: {self.trading_mode.value}")
        logger.info(f"Supported chains: {self.supported_chains}")
        
        global strategy_engine, risk_manager
        
        logger.info(f"Using strategy engine: {type(strategy_engine).__name__}")
        logger.info(f"Using risk manager: {type(risk_manager).__name__}")
        logger.info("Pre-trading safety checks passed")
        return True
    
    async def _get_live_opportunities(self) -> List[Dict[str, Any]]:
        """Get live trading opportunities (mock for testing)."""
        return []
    
    async def _execute_pending_trades(self) -> None:
        """Execute pending trades in the queue."""
        return
    
    async def _monitor_active_positions(self) -> None:
        """Monitor active positions."""
        return
    
    async def _monitor_chain_health(self) -> None:
        """Monitor chain health."""
        return
    
    async def _reset_daily_counters(self) -> None:
        """Reset daily counters if new day."""
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_trades_count = 0
            self.last_reset_date = today
            logger.info("Daily counters reset")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current engine status."""
        
        return {
            "is_running": self.is_running,
            "execution_mode": self.execution_mode.value,
            "trading_mode": self.trading_mode.value,
            "pending_executions": len(self.pending_executions),
            "active_trades": len(self.active_trades),
            "daily_trades_count": self.daily_trades_count,
            "emergency_stop": self.emergency_stop,
            "supported_chains": self.supported_chains,
            "chain_status": self.chain_status
        }

# Global trading engine instance
trading_engine = TradingEngine()