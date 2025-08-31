# APP: backend
# FILE: backend/app/storage/copy_trading_repo.py
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy import select, update, delete, and_, or_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .copy_trading_models import (
    TrackedWallet, DetectedTransaction, CopyTrade, CopyTradingMetrics,
    WalletPerformanceSnapshot, ChainType, WalletStatus, CopyMode,
    CopyTradeStatus, create_wallet_key, parse_wallet_key
)

logger = logging.getLogger("storage.copy_trading_repo")


class TrackedWalletRepository:
    """Repository for tracked wallet operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_wallet(
        self,
        address: str,
        chain: ChainType,
        nickname: str,
        copy_percentage: Decimal = Decimal("5.0"),
        min_trade_value_usd: Decimal = Decimal("100.0"),
        max_position_usd: Decimal = Decimal("1000.0"),
        **kwargs
    ) -> TrackedWallet:
        """Create a new tracked wallet."""
        wallet = TrackedWallet(
            address=address.lower(),
            chain=chain,
            nickname=nickname,
            copy_percentage=copy_percentage,
            min_trade_value_usd=min_trade_value_usd,
            max_position_usd=max_position_usd,
            **kwargs
        )
        
        self.session.add(wallet)
        await self.session.commit()
        await self.session.refresh(wallet)
        
        logger.info(f"Created tracked wallet {nickname} ({address}) on {chain.value}")
        return wallet
    
    async def get_wallet_by_address(
        self,
        address: str,
        chain: ChainType
    ) -> Optional[TrackedWallet]:
        """Get wallet by address and chain."""
        stmt = select(TrackedWallet).where(
            and_(
                TrackedWallet.address == address.lower(),
                TrackedWallet.chain == chain
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_wallet_by_id(self, wallet_id: str) -> Optional[TrackedWallet]:
        """Get wallet by ID."""
        stmt = select(TrackedWallet).where(TrackedWallet.id == wallet_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_wallets(
        self,
        status: Optional[WalletStatus] = None,
        chain: Optional[ChainType] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[TrackedWallet]:
        """List tracked wallets with optional filters."""
        stmt = select(TrackedWallet)
        
        if status:
            stmt = stmt.where(TrackedWallet.status == status)
        if chain:
            stmt = stmt.where(TrackedWallet.chain == chain)
        
        stmt = stmt.order_by(desc(TrackedWallet.created_at))
        stmt = stmt.limit(limit).offset(offset)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_active_wallets(self) -> List[TrackedWallet]:
        """Get all active tracked wallets."""
        stmt = select(TrackedWallet).where(
            TrackedWallet.status == WalletStatus.ACTIVE
        ).order_by(TrackedWallet.created_at)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def update_wallet_status(
        self,
        wallet_id: str,
        status: WalletStatus
    ) -> bool:
        """Update wallet status."""
        stmt = update(TrackedWallet).where(
            TrackedWallet.id == wallet_id
        ).values(
            status=status,
            updated_at=datetime.now(timezone.utc)
        )
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
    
    async def update_wallet_performance(
        self,
        wallet_id: str,
        total_trades_copied: int,
        successful_copies: int,
        total_pnl_usd: Decimal,
        win_rate: float,
        avg_profit_pct: float
    ) -> bool:
        """Update wallet performance metrics."""
        stmt = update(TrackedWallet).where(
            TrackedWallet.id == wallet_id
        ).values(
            total_trades_copied=total_trades_copied,
            successful_copies=successful_copies,
            total_pnl_usd=total_pnl_usd,
            win_rate=win_rate,
            avg_profit_pct=avg_profit_pct,
            updated_at=datetime.now(timezone.utc)
        )
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
    
    async def update_last_activity(
        self,
        wallet_id: str,
        activity_time: datetime
    ) -> bool:
        """Update wallet's last activity timestamp."""
        stmt = update(TrackedWallet).where(
            TrackedWallet.id == wallet_id
        ).values(
            last_activity_at=activity_time,
            updated_at=datetime.now(timezone.utc)
        )
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
    
    async def delete_wallet(self, wallet_id: str) -> bool:
        """Delete a tracked wallet and all related data."""
        stmt = delete(TrackedWallet).where(TrackedWallet.id == wallet_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
    
    async def get_wallet_statistics(self) -> Dict[str, Any]:
        """Get overall wallet tracking statistics."""
        # Total wallets by status
        status_counts = await self.session.execute(
            select(TrackedWallet.status, func.count(TrackedWallet.id))
            .group_by(TrackedWallet.status)
        )
        
        # Chain distribution
        chain_counts = await self.session.execute(
            select(TrackedWallet.chain, func.count(TrackedWallet.id))
            .group_by(TrackedWallet.chain)
        )
        
        # Performance aggregates
        perf_stats = await self.session.execute(
            select(
                func.count(TrackedWallet.id),
                func.sum(TrackedWallet.total_trades_copied),
                func.sum(TrackedWallet.successful_copies),
                func.sum(TrackedWallet.total_pnl_usd),
                func.avg(TrackedWallet.win_rate)
            ).where(TrackedWallet.status == WalletStatus.ACTIVE)
        )
        
        perf_result = perf_stats.first()
        
        return {
            "status_counts": {row[0].value: row[1] for row in status_counts},
            "chain_counts": {row[0].value: row[1] for row in chain_counts},
            "performance": {
                "active_wallets": perf_result[0] or 0,
                "total_trades_copied": int(perf_result[1] or 0),
                "successful_copies": int(perf_result[2] or 0),
                "total_pnl_usd": float(perf_result[3] or 0),
                "avg_win_rate": float(perf_result[4] or 0)
            }
        }


class DetectedTransactionRepository:
    """Repository for detected transaction operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_transaction(
        self,
        tx_hash: str,
        wallet_id: str,
        block_number: int,
        timestamp: datetime,
        chain: ChainType,
        token_address: str,
        action: str,
        amount_usd: Decimal,
        **kwargs
    ) -> DetectedTransaction:
        """Create a new detected transaction."""
        transaction = DetectedTransaction(
            tx_hash=tx_hash,
            wallet_id=wallet_id,
            block_number=block_number,
            timestamp=timestamp,
            chain=chain,
            token_address=token_address.lower(),
            action=action,
            amount_usd=amount_usd,
            **kwargs
        )
        
        self.session.add(transaction)
        await self.session.commit()
        await self.session.refresh(transaction)
        
        logger.info(f"Created detected transaction {tx_hash} for wallet {wallet_id}")
        return transaction
    
    async def get_transaction_by_hash(self, tx_hash: str) -> Optional[DetectedTransaction]:
        """Get transaction by hash."""
        stmt = select(DetectedTransaction).where(
            DetectedTransaction.tx_hash == tx_hash
        ).options(selectinload(DetectedTransaction.wallet))
        
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_recent_transactions(
        self,
        wallet_id: Optional[str] = None,
        chain: Optional[ChainType] = None,
        limit: int = 50,
        hours_back: int = 24
    ) -> List[DetectedTransaction]:
        """Get recent transactions with optional filters."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        
        stmt = select(DetectedTransaction).where(
            DetectedTransaction.timestamp > cutoff_time
        ).options(selectinload(DetectedTransaction.wallet))
        
        if wallet_id:
            stmt = stmt.where(DetectedTransaction.wallet_id == wallet_id)
        if chain:
            stmt = stmt.where(DetectedTransaction.chain == chain)
        
        stmt = stmt.order_by(desc(DetectedTransaction.timestamp))
        stmt = stmt.limit(limit)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_unprocessed_transactions(self, limit: int = 100) -> List[DetectedTransaction]:
        """Get unprocessed transactions for copy trading evaluation."""
        stmt = select(DetectedTransaction).where(
            DetectedTransaction.processed == False
        ).options(selectinload(DetectedTransaction.wallet)).order_by(
            DetectedTransaction.detected_at
        ).limit(limit)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def mark_transaction_processed(
        self,
        tx_id: str,
        copy_eligible: bool,
        skip_reason: Optional[str] = None
    ) -> bool:
        """Mark transaction as processed."""
        stmt = update(DetectedTransaction).where(
            DetectedTransaction.id == tx_id
        ).values(
            processed=True,
            copy_eligible=copy_eligible,
            skip_reason=skip_reason,
            processed_at=datetime.now(timezone.utc)
        )
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
    
    async def get_wallet_transaction_history(
        self,
        wallet_id: str,
        days_back: int = 30,
        action: Optional[str] = None
    ) -> List[DetectedTransaction]:
        """Get transaction history for a specific wallet."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        stmt = select(DetectedTransaction).where(
            and_(
                DetectedTransaction.wallet_id == wallet_id,
                DetectedTransaction.timestamp > cutoff_time
            )
        )
        
        if action:
            stmt = stmt.where(DetectedTransaction.action == action)
        
        stmt = stmt.order_by(desc(DetectedTransaction.timestamp))
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def cleanup_old_transactions(self, days_to_keep: int = 90) -> int:
        """Clean up old transactions beyond retention period."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        
        stmt = delete(DetectedTransaction).where(
            DetectedTransaction.detected_at < cutoff_time
        )
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        
        logger.info(f"Cleaned up {result.rowcount} old detected transactions")
        return result.rowcount


class CopyTradeRepository:
    """Repository for copy trade operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_copy_trade(
        self,
        wallet_id: str,
        original_tx_id: str,
        trace_id: str,
        target_amount_usd: Decimal,
        chain: ChainType,
        action: str,
        **kwargs
    ) -> CopyTrade:
        """Create a new copy trade record."""
        copy_trade = CopyTrade(
            wallet_id=wallet_id,
            original_tx_id=original_tx_id,
            trace_id=trace_id,
            target_amount_usd=target_amount_usd,
            chain=chain,
            action=action,
            **kwargs
        )
        
        self.session.add(copy_trade)
        await self.session.commit()
        await self.session.refresh(copy_trade)
        
        logger.info(f"Created copy trade {copy_trade.id} for wallet {wallet_id}")
        return copy_trade
    
    async def update_copy_trade_execution(
        self,
        copy_trade_id: str,
        status: CopyTradeStatus,
        copy_tx_hash: Optional[str] = None,
        actual_amount_usd: Optional[Decimal] = None,
        actual_slippage_bps: Optional[int] = None,
        total_fees_usd: Optional[Decimal] = None,
        execution_delay_seconds: Optional[int] = None,
        failure_reason: Optional[str] = None
    ) -> bool:
        """Update copy trade with execution results."""
        updates = {
            "status": status,
            "executed_at": datetime.now(timezone.utc) if status == CopyTradeStatus.EXECUTED else None
        }
        
        if copy_tx_hash:
            updates["copy_tx_hash"] = copy_tx_hash
        if actual_amount_usd is not None:
            updates["actual_amount_usd"] = actual_amount_usd
        if actual_slippage_bps is not None:
            updates["actual_slippage_bps"] = actual_slippage_bps
        if total_fees_usd is not None:
            updates["total_fees_usd"] = total_fees_usd
        if execution_delay_seconds is not None:
            updates["execution_delay_seconds"] = execution_delay_seconds
        if failure_reason:
            updates["failure_reason"] = failure_reason
        
        stmt = update(CopyTrade).where(
            CopyTrade.id == copy_trade_id
        ).values(**updates)
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
    
    async def update_copy_trade_pnl(
        self,
        copy_trade_id: str,
        exit_price: Decimal,
        pnl_usd: Decimal,
        pnl_percentage: float
    ) -> bool:
        """Update copy trade P&L when position is closed."""
        stmt = update(CopyTrade).where(
            CopyTrade.id == copy_trade_id
        ).values(
            exit_price=exit_price,
            pnl_usd=pnl_usd,
            pnl_percentage=pnl_percentage,
            position_closed=True,
            closed_at=datetime.now(timezone.utc)
        )
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
    
    async def get_copy_trades(
        self,
        wallet_id: Optional[str] = None,
        status: Optional[CopyTradeStatus] = None,
        chain: Optional[ChainType] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[CopyTrade]:
        """Get copy trades with optional filters."""
        stmt = select(CopyTrade).options(
            selectinload(CopyTrade.wallet),
            selectinload(CopyTrade.original_transaction)
        )
        
        if wallet_id:
            stmt = stmt.where(CopyTrade.wallet_id == wallet_id)
        if status:
            stmt = stmt.where(CopyTrade.status == status)
        if chain:
            stmt = stmt.where(CopyTrade.chain == chain)
        
        stmt = stmt.order_by(desc(CopyTrade.created_at))
        stmt = stmt.limit(limit).offset(offset)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_active_positions(self, wallet_id: Optional[str] = None) -> List[CopyTrade]:
        """Get active copy trade positions (not yet closed)."""
        stmt = select(CopyTrade).where(
            and_(
                CopyTrade.status == CopyTradeStatus.EXECUTED,
                CopyTrade.position_closed == False
            )
        ).options(
            selectinload(CopyTrade.wallet),
            selectinload(CopyTrade.original_transaction)
        )
        
        if wallet_id:
            stmt = stmt.where(CopyTrade.wallet_id == wallet_id)
        
        stmt = stmt.order_by(desc(CopyTrade.executed_at))
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_copy_trade_performance(
        self,
        wallet_id: Optional[str] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """Get copy trade performance metrics."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        # Base query
        base_query = select(CopyTrade).where(
            CopyTrade.created_at > cutoff_time
        )
        
        if wallet_id:
            base_query = base_query.where(CopyTrade.wallet_id == wallet_id)
        
        # Total trades
        total_trades = await self.session.scalar(
            select(func.count()).select_from(base_query.subquery())
        )
        
        # Successful trades
        successful_trades = await self.session.scalar(
            select(func.count()).select_from(
                base_query.where(CopyTrade.status == CopyTradeStatus.EXECUTED).subquery()
            )
        )
        
        # P&L metrics for closed positions
        pnl_stats = await self.session.execute(
            select(
                func.sum(CopyTrade.pnl_usd),
                func.avg(CopyTrade.pnl_percentage),
                func.count(CopyTrade.id)
            ).select_from(
                base_query.where(CopyTrade.position_closed == True).subquery()
            )
        )
        
        pnl_result = pnl_stats.first()
        
        # Execution metrics
        exec_stats = await self.session.execute(
            select(
                func.avg(CopyTrade.execution_delay_seconds),
                func.avg(CopyTrade.actual_slippage_bps),
                func.sum(CopyTrade.total_fees_usd)
            ).select_from(
                base_query.where(CopyTrade.status == CopyTradeStatus.EXECUTED).subquery()
            )
        )
        
        exec_result = exec_stats.first()
        
        return {
            "total_trades": total_trades or 0,
            "successful_trades": successful_trades or 0,
            "success_rate": (successful_trades / total_trades * 100) if total_trades > 0 else 0.0,
            "closed_positions": pnl_result[2] or 0,
            "total_pnl_usd": float(pnl_result[0] or 0),
            "avg_pnl_percentage": float(pnl_result[1] or 0),
            "avg_execution_delay_seconds": float(exec_result[0] or 0),
            "avg_slippage_bps": float(exec_result[1] or 0),
            "total_fees_usd": float(exec_result[2] or 0)
        }


class CopyTradingMetricsRepository:
    """Repository for copy trading metrics operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_or_update_daily_metrics(
        self,
        date: datetime,
        wallet_id: Optional[str] = None,
        **metrics_data
    ) -> CopyTradingMetrics:
        """Create or update daily metrics."""
        # Check if metrics already exist
        stmt = select(CopyTradingMetrics).where(
            and_(
                func.date(CopyTradingMetrics.date) == date.date(),
                CopyTradingMetrics.wallet_id == wallet_id
            )
        )
        
        result = await self.session.execute(stmt)
        metrics = result.scalar_one_or_none()
        
        if metrics:
            # Update existing metrics
            for key, value in metrics_data.items():
                setattr(metrics, key, value)
            metrics.updated_at = datetime.now(timezone.utc)
        else:
            # Create new metrics
            metrics = CopyTradingMetrics(
                date=date,
                wallet_id=wallet_id,
                **metrics_data
            )
            self.session.add(metrics)
        
        await self.session.commit()
        await self.session.refresh(metrics)
        return metrics
    
    async def get_metrics_history(
        self,
        wallet_id: Optional[str] = None,
        days_back: int = 30
    ) -> List[CopyTradingMetrics]:
        """Get historical metrics."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        stmt = select(CopyTradingMetrics).where(
            CopyTradingMetrics.date > cutoff_time
        )
        
        if wallet_id:
            stmt = stmt.where(CopyTradingMetrics.wallet_id == wallet_id)
        
        stmt = stmt.order_by(desc(CopyTradingMetrics.date))
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


# Factory function to create all repositories
def create_copy_trading_repositories(session: AsyncSession) -> Dict[str, Any]:
    """Create all copy trading repositories."""
    return {
        "wallets": TrackedWalletRepository(session),
        "transactions": DetectedTransactionRepository(session),
        "copy_trades": CopyTradeRepository(session),
        "metrics": CopyTradingMetricsRepository(session)
    }