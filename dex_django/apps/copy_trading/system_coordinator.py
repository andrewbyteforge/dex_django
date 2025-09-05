# APP: backend
# FILE: backend/app/copy_trading/system_coordinator.py
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from decimal import Decimal

from dex_django.apps.discovery.wallet_monitor import wallet_monitor, WalletTransaction
from dex_django.apps.strategy.copy_trading_strategy import copy_trading_strategy
from dex_django.apps.strategy.trader_performance_tracker import trader_performance_tracker
from dex_django.apps.trading.live_executor import live_executor
from dex_django.apps.core.runtime_state import runtime_state

logger = logging.getLogger("copy_trading.coordinator")


class CopyTradingCoordinator:
    """
    Main coordinator that orchestrates the complete copy trading pipeline:
    1. Wallet Monitor detects transactions
    2. Performance Tracker analyzes traders
    3. Strategy Engine evaluates opportunities  
    4. Live Executor processes trades
    5. Runtime State manages paper/live modes
    """
    
    def __init__(self):
        self._initialized = False
        self._running = False
        self._followed_traders: Dict[str, Dict[str, Any]] = {}
        
        # System statistics
        self._stats = {
            "transactions_detected": 0,
            "opportunities_evaluated": 0,
            "trades_executed": 0,
            "trades_successful": 0,
            "total_pnl_usd": Decimal("0"),
            "start_time": None,
            "last_activity": None
        }
        
        # Configure wallet monitor callback
        self._original_emit_copy_signal = wallet_monitor._emit_copy_signal
        wallet_monitor._emit_copy_signal = self._on_copy_signal_detected
    
    async def initialize(
        self, 
        private_key: Optional[str] = None,
        enable_live_trading: bool = False
    ) -> bool:
        """
        Initialize the complete copy trading system.
        """
        try:
            logger.info("Initializing copy trading system coordinator...")
            
            # Initialize live executor if private key provided
            if private_key and enable_live_trading:
                success = await live_executor.initialize(private_key)
                if not success:
                    logger.error("Failed to initialize live executor")
                    return False
                logger.info("Live trading enabled")
            else:
                logger.info("Paper trading mode enabled")
                await runtime_state.set_paper_enabled(True)
            
            self._initialized = True
            logger.info("Copy trading system coordinator initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize copy trading coordinator: {e}")
            return False
    
    async def start_system(self, trader_addresses: List[str]) -> Dict[str, Any]:
        """
        Start the complete copy trading system with specified traders.
        """
        if not self._initialized:
            return {"success": False, "error": "System not initialized"}
        
        try:
            logger.info(f"Starting copy trading system with {len(trader_addresses)} traders")
            
            # Load trader configurations
            for address in trader_addresses:
                await self._load_trader_config(address)
            
            # Start wallet monitoring
            await wallet_monitor.start_monitoring(list(self._followed_traders.keys()))
            
            # Mark system as running
            self._running = True
            self._stats["start_time"] = datetime.now(timezone.utc)
            
            logger.info("Copy trading system started successfully")
            
            return {
                "success": True,
                "message": "Copy trading system started",
                "traders_loaded": len(self._followed_traders),
                "monitoring_active": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to start copy trading system: {e}")
            return {"success": False, "error": str(e)}
    
    async def stop_system(self) -> Dict[str, Any]:
        """
        Stop the copy trading system gracefully.
        """
        try:
            logger.info("Stopping copy trading system...")
            
            # Stop wallet monitoring
            await wallet_monitor.stop_monitoring()
            
            # Mark system as stopped
            self._running = False
            
            # Log final statistics
            uptime = None
            if self._stats["start_time"]:
                uptime = int((datetime.now(timezone.utc) - self._stats["start_time"]).total_seconds())
            
            logger.info(
                f"Copy trading system stopped. Stats: "
                f"Trades: {self._stats['trades_executed']}, "
                f"Success: {self._stats['trades_successful']}, "
                f"PnL: ${self._stats['total_pnl_usd']}, "
                f"Uptime: {uptime}s"
            )
            
            return {
                "success": True,
                "message": "Copy trading system stopped",
                "final_stats": self._get_system_stats(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error stopping copy trading system: {e}")
            return {"success": False, "error": str(e)}
    
    async def add_trader(
        self,
        address: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add a new trader to the copy trading system.
        """
        try:
            address = address.lower()
            
            if address in self._followed_traders:
                return {"success": False, "error": "Trader already being followed"}
            
            # Validate trader config
            validated_config = await self._validate_trader_config(config)
            
            # Store trader configuration
            self._followed_traders[address] = {
                "address": address,
                "config": validated_config,
                "added_at": datetime.now(timezone.utc),
                "status": "active",
                "stats": {
                    "opportunities_detected": 0,
                    "trades_executed": 0,
                    "trades_successful": 0,
                    "total_pnl_usd": Decimal("0")
                }
            }
            
            # Add to wallet monitoring if system is running
            if self._running:
                await wallet_monitor.add_wallet(address)
            
            # Start background performance analysis
            asyncio.create_task(self._analyze_trader_background(address))
            
            logger.info(f"Added trader {address[:8]} to copy trading system")
            
            return {
                "success": True,
                "message": "Trader added successfully",
                "trader_address": address,
                "monitoring_active": self._running
            }
            
        except Exception as e:
            logger.error(f"Error adding trader: {e}")
            return {"success": False, "error": str(e)}
    
    async def remove_trader(self, address: str) -> Dict[str, Any]:
        """
        Remove a trader from the copy trading system.
        """
        try:
            address = address.lower()
            
            if address not in self._followed_traders:
                return {"success": False, "error": "Trader not found"}
            
            # Remove from monitoring
            if self._running:
                await wallet_monitor.remove_wallet(address)
            
            # Archive trader data
            removed_trader = self._followed_traders.pop(address)
            
            logger.info(f"Removed trader {address[:8]} from copy trading system")
            
            return {
                "success": True,
                "message": "Trader removed successfully",
                "trader_address": address,
                "final_stats": removed_trader["stats"]
            }
            
        except Exception as e:
            logger.error(f"Error removing trader: {e}")
            return {"success": False, "error": str(e)}
    
    async def _on_copy_signal_detected(self, tx: WalletTransaction) -> None:
        """
        Handle copy signals from wallet monitor - main processing pipeline.
        """
        try:
            trader_address = tx.from_address.lower()
            
            # Update statistics
            self._stats["transactions_detected"] += 1
            self._stats["last_activity"] = datetime.now(timezone.utc)
            
            if trader_address in self._followed_traders:
                trader_data = self._followed_traders[trader_address]
                trader_data["stats"]["opportunities_detected"] += 1
            
            # Call the original emit method for thought log
            await self._original_emit_copy_signal(tx)
            
            # Process through our pipeline
            await self._process_copy_opportunity(tx)
            
        except Exception as e:
            logger.error(f"Error handling copy signal: {e}")
    
    async def _process_copy_opportunity(self, tx: WalletTransaction) -> None:
        """
        Main copy trading processing pipeline.
        """
        trader_address = tx.from_address.lower()
        trace_id = f"copy_{tx.tx_hash[:8]}_{int(datetime.now().timestamp())}"
        
        logger.info(f"[{trace_id}] Processing copy opportunity from {trader_address[:8]}")
        
        try:
            # Step 1: Get trader configuration
            if trader_address not in self._followed_traders:
                logger.info(f"[{trace_id}] Trader not in followed list, skipping")
                return
            
            trader_data = self._followed_traders[trader_address]
            trader_config = trader_data["config"]
            
            if not trader_config.get("enabled", True):
                logger.info(f"[{trace_id}] Trader disabled, skipping")
                return
            
            # Step 2: Update trader performance tracking
            await trader_performance_tracker.track_transaction(tx)
            
            # Step 3: Evaluate copy opportunity with strategy engine
            self._stats["opportunities_evaluated"] += 1
            
            evaluation = await copy_trading_strategy.evaluate_copy_opportunity(
                tx, trader_config, trace_id
            )
            
            # Step 4: Execute if approved
            if evaluation.decision.value == "copy":
                execution_result = await copy_trading_strategy.execute_copy_trade(
                    tx, evaluation, trader_config, trace_id
                )
                
                # Step 5: Update statistics
                await self._update_trade_stats(trader_address, execution_result, trace_id)
            else:
                logger.info(
                    f"[{trace_id}] Copy opportunity skipped: {evaluation.reason.value}"
                )
            
        except Exception as e:
            logger.error(f"[{trace_id}] Error processing copy opportunity: {e}")
    
    async def _update_trade_stats(
        self,
        trader_address: str,
        execution_result: Any,
        trace_id: str
    ) -> None:
        """
        Update system and trader statistics after trade execution.
        """
        try:
            # Update global stats
            self._stats["trades_executed"] += 1
            
            if execution_result.success:
                self._stats["trades_successful"] += 1
                
                # Update PnL (simplified - would track realized PnL properly)
                if execution_result.actual_amount_usd:
                    # Mock PnL calculation
                    estimated_pnl = execution_result.actual_amount_usd * Decimal("0.02")  # 2% gain assumption
                    self._stats["total_pnl_usd"] += estimated_pnl
            
            # Update trader-specific stats
            if trader_address in self._followed_traders:
                trader_stats = self._followed_traders[trader_address]["stats"]
                trader_stats["trades_executed"] += 1
                
                if execution_result.success:
                    trader_stats["trades_successful"] += 1
                    
                    if execution_result.actual_amount_usd:
                        estimated_pnl = execution_result.actual_amount_usd * Decimal("0.02")
                        trader_stats["total_pnl_usd"] += estimated_pnl
            
            # Emit system metrics update
            await runtime_state.update_paper_metrics(
                total_trades=self._stats["trades_executed"],
                successful_trades=self._stats["trades_successful"],
                total_pnl_usd=float(self._stats["total_pnl_usd"]),
                last_trade_time=datetime.now(timezone.utc).isoformat()
            )
            
            logger.info(
                f"[{trace_id}] Updated stats - Success: {execution_result.success}, "
                f"Total trades: {self._stats['trades_executed']}"
            )
            
        except Exception as e:
            logger.error(f"Error updating trade stats: {e}")
    
    async def _load_trader_config(self, address: str) -> None:
        """
        Load trader configuration from database or use defaults.
        """
        # Mock configuration - would load from database in production
        default_config = {
            "enabled": True,
            "copy_mode": "percentage",
            "copy_percentage": Decimal("5.0"),
            "max_copy_amount_usd": Decimal("1000.0"),
            "min_trade_value_usd": Decimal("100.0"),
            "max_slippage_bps": 300,
            "allowed_chains": ["ethereum", "bsc", "base"],
            "copy_buy_only": True,
            "risk_multiplier": Decimal("1.0")
        }
        
        self._followed_traders[address.lower()] = {
            "address": address.lower(),
            "config": default_config,
            "added_at": datetime.now(timezone.utc),
            "status": "active",
            "stats": {
                "opportunities_detected": 0,
                "trades_executed": 0,
                "trades_successful": 0,
                "total_pnl_usd": Decimal("0")
            }
        }
    
    async def _validate_trader_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize trader configuration.
        """
        validated = {
            "enabled": config.get("enabled", True),
            "copy_mode": config.get("copy_mode", "percentage"),
            "copy_percentage": Decimal(str(config.get("copy_percentage", 5.0))),
            "max_copy_amount_usd": Decimal(str(config.get("max_copy_amount_usd", 1000.0))),
            "min_trade_value_usd": Decimal(str(config.get("min_trade_value_usd", 100.0))),
            "max_slippage_bps": int(config.get("max_slippage_bps", 300)),
            "allowed_chains": config.get("allowed_chains", ["ethereum", "bsc", "base"]),
            "copy_buy_only": config.get("copy_buy_only", True),
            "risk_multiplier": Decimal(str(config.get("risk_multiplier", 1.0)))
        }
        
        # Validation rules
        if validated["copy_percentage"] < Decimal("0.1") or validated["copy_percentage"] > Decimal("50.0"):
            raise ValueError("Copy percentage must be between 0.1% and 50%")
        
        if validated["max_copy_amount_usd"] < Decimal("10") or validated["max_copy_amount_usd"] > Decimal("100000"):
            raise ValueError("Max copy amount must be between $10 and $100,000")
        
        if validated["max_slippage_bps"] < 10 or validated["max_slippage_bps"] > 2000:
            raise ValueError("Max slippage must be between 10 and 2000 basis points")
        
        return validated
    
    async def _analyze_trader_background(self, address: str) -> None:
        """
        Background task to analyze trader performance history.
        """
        try:
            logger.info(f"Starting background analysis for trader {address[:8]}")
            
            # Mock analysis - would fetch historical data and analyze
            await asyncio.sleep(10)  # Simulate analysis time
            
            # Get performance data
            performance = await trader_performance_tracker.get_trader_performance(address)
            
            if performance:
                logger.info(
                    f"Trader {address[:8]} analysis complete: "
                    f"WR={performance['performance']['win_rate']:.1%}, "
                    f"Risk={performance['performance']['risk_score']:.0f}"
                )
            
        except Exception as e:
            logger.error(f"Error in background trader analysis: {e}")
    
    def _get_system_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive system statistics.
        """
        uptime_seconds = 0
        if self._stats["start_time"]:
            uptime_seconds = int((datetime.now(timezone.utc) - self._stats["start_time"]).total_seconds())
        
        success_rate = 0.0
        if self._stats["trades_executed"] > 0:
            success_rate = self._stats["trades_successful"] / self._stats["trades_executed"]
        
        return {
            "system": {
                "running": self._running,
                "uptime_seconds": uptime_seconds,
                "followed_traders": len(self._followed_traders),
                "active_monitoring": wallet_monitor._is_running
            },
            "activity": {
                "transactions_detected": self._stats["transactions_detected"],
                "opportunities_evaluated": self._stats["opportunities_evaluated"],
                "trades_executed": self._stats["trades_executed"],
                "trades_successful": self._stats["trades_successful"],
                "success_rate": success_rate,
                "total_pnl_usd": float(self._stats["total_pnl_usd"]),
                "last_activity": self._stats["last_activity"].isoformat() if self._stats["last_activity"] else None
            },
            "traders": {
                address: {
                    "opportunities": data["stats"]["opportunities_detected"],
                    "trades": data["stats"]["trades_executed"],
                    "pnl_usd": float(data["stats"]["total_pnl_usd"])
                }
                for address, data in self._followed_traders.items()
            }
        }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """
        Get current system status and health.
        """
        try:
            # Get component status
            monitor_status = await wallet_monitor.get_monitoring_status()
            executor_status = await live_executor.get_status()
            paper_enabled = await runtime_state.get_paper_enabled()
            
            return {
                "status": "ok",
                "coordinator": {
                    "initialized": self._initialized,
                    "running": self._running,
                    "paper_mode": paper_enabled
                },
                "components": {
                    "wallet_monitor": monitor_status,
                    "live_executor": executor_status,
                    "strategy_engine": "healthy",
                    "performance_tracker": "healthy"
                },
                "statistics": self._get_system_stats(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def cleanup(self) -> None:
        """
        Cleanup coordinator resources.
        """
        try:
            if self._running:
                await self.stop_system()
            
            # Restore original