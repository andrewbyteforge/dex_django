# APP: backend
# FILE: backend/app/copy_trading/copy_trading_coordinator.py
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set
from decimal import Decimal

from backend.app.copy_trading.wallet_tracker import (
    WalletTracker, WalletTransaction, ChainType, WalletStatus, TrackedWallet
)
from backend.app.strategy.copy_trading_strategy import (
    CopyTradingStrategy, copy_trading_strategy
)
from backend.app.storage.copy_trading_repo import create_copy_trading_repositories
from backend.app.storage.copy_trading_models import (
    TrackedWallet as DBTrackedWallet, DetectedTransaction, CopyTradeStatus
)
from backend.app.core.runtime_state import runtime_state
from backend.app.core.database import get_db

logger = logging.getLogger("copy_trading.coordinator")


class CopyTradingCoordinator:
    """
    Main coordinator that orchestrates the complete copy trading pipeline:
    1. WalletTracker detects transactions
    2. Strategy engine evaluates opportunities  
    3. Execution engine processes trades
    4. Database persistence and metrics tracking
    """
    
    def __init__(self):
        self.wallet_tracker = WalletTracker()
        self.strategy_engine = copy_trading_strategy
        self.running = False
        self.processing_lock = asyncio.Lock()
        
        # Processing statistics
        self.transactions_processed = 0
        self.copies_executed = 0
        self.copies_skipped = 0
        self.last_activity = None
        
        # Configure wallet tracker callback
        self.wallet_tracker._transaction_callback = self._on_transaction_detected
    
    async def start(self) -> Dict[str, Any]:
        """Start the complete copy trading system."""
        if self.running:
            logger.warning("Copy trading coordinator already running")
            return {"status": "already_running"}
        
        try:
            # Load tracked wallets from database
            await self._load_tracked_wallets_from_db()
            
            # Start wallet tracker
            await self.wallet_tracker.start_monitoring()
            
            # Start background processing tasks
            asyncio.create_task(self._periodic_sync_task())
            asyncio.create_task(self._metrics_calculation_task())
            
            self.running = True
            
            logger.info("Copy trading coordinator started successfully")
            
            # Emit startup thought log
            await runtime_state.emit_thought_log({
                "event": "copy_trading_started",
                "system_status": {
                    "tracked_wallets": len(self.wallet_tracker.tracked_wallets),
                    "active_chains": list(set(w.chain.value for w in self.wallet_tracker.tracked_wallets.values())),
                    "monitoring_active": self.wallet_tracker.running
                },
                "action": "begin_monitoring",
                "rationale": "Copy trading system initialization complete, monitoring active wallets"
            })
            
            return {
                "status": "started",
                "tracked_wallets": len(self.wallet_tracker.tracked_wallets),
                "monitoring_active": self.wallet_tracker.running
            }
            
        except Exception as e:
            logger.error(f"Failed to start copy trading coordinator: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> Dict[str, Any]:
        """Stop the copy trading system gracefully."""
        logger.info("Stopping copy trading coordinator...")
        
        self.running = False
        
        # Stop wallet tracker
        await self.wallet_tracker.stop_monitoring()
        
        # Wait for any in-progress processing to complete
        async with self.processing_lock:
            logger.info("All copy trading processing completed")
        
        return {
            "status": "stopped",
            "final_stats": {
                "transactions_processed": self.transactions_processed,
                "copies_executed": self.copies_executed,
                "copies_skipped": self.copies_skipped
            }
        }
    
    async def add_tracked_wallet(
        self,
        address: str,
        chain: ChainType,
        nickname: str,
        copy_settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a new wallet to track with database persistence."""
        
        try:
            async with get_db() as session:
                repos = create_copy_trading_repositories(session)
                
                # Check if wallet already exists
                existing = await repos["wallets"].get_wallet_by_address(address, chain)
                if existing:
                    return {
                        "success": False,
                        "error": f"Wallet {address} on {chain.value} already being tracked"
                    }
                
                # Create in database
                db_wallet = await repos["wallets"].create_wallet(
                    address=address,
                    chain=chain,
                    nickname=nickname,
                    copy_percentage=Decimal(str(copy_settings.get("copy_percentage", 5.0))),
                    min_trade_value_usd=Decimal(str(copy_settings.get("min_trade_value_usd", 100.0))),
                    max_position_usd=Decimal(str(copy_settings.get("max_position_usd", 1000.0))),
                    copy_mode=copy_settings.get("copy_mode", "percentage"),
                    max_slippage_bps=copy_settings.get("max_slippage_bps", 300),
                    allowed_chains=str(copy_settings.get("allowed_chains", [chain.value])),
                    copy_buy_only=copy_settings.get("copy_buy_only", False),
                    copy_sell_only=copy_settings.get("copy_sell_only", False)
                )
                
                # Add to wallet tracker
                success = await self.wallet_tracker.add_wallet(
                    address=address,
                    chain=chain,
                    nickname=nickname,
                    copy_percentage=float(copy_settings.get("copy_percentage", 5.0)),
                    min_trade_value_usd=float(copy_settings.get("min_trade_value_usd", 100.0)),
                    max_trade_value_usd=float(copy_settings.get("max_position_usd", 1000.0))
                )
                
                if success:
                    logger.info(f"Added tracked wallet {nickname} ({address}) on {chain.value}")
                    
                    # Emit thought log
                    await runtime_state.emit_thought_log({
                        "event": "wallet_added_to_tracking",
                        "wallet": {
                            "address": address,
                            "nickname": nickname,
                            "chain": chain.value,
                            "copy_percentage": copy_settings.get("copy_percentage", 5.0)
                        },
                        "action": "start_monitoring",
                        "rationale": f"New wallet added to copy trading system with {copy_settings.get('copy_percentage', 5.0)}% copy rate"
                    })
                    
                    return {
                        "success": True,
                        "wallet_id": db_wallet.id,
                        "message": f"Wallet {nickname} added and monitoring started"
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to add wallet to tracking system"
                    }
                    
        except Exception as e:
            logger.error(f"Failed to add tracked wallet: {e}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}"
            }
    
    async def remove_tracked_wallet(
        self,
        address: str,
        chain: ChainType
    ) -> Dict[str, Any]:
        """Remove a tracked wallet from both tracker and database."""
        
        try:
            async with get_db() as session:
                repos = create_copy_trading_repositories(session)
                
                # Get wallet from database
                wallet = await repos["wallets"].get_wallet_by_address(address, chain)
                if not wallet:
                    return {
                        "success": False,
                        "error": f"Wallet {address} on {chain.value} not found"
                    }
                
                # Remove from wallet tracker
                tracker_success = await self.wallet_tracker.remove_wallet(address, chain)
                
                # Remove from database (cascades to related records)
                db_success = await repos["wallets"].delete_wallet(wallet.id)
                
                if tracker_success and db_success:
                    logger.info(f"Removed tracked wallet {wallet.nickname} ({address})")
                    return {
                        "success": True,
                        "message": f"Wallet {wallet.nickname} removed from tracking"
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to remove wallet from tracking system"
                    }
                    
        except Exception as e:
            logger.error(f"Failed to remove tracked wallet: {e}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}"
            }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive copy trading system status."""
        
        try:
            async with get_db() as session:
                repos = create_copy_trading_repositories(session)
                
                # Get database statistics
                wallet_stats = await repos["wallets"].get_wallet_statistics()
                
                # Get recent activity
                recent_txs = await repos["transactions"].get_recent_transactions(limit=10)
                recent_copies = await repos["copy_trades"].get_copy_trades(
                    status=CopyTradeStatus.EXECUTED, limit=5
                )
                
                # Get strategy statistics
                strategy_stats = await self.strategy_engine.get_copy_trading_statistics()
                
                return {
                    "system": {
                        "running": self.running,
                        "wallet_tracker_active": self.wallet_tracker.running,
                        "transactions_processed": self.transactions_processed,
                        "copies_executed": self.copies_executed,
                        "copies_skipped": self.copies_skipped,
                        "last_activity": self.last_activity.isoformat() if self.last_activity else None
                    },
                    "wallets": wallet_stats,
                    "recent_activity": {
                        "transactions": len(recent_txs),
                        "recent_copies": len(recent_copies),
                        "last_transaction": recent_txs[0].timestamp.isoformat() if recent_txs else None
                    },
                    "strategy": strategy_stats
                }
                
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {
                "system": {
                    "running": self.running,
                    "error": str(e)
                }
            }
    
    async def _on_transaction_detected(self, transaction: WalletTransaction) -> None:
        """
        Callback invoked when WalletTracker detects a new transaction.
        This is the main entry point for copy trading pipeline.
        """
        
        async with self.processing_lock:
            self.transactions_processed += 1
            self.last_activity = datetime.now(timezone.utc)
            
            logger.info(
                f"Processing detected transaction: {transaction.tx_hash} "
                f"from {transaction.wallet_address} ({transaction.action} {transaction.token_symbol})"
            )
            
            try:
                # Store transaction in database
                await self._store_detected_transaction(transaction)
                
                # Get wallet configuration
                wallet_config = await self._get_wallet_config(transaction.wallet_address, transaction.chain)
                
                if not wallet_config:
                    logger.warning(f"No configuration found for wallet {transaction.wallet_address}")
                    self.copies_skipped += 1
                    return
                
                # Process through strategy engine
                execution_result = await self.strategy_engine.process_wallet_transaction(
                    transaction, wallet_config
                )
                
                if execution_result and execution_result.success:
                    self.copies_executed += 1
                    logger.info(f"Copy trade executed: {execution_result.copy_trade_id}")
                    
                    # Broadcast copy execution via WebSocket
                    await runtime_state.emit_copy_trade_executed({
                        "copy_trade_id": execution_result.copy_trade_id,
                        "original_tx": transaction.tx_hash,
                        "amount_usd": float(execution_result.actual_amount_usd or 0),
                        "token_symbol": transaction.token_symbol,
                        "chain": transaction.chain.value,
                        "wallet_nickname": wallet_config.get("nickname", "Unknown")
                    })
                else:
                    self.copies_skipped += 1
                    logger.debug("Transaction skipped or failed copy evaluation")
                
            except Exception as e:
                logger.error(f"Error processing transaction {transaction.tx_hash}: {e}")
                self.copies_skipped += 1
    
    async def _store_detected_transaction(self, transaction: WalletTransaction) -> None:
        """Store detected transaction in database."""
        
        try:
            async with get_db() as session:
                repos = create_copy_trading_repositories(session)
                
                # Get wallet ID
                wallet = await repos["wallets"].get_wallet_by_address(
                    transaction.wallet_address, transaction.chain
                )
                
                if wallet:
                    # Store transaction
                    await repos["transactions"].create_transaction(
                        tx_hash=transaction.tx_hash,
                        wallet_id=wallet.id,
                        block_number=0,  # WalletTransaction doesn't have block number
                        timestamp=transaction.timestamp,
                        chain=transaction.chain,
                        token_address=transaction.token_address,
                        token_symbol=transaction.token_symbol,
                        action=transaction.action,
                        amount_token=transaction.amount_token,
                        amount_usd=transaction.amount_usd,
                        gas_fee_usd=transaction.gas_fee_usd,
                        confidence_score=transaction.confidence_score,
                        dex_name=transaction.dex_used
                    )
                    
                    # Update wallet last activity
                    await repos["wallets"].update_last_activity(wallet.id, transaction.timestamp)
                
        except Exception as e:
            logger.error(f"Failed to store detected transaction: {e}")
    
    async def _get_wallet_config(self, address: str, chain: ChainType) -> Optional[Dict[str, Any]]:
        """Get wallet configuration for copy trading decisions."""
        
        try:
            async with get_db() as session:
                repos = create_copy_trading_repositories(session)
                
                wallet = await repos["wallets"].get_wallet_by_address(address, chain)
                
                if not wallet:
                    return None
                
                return {
                    "wallet_id": wallet.id,
                    "nickname": wallet.nickname,
                    "status": wallet.status.value,
                    "copy_mode": wallet.copy_mode.value,
                    "copy_percentage": float(wallet.copy_percentage),
                    "fixed_amount_usd": float(wallet.fixed_amount_usd) if wallet.fixed_amount_usd else None,
                    "max_position_usd": float(wallet.max_position_usd),
                    "min_trade_value_usd": float(wallet.min_trade_value_usd),
                    "max_slippage_bps": wallet.max_slippage_bps,
                    "allowed_chains": wallet.allowed_chains.split(",") if wallet.allowed_chains else [chain.value],
                    "copy_buy_only": wallet.copy_buy_only,
                    "copy_sell_only": wallet.copy_sell_only
                }
                
        except Exception as e:
            logger.error(f"Failed to get wallet config: {e}")
            return None
    
    async def _load_tracked_wallets_from_db(self) -> None:
        """Load existing tracked wallets from database into WalletTracker."""
        
        try:
            async with get_db() as session:
                repos = create_copy_trading_repositories(session)
                
                # Get all active wallets
                active_wallets = await repos["wallets"].get_active_wallets()
                
                for wallet in active_wallets:
                    await self.wallet_tracker.add_wallet(
                        address=wallet.address,
                        chain=wallet.chain,
                        nickname=wallet.nickname,
                        copy_percentage=float(wallet.copy_percentage),
                        min_trade_value_usd=float(wallet.min_trade_value_usd),
                        max_trade_value_usd=float(wallet.max_position_usd)
                    )
                
                logger.info(f"Loaded {len(active_wallets)} tracked wallets from database")
                
        except Exception as e:
            logger.error(f"Failed to load tracked wallets from database: {e}")
    
    async def _periodic_sync_task(self) -> None:
        """Periodic task to sync state and perform maintenance."""
        
        while self.running:
            try:
                await asyncio.sleep(300)  # 5 minutes
                
                # Sync wallet tracker state with database
                await self._sync_wallet_performance()
                
                # Clean up old transactions
                async with get_db() as session:
                    repos = create_copy_trading_repositories(session)
                    cleaned = await repos["transactions"].cleanup_old_transactions(days_to_keep=90)
                    if cleaned > 0:
                        logger.info(f"Cleaned up {cleaned} old transactions")
                        
            except Exception as e:
                logger.error(f"Error in periodic sync task: {e}")
    
    async def _metrics_calculation_task(self) -> None:
        """Background task to calculate and update performance metrics."""
        
        while self.running:
            try:
                await asyncio.sleep(3600)  # 1 hour
                
                # Calculate daily metrics for each wallet
                async with get_db() as session:
                    repos = create_copy_trading_repositories(session)
                    
                    active_wallets = await repos["wallets"].get_active_wallets()
                    
                    for wallet in active_wallets:
                        # Get performance for today
                        performance = await repos["copy_trades"].get_copy_trade_performance(
                            wallet_id=wallet.id, days_back=1
                        )
                        
                        # Update daily metrics
                        await repos["metrics"].create_or_update_daily_metrics(
                            date=datetime.now(timezone.utc),
                            wallet_id=wallet.id,
                            total_trades=performance["total_trades"],
                            successful_trades=performance["successful_trades"],
                            total_volume_usd=Decimal(str(performance.get("total_volume_usd", 0))),
                            realized_pnl_usd=Decimal(str(performance["total_pnl_usd"])),
                            win_rate=performance["success_rate"] / 100,
                            avg_execution_delay_seconds=performance["avg_execution_delay_seconds"]
                        )
                        
            except Exception as e:
                logger.error(f"Error in metrics calculation task: {e}")
    
    async def _sync_wallet_performance(self) -> None:
        """Sync wallet performance metrics between tracker and database."""
        
        try:
            for wallet_key, tracker_wallet in self.wallet_tracker.tracked_wallets.items():
                performance = await self.wallet_tracker.get_wallet_performance(
                    tracker_wallet.address, tracker_wallet.chain
                )
                
                if performance:
                    async with get_db() as session:
                        repos = create_copy_trading_repositories(session)
                        
                        db_wallet = await repos["wallets"].get_wallet_by_address(
                            tracker_wallet.address, tracker_wallet.chain
                        )
                        
                        if db_wallet:
                            await repos["wallets"].update_wallet_performance(
                                db_wallet.id,
                                total_trades_copied=performance["total_trades"],
                                successful_copies=performance["buy_trades"] + performance["sell_trades"],
                                total_pnl_usd=Decimal("0"),  # Would calculate actual P&L
                                win_rate=performance["success_rate"],
                                avg_profit_pct=0.0  # Would calculate from closed positions
                            )
                            
        except Exception as e:
            logger.error(f"Error syncing wallet performance: {e}")


# Global copy trading coordinator instance
copy_trading_coordinator = CopyTradingCoordinator()


# Update runtime_state to include copy trading broadcasts
async def emit_copy_trade_executed(data: Dict[str, Any]) -> None:
    """Emit copy trade execution event via WebSocket."""
    message = {
        "type": "copy_trade_executed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": data
    }
    
    # Broadcast to all connected WebSocket clients
    await runtime_state.broadcast_to_paper_clients(message)


# Monkey patch runtime_state to add copy trading method
runtime_state.emit_copy_trade_executed = emit_copy_trade_executed