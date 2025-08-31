from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from apps.intelligence import strategy_engine, risk_manager, TradingMode, StrategyType
from apps.storage.models import Trade, LedgerEntry

logger = logging.getLogger("trading.engine")

class TradeStatus(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ExecutionMode(Enum):
    PAPER = "paper"
    LIVE = "live"

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
        
        # This would initialize the router executor for the specific chain
        from .router_executor import router_executor
        
        if not router_executor.initialized:
            success = await router_executor.initialize()
            if not success:
                raise ConnectionError(f"Failed to initialize router executor for {chain}")
    
    async def _initialize_solana_connection(self) -> None:
        """Initialize connection to Solana."""
        
        # Solana would need a separate executor (Jupiter integration)
        try:
            from .solana_executor import solana_executor
            success = await solana_executor.initialize()
            if not success:
                raise ConnectionError("Failed to initialize Solana executor")
        except ImportError:
            logger.warning("Solana executor not implemented yet")
    
    async def _trading_loop(self) -> None:
        """Main trading loop - runs continuously when engine is active."""
        
        logger.info("Starting main trading loop")
        
        while self.is_running and not self.emergency_stop:
            try:
                # Reset daily counters if new day
                await self._reset_daily_counters()
                
                # Check circuit breakers
                if await risk_manager.check_circuit_breaker(self.trading_mode):
                    logger.warning("Circuit breaker activated - pausing trading")
                    await asyncio.sleep(300)  # Wait 5 minutes
                    continue
                
                # Monitor chain health
                if self.execution_mode == ExecutionMode.LIVE:
                    await self._monitor_chain_health()
                
                # Generate trading signals
                opportunities = await self._get_live_opportunities()
                
                if opportunities:
                    signals = await strategy_engine.generate_trading_signals(
                        opportunities, self.user_balance_usd, self.trading_mode
                    )
                    
                    # Process high-priority signals
                    for signal in signals:
                        if signal.urgency in ["CRITICAL", "HIGH"]:
                            await self._process_trading_signal(signal)
                
                # Execute pending trades
                await self._execute_pending_trades()
                
                # Monitor active positions
                await self._monitor_active_positions()
                
                # Wait before next iteration
                await asyncio.sleep(5)  # 5-second loop
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                await asyncio.sleep(10)  # Wait longer on error
        
        logger.info("Trading loop stopped")
    
    async def _monitor_chain_health(self) -> None:
        """Monitor health of all connected chains."""
        
        for chain in self.supported_chains:
            if self.chain_status.get(chain) == "connected":
                try:
                    # Check if chain is still responsive
                    if chain == "solana":
                        # Solana-specific health check
                        pass
                    else:
                        # EVM chain health check
                        from .router_executor import router_executor
                        if chain in router_executor.web3_connections:
                            web3 = router_executor.web3_connections[chain]
                            latest_block = web3.eth.block_number
                            logger.debug(f"{chain} latest block: {latest_block}")
                
                except Exception as e:
                    logger.warning(f"Chain {chain} health check failed: {e}")
                    self.chain_status[chain] = "unhealthy"
    
    async def _process_trading_signal(self, signal) -> None:
        """Process a trading signal and create execution plan."""
        
        logger.info(f"Processing signal: {signal.action} {signal.pair_address}")
        
        try:
            # Safety checks
            if not await self._can_execute_trade(signal):
                logger.info(f"Cannot execute trade - safety limits reached")
                return
            
            # Check if chain is supported and healthy
            chain = getattr(signal, 'chain', 'ethereum')
            if chain not in self.supported_chains:
                logger.warning(f"Unsupported chain: {chain}")
                return
            
            if self.execution_mode == ExecutionMode.LIVE:
                if self.chain_status.get(chain) != "connected":
                    logger.warning(f"Chain {chain} not connected - skipping trade")
                    return
            
            # Create execution plan
            execution = TradeExecution(
                signal_id=f"signal_{datetime.now().timestamp()}",
                pair_address=signal.pair_address,
                chain=chain,
                dex_name=getattr(signal, 'dex', 'uniswap_v2'),
                token_address=getattr(signal, 'token_address', ''),
                action=signal.action,
                amount_usd=signal.position_sizing.recommended_amount_usd if signal.position_sizing else Decimal("10"),
                expected_slippage=signal.position_sizing.max_acceptable_slippage if signal.position_sizing else Decimal("5"),
                stop_loss_price=signal.position_sizing.stop_loss_price if signal.position_sizing else None,
                take_profit_price=signal.position_sizing.take_profit_price if signal.position_sizing else None,
                execution_deadline=signal.execution_deadline,
                status=TradeStatus.PENDING
            )
            
            # Add to execution queue
            self.pending_executions.append(execution)
            
            logger.info(f"Added execution to queue: {execution.signal_id} on {chain}")
            
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
    
    async def _execute_pending_trades(self) -> None:
        """Execute pending trades in the queue."""
        
        if not self.pending_executions:
            return
        
        # Process executions in order of urgency/deadline
        self.pending_executions.sort(key=lambda x: x.execution_deadline)
        
        for execution in self.pending_executions[:]:
            try:
                # Check if deadline passed
                if datetime.now() > execution.execution_deadline:
                    execution.status = TradeStatus.CANCELLED
                    logger.info(f"Trade expired: {execution.signal_id}")
                    self.pending_executions.remove(execution)
                    continue
                
                # Execute the trade
                await self._execute_single_trade(execution)
                
                # Remove from pending if completed or failed
                if execution.status in [TradeStatus.COMPLETED, TradeStatus.FAILED, TradeStatus.CANCELLED]:
                    self.pending_executions.remove(execution)
                
            except Exception as e:
                logger.error(f"Error executing trade {execution.signal_id}: {e}")
                execution.status = TradeStatus.FAILED
                execution.error_message = str(e)
    
    async def _execute_single_trade(self, execution: TradeExecution) -> None:
        """Execute a single trade with multi-chain support."""
        
        logger.info(f"Executing trade: {execution.action} {execution.amount_usd} USD of {execution.pair_address} on {execution.chain}")
        
        execution.status = TradeStatus.EXECUTING
        
        try:
            if self.execution_mode == ExecutionMode.PAPER:
                # Paper trading execution
                result = await self._execute_paper_trade(execution)
            else:
                # Live trading execution (multi-chain)
                result = await self._execute_live_trade(execution)
            
            if result["success"]:
                execution.status = TradeStatus.COMPLETED
                execution.transaction_hash = result.get("tx_hash")
                execution.executed_price = result.get("price")
                execution.gas_used = result.get("gas_used")
                
                # Record the trade
                await self._record_trade(execution)
                
                # Update counters
                self.daily_trades_count += 1
                
                logger.info(f"Trade completed successfully: {execution.signal_id}")
            else:
                execution.status = TradeStatus.FAILED
                execution.error_message = result.get("error", "Unknown error")
                logger.error(f"Trade failed: {execution.signal_id} - {execution.error_message}")
        
        except Exception as e:
            execution.status = TradeStatus.FAILED
            execution.error_message = str(e)
            logger.error(f"Trade execution error: {e}")
    
    async def _execute_paper_trade(self, execution: TradeExecution) -> Dict[str, Any]:
        """Execute paper trade (simulation) with multi-chain awareness."""
        
        logger.info(f"Paper trading: {execution.action} ${execution.amount_usd} on {execution.chain}")
        
        # Simulate execution delay based on chain
        chain_delays = {
            "ethereum": 2,    # Slower due to congestion
            "bsc": 1,        # Faster
            "base": 1,       # Fast
            "polygon": 1,    # Fast
            "solana": 0.5    # Fastest
        }
        
        await asyncio.sleep(chain_delays.get(execution.chain, 1))
        
        # Mock successful execution with chain-specific characteristics
        chain_characteristics = {
            "ethereum": {"gas_cost": 0.005, "slippage_factor": 1.0},
            "bsc": {"gas_cost": 0.001, "slippage_factor": 0.8},
            "base": {"gas_cost": 0.0005, "slippage_factor": 0.7},
            "polygon": {"gas_cost": 0.001, "slippage_factor": 0.8},
            "solana": {"gas_cost": 0.00005, "slippage_factor": 0.5}
        }
        
        characteristics = chain_characteristics.get(execution.chain, chain_characteristics["ethereum"])
        
        mock_price = Decimal("2000")  # Mock token price
        mock_slippage = min(
            execution.expected_slippage * Decimal(str(characteristics["slippage_factor"])), 
            Decimal("2")
        )
        
        return {
            "success": True,
            "tx_hash": f"0x{'0' * 60}paper_{execution.chain}",
            "price": mock_price,
            "gas_used": int(150000 * (1 / characteristics["gas_cost"] / 1000)),  # Relative gas usage
            "actual_slippage": mock_slippage,
            "chain": execution.chain
        }
    
    async def _execute_live_trade(self, execution: TradeExecution) -> Dict[str, Any]:
        """Execute live trade on blockchain using multi-chain router integration."""
        
        logger.info(f"Live trading: {execution.action} ${execution.amount_usd} on {execution.chain}")
        
        try:
            if execution.chain == "solana":
                # Use Solana/Jupiter executor
                return await self._execute_solana_trade(execution)
            else:
                # Use EVM router executor
                return await self._execute_evm_trade(execution)
                
        except Exception as e:
            logger.error(f"Live trade execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_evm_trade(self, execution: TradeExecution) -> Dict[str, Any]:
        """Execute trade on EVM-compatible chains (Ethereum, BSC, Base, Polygon)."""
        
        from .router_executor import router_executor
        
        # Initialize router if needed
        if not router_executor.initialized:
            success = await router_executor.initialize()
            if not success:
                return {"success": False, "error": "Failed to initialize router executor"}
        
        # Get chain-specific parameters
        chain_configs = {
            "ethereum": {"native_token": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "price": 2000},
            "bsc": {"native_token": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c", "price": 300},
            "base": {"native_token": "0x4200000000000000000000000000000000000006", "price": 2000},
            "polygon": {"native_token": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270", "price": 0.8}
        }
        
        config = chain_configs.get(execution.chain, chain_configs["ethereum"])
        
        # Convert USD amount to native token amount
        amount_in_native = Decimal(str(execution.amount_usd)) / Decimal(str(config["price"]))
        
        # Execute swap through direct router integration
        result = await router_executor.execute_swap(
            token_in=config["native_token"],
            token_out=execution.token_address,
            amount_in=amount_in_native,
            chain=execution.chain,
            dex=execution.dex_name,
            slippage_bps=int(execution.expected_slippage * 100)
        )
        
        return result
    
    async def _execute_solana_trade(self, execution: TradeExecution) -> Dict[str, Any]:
        """Execute trade on Solana using Jupiter."""
        
        try:
            from .solana_executor import solana_executor
            
            # Initialize Solana executor if needed
            if not solana_executor.initialized:
                success = await solana_executor.initialize()
                if not success:
                    return {"success": False, "error": "Failed to initialize Solana executor"}
            
            # Convert USD amount to SOL amount
            sol_price_usd = 20  # Mock price - replace with real price feed
            amount_in_sol = Decimal(str(execution.amount_usd)) / Decimal(str(sol_price_usd))
            
            # Execute swap through Jupiter
            result = await solana_executor.execute_jupiter_swap(
                token_in="So11111111111111111111111111111111111111112",  # SOL
                token_out=execution.token_address,
                amount_in=amount_in_sol,
                slippage_bps=int(execution.expected_slippage * 100)
            )
            
            return result
            
        except ImportError:
            return {"success": False, "error": "Solana executor not implemented yet"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _monitor_active_positions(self) -> None:
        """Monitor active positions for stop-loss/take-profit triggers."""
        
        if not self.active_trades:
            return
        
        logger.debug(f"Monitoring {len(self.active_trades)} active positions")
        
        # TODO: Implement position monitoring across all chains
        # This would check current prices against stop-loss/take-profit levels
        # and automatically close positions when triggered
    
    async def _record_trade(self, execution: TradeExecution) -> None:
        """Record completed trade in database."""
        
        try:
            # Create trade record
            trade = Trade.objects.create(
                pair_address=execution.pair_address,
                chain=execution.chain,
                action=execution.action,
                amount_usd=execution.amount_usd,
                executed_price=execution.executed_price,
                transaction_hash=execution.transaction_hash,
                gas_used=execution.gas_used,
                slippage_pct=execution.expected_slippage,
                is_paper=(self.execution_mode == ExecutionMode.PAPER),
                strategy_type="automated",
                status="completed"
            )
            
            # Create ledger entry
            LedgerEntry.objects.create(
                trade=trade,
                action=execution.action,
                amount_usd=execution.amount_usd,
                is_paper=(self.execution_mode == ExecutionMode.PAPER)
            )
            
            logger.info(f"Trade recorded: {trade.id} on {execution.chain}")
            
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
    
    async def _can_execute_trade(self, signal) -> bool:
        """Check if we can execute a trade based on safety limits."""
        
        # Check daily limits
        if self.daily_trades_count >= self.daily_trade_limit:
            logger.warning("Daily trade limit reached")
            return False
        
        # Check concurrent trades
        if len(self.active_trades) >= self.max_concurrent_trades:
            logger.warning("Max concurrent trades reached")
            return False
        
        # Check emergency stop
        if self.emergency_stop:
            logger.warning("Emergency stop active")
            return False
        
        return True
    
    async def _pre_trading_safety_checks(self) -> bool:
        """Run safety checks before starting trading."""
        
        logger.info("Running pre-trading safety checks")
        
        # Check if risk manager is available
        if not risk_manager:
            logger.error("Risk manager not available")
            return False
        
        # Check if strategy engine is available
        if not strategy_engine:
            logger.error("Strategy engine not available")
            return False
        
        # Check supported chains
        logger.info(f"Supported chains: {self.supported_chains}")
        
        logger.info("Pre-trading safety checks passed")
        return True
    
    async def _get_live_opportunities(self) -> List[Dict[str, Any]]:
        """Get live trading opportunities from multi-chain sources."""
        
        # This would integrate with your existing discovery system
        # Mock multi-chain opportunities for testing
        return [
            {
                "pair_address": "0x1234...ethereum",
                "chain": "ethereum",
                "dex": "uniswap_v3",
                "token_address": "0xabcd...eth",
                "token0_symbol": "DEFI",
                "token1_symbol": "WETH",
                "estimated_liquidity_usd": 150000,
                "opportunity_score": 8.2,
                "source": "live_scan"
            },
            {
                "pair_address": "jupiter_bonk123",
                "chain": "solana",
                "dex": "jupiter",
                "token_address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                "token0_symbol": "BONK",
                "token1_symbol": "SOL",
                "estimated_liquidity_usd": 89000,
                "opportunity_score": 7.5,
                "source": "jupiter_api"
            }
        ]
    
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