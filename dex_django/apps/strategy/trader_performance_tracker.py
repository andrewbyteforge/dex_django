# APP: backend
# FILE: backend/app/strategy/trader_performance_tracker.py
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from dex_django.discovery.wallet_monitor import WalletTransaction
from dex_django.core.runtime_state import runtime_state

logger = logging.getLogger(__name__)


class PerformanceMetric(Enum):
    """Available performance metrics for trader evaluation."""
    WIN_RATE = "win_rate"
    TOTAL_PNL = "total_pnl"
    AVG_TRADE_SIZE = "avg_trade_size"
    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    PROFIT_FACTOR = "profit_factor"
    TRADES_PER_DAY = "trades_per_day"
    CONSISTENCY_SCORE = "consistency_score"


@dataclass
class TradeRecord:
    """Individual trade record for performance calculation."""
    tx_hash: str
    timestamp: datetime
    token_symbol: str
    token_address: str
    chain: str
    dex_name: str
    action: str  # 'buy' or 'sell'
    amount_usd: Decimal
    price_entry: Optional[Decimal] = None
    price_exit: Optional[Decimal] = None
    pnl_usd: Optional[Decimal] = None
    is_profitable: Optional[bool] = None
    hold_time_hours: Optional[float] = None
    gas_cost_usd: Optional[Decimal] = None


@dataclass
class PerformanceSnapshot:
    """Performance snapshot for a trader at a specific time."""
    timestamp: datetime
    total_trades: int
    profitable_trades: int
    win_rate: float
    total_pnl_usd: Decimal
    total_volume_usd: Decimal
    avg_trade_size_usd: Decimal
    max_drawdown_pct: float
    sharpe_ratio: Optional[float]
    profit_factor: Optional[float]
    avg_hold_time_hours: float
    trades_per_day: float
    consistency_score: float
    risk_score: float  # 0-100, higher = riskier
    confidence_level: float  # 0-100, data quality indicator


@dataclass
class TraderProfile:
    """Complete trader performance profile."""
    address: str
    first_seen: datetime
    last_activity: datetime
    total_days_active: int
    
    # Trade history
    trades: List[TradeRecord] = field(default_factory=list)
    
    # Current performance
    current_performance: Optional[PerformanceSnapshot] = None
    
    # Historical snapshots (daily)
    performance_history: List[PerformanceSnapshot] = field(default_factory=list)
    
    # Risk indicators
    suspicious_activity: bool = False
    risk_flags: List[str] = field(default_factory=list)
    
    # Metadata
    analysis_complete: bool = False
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TraderPerformanceTracker:
    """
    Advanced trader performance tracking and analysis system.
    Maintains detailed records of all followed traders' performance metrics.
    """
    
    def __init__(self):
        # In-memory trader profiles (would be database-backed in production)
        self._trader_profiles: Dict[str, TraderProfile] = {}
        
        # Performance calculation settings
        self._min_trades_for_analysis = 10
        self._analysis_window_days = 30
        self._risk_free_rate = Decimal("0.05")  # 5% annual
        
        # Risk detection thresholds
        self._max_drawdown_warning = 0.50  # 50%
        self._min_win_rate_warning = 0.30  # 30%
        self._max_trade_size_ratio = 0.80  # 80% of portfolio
        
    async def track_transaction(self, wallet_tx: WalletTransaction) -> None:
        """
        Process a new wallet transaction and update trader performance.
        """
        trader_address = wallet_tx.from_address.lower()
        
        try:
            # Get or create trader profile
            if trader_address not in self._trader_profiles:
                self._trader_profiles[trader_address] = TraderProfile(
                    address=trader_address,
                    first_seen=wallet_tx.timestamp,
                    last_activity=wallet_tx.timestamp,
                    total_days_active=1
                )
            
            profile = self._trader_profiles[trader_address]
            
            # Convert wallet transaction to trade record
            trade_record = TradeRecord(
                tx_hash=wallet_tx.tx_hash,
                timestamp=wallet_tx.timestamp,
                token_symbol=wallet_tx.token_symbol or "UNKNOWN",
                token_address=wallet_tx.token_address,
                chain=wallet_tx.chain,
                dex_name=wallet_tx.dex_name,
                action=wallet_tx.action,
                amount_usd=wallet_tx.amount_usd,
                gas_cost_usd=self._calculate_gas_cost(wallet_tx)
            )
            
            # Add trade to profile
            profile.trades.append(trade_record)
            profile.last_activity = wallet_tx.timestamp
            profile.last_updated = datetime.now(timezone.utc)
            
            # Update days active
            days_active = (profile.last_activity - profile.first_seen).days + 1
            profile.total_days_active = days_active
            
            # Recalculate performance if we have enough trades
            if len(profile.trades) >= self._min_trades_for_analysis:
                await self._update_performance_metrics(trader_address)
            
            logger.info(
                f"Tracked transaction for {trader_address[:8]}: "
                f"{wallet_tx.action} {wallet_tx.token_symbol} ${wallet_tx.amount_usd}"
            )
            
        except Exception as e:
            logger.error(f"Error tracking transaction: {e}")
    
    async def _update_performance_metrics(self, trader_address: str) -> None:
        """
        Calculate and update comprehensive performance metrics for a trader.
        """
        try:
            profile = self._trader_profiles[trader_address]
            
            # Get trades within analysis window
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self._analysis_window_days)
            recent_trades = [
                trade for trade in profile.trades 
                if trade.timestamp >= cutoff_date
            ]
            
            if len(recent_trades) < self._min_trades_for_analysis:
                return
            
            # Calculate position PnL by matching buy/sell pairs
            await self._calculate_position_pnl(recent_trades)
            
            # Calculate basic metrics
            total_trades = len(recent_trades)
            profitable_trades = len([t for t in recent_trades if t.is_profitable])
            win_rate = profitable_trades / total_trades if total_trades > 0 else 0.0
            
            total_pnl = sum(trade.pnl_usd or Decimal("0") for trade in recent_trades)
            total_volume = sum(trade.amount_usd for trade in recent_trades)
            avg_trade_size = total_volume / total_trades if total_trades > 0 else Decimal("0")
            
            # Calculate advanced metrics
            max_drawdown = await self._calculate_max_drawdown(recent_trades)
            sharpe_ratio = await self._calculate_sharpe_ratio(recent_trades)
            profit_factor = await self._calculate_profit_factor(recent_trades)
            avg_hold_time = await self._calculate_avg_hold_time(recent_trades)
            trades_per_day = total_trades / self._analysis_window_days
            consistency_score = await self._calculate_consistency_score(recent_trades)
            risk_score = await self._calculate_risk_score(recent_trades)
            
            # Create performance snapshot
            snapshot = PerformanceSnapshot(
                timestamp=datetime.now(timezone.utc),
                total_trades=total_trades,
                profitable_trades=profitable_trades,
                win_rate=win_rate,
                total_pnl_usd=total_pnl,
                total_volume_usd=total_volume,
                avg_trade_size_usd=avg_trade_size,
                max_drawdown_pct=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                profit_factor=profit_factor,
                avg_hold_time_hours=avg_hold_time,
                trades_per_day=trades_per_day,
                consistency_score=consistency_score,
                risk_score=risk_score,
                confidence_level=min(100.0, total_trades * 2.0)  # Simple confidence based on trade count
            )
            
            # Update profile
            profile.current_performance = snapshot
            profile.performance_history.append(snapshot)
            profile.analysis_complete = True
            
            # Check for risk flags
            await self._update_risk_flags(trader_address, snapshot)
            
            logger.info(
                f"Updated performance for {trader_address[:8]}: "
                f"WR={win_rate:.1%}, PnL=${total_pnl:.2f}, Trades={total_trades}"
            )
            
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
    
    async def _calculate_position_pnl(self, trades: List[TradeRecord]) -> None:
        """
        Calculate PnL for positions by matching buy/sell transactions.
        This is a simplified version - production would handle partial fills.
        """
        # Group trades by token
        token_trades = {}
        for trade in trades:
            token_key = f"{trade.token_address}_{trade.chain}"
            if token_key not in token_trades:
                token_trades[token_key] = []
            token_trades[token_key].append(trade)
        
        # Calculate PnL for each token
        for token_key, token_trade_list in token_trades.items():
            # Sort by timestamp
            token_trade_list.sort(key=lambda x: x.timestamp)
            
            position_size = Decimal("0")
            weighted_avg_price = Decimal("0")
            total_cost = Decimal("0")
            
            for trade in token_trade_list:
                if trade.action == "buy":
                    # Add to position
                    old_value = position_size * weighted_avg_price
                    new_value = trade.amount_usd
                    
                    position_size += trade.amount_usd  # Simplified - using USD value
                    total_cost += trade.amount_usd
                    
                    if position_size > 0:
                        weighted_avg_price = (old_value + new_value) / position_size
                    
                elif trade.action == "sell" and position_size > 0:
                    # Calculate PnL for this sell
                    sell_ratio = min(Decimal("1.0"), trade.amount_usd / position_size)
                    cost_basis = total_cost * sell_ratio
                    
                    trade.pnl_usd = trade.amount_usd - cost_basis
                    trade.is_profitable = trade.pnl_usd > 0
                    
                    # Reduce position
                    position_size -= min(position_size, trade.amount_usd)
                    total_cost -= min(total_cost, cost_basis)
    
    async def _calculate_max_drawdown(self, trades: List[TradeRecord]) -> float:
        """Calculate maximum drawdown percentage."""
        if not trades:
            return 0.0
        
        # Calculate running PnL
        running_pnl = Decimal("0")
        peak_pnl = Decimal("0")
        max_drawdown = 0.0
        
        for trade in sorted(trades, key=lambda x: x.timestamp):
            if trade.pnl_usd is not None:
                running_pnl += trade.pnl_usd
                peak_pnl = max(peak_pnl, running_pnl)
                
                if peak_pnl > 0:
                    current_drawdown = float((peak_pnl - running_pnl) / peak_pnl)
                    max_drawdown = max(max_drawdown, current_drawdown)
        
        return max_drawdown
    
    async def _calculate_sharpe_ratio(self, trades: List[TradeRecord]) -> Optional[float]:
        """Calculate Sharpe ratio for the trading strategy."""
        if len(trades) < 5:  # Need minimum trades for meaningful calculation
            return None
        
        # Calculate daily returns
        daily_returns = []
        trades_by_date = {}
        
        for trade in trades:
            date_key = trade.timestamp.date()
            if date_key not in trades_by_date:
                trades_by_date[date_key] = []
            trades_by_date[date_key].append(trade)
        
        for date, day_trades in trades_by_date.items():
            daily_pnl = sum(trade.pnl_usd or Decimal("0") for trade in day_trades)
            daily_returns.append(float(daily_pnl))
        
        if len(daily_returns) < 2:
            return None
        
        # Calculate Sharpe ratio
        import statistics
        
        avg_return = statistics.mean(daily_returns)
        return_std = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0
        
        if return_std == 0:
            return None
        
        # Annualized Sharpe ratio (assuming 365 trading days)
        daily_risk_free = float(self._risk_free_rate) / 365
        sharpe = (avg_return - daily_risk_free) / return_std * (365 ** 0.5)
        
        return sharpe
    
    async def _calculate_profit_factor(self, trades: List[TradeRecord]) -> Optional[float]:
        """Calculate profit factor (gross profit / gross loss)."""
        profitable_pnl = sum(
            trade.pnl_usd for trade in trades 
            if trade.pnl_usd and trade.pnl_usd > 0
        )
        losing_pnl = abs(sum(
            trade.pnl_usd for trade in trades 
            if trade.pnl_usd and trade.pnl_usd < 0
        ))
        
        if losing_pnl == 0:
            return float('inf') if profitable_pnl > 0 else None
        
        return float(profitable_pnl / losing_pnl)
    
    async def _calculate_avg_hold_time(self, trades: List[TradeRecord]) -> float:
        """Calculate average holding time in hours."""
        # Simplified - would need to match buy/sell pairs properly
        hold_times = [trade.hold_time_hours for trade in trades if trade.hold_time_hours]
        
        if not hold_times:
            return 24.0  # Default 1 day
        
        return sum(hold_times) / len(hold_times)
    
    async def _calculate_consistency_score(self, trades: List[TradeRecord]) -> float:
        """Calculate consistency score (0-100) based on profit distribution."""
        if not trades:
            return 0.0
        
        profitable_trades = [trade for trade in trades if trade.is_profitable]
        losing_trades = [trade for trade in trades if trade.is_profitable is False]
        
        if not profitable_trades:
            return 0.0
        
        # Score based on win rate and profit distribution
        win_rate = len(profitable_trades) / len(trades)
        
        # Penalty for large losing trades
        if losing_trades:
            avg_win = sum(trade.pnl_usd or Decimal("0") for trade in profitable_trades) / len(profitable_trades)
            avg_loss = sum(trade.pnl_usd or Decimal("0") for trade in losing_trades) / len(losing_trades)
            
            if avg_win > 0:
                loss_ratio = abs(float(avg_loss / avg_win))
                consistency = win_rate * (1 - min(0.5, loss_ratio * 0.1))
            else:
                consistency = win_rate * 0.5
        else:
            consistency = win_rate
        
        return min(100.0, consistency * 100)
    
    async def _calculate_risk_score(self, trades: List[TradeRecord]) -> float:
        """Calculate risk score (0-100, higher = riskier)."""
        if not trades:
            return 50.0
        
        risk_factors = []
        
        # Factor 1: Trade size variance
        trade_sizes = [float(trade.amount_usd) for trade in trades]
        if len(trade_sizes) > 1:
            import statistics
            size_cv = statistics.stdev(trade_sizes) / statistics.mean(trade_sizes)
            risk_factors.append(min(1.0, size_cv))
        
        # Factor 2: Loss magnitude
        losses = [float(trade.pnl_usd) for trade in trades if trade.pnl_usd and trade.pnl_usd < 0]
        if losses:
            max_loss = abs(min(losses))
            avg_trade_size = sum(trade_sizes) / len(trade_sizes)
            loss_factor = min(1.0, max_loss / avg_trade_size)
            risk_factors.append(loss_factor)
        
        # Factor 3: Trading frequency (very high frequency = risky)
        days_span = (max(trade.timestamp for trade in trades) - min(trade.timestamp for trade in trades)).days
        if days_span > 0:
            trades_per_day = len(trades) / days_span
            freq_factor = min(1.0, trades_per_day / 10.0)  # >10 trades/day = high risk
            risk_factors.append(freq_factor)
        
        if not risk_factors:
            return 50.0
        
        avg_risk = sum(risk_factors) / len(risk_factors)
        return min(100.0, avg_risk * 100)
    
    async def _update_risk_flags(self, trader_address: str, snapshot: PerformanceSnapshot) -> None:
        """Update risk flags based on performance snapshot."""
        profile = self._trader_profiles[trader_address]
        profile.risk_flags.clear()
        
        # High drawdown warning
        if snapshot.max_drawdown_pct > self._max_drawdown_warning:
            profile.risk_flags.append(f"HIGH_DRAWDOWN:{snapshot.max_drawdown_pct:.1%}")
        
        # Low win rate warning
        if snapshot.win_rate < self._min_win_rate_warning:
            profile.risk_flags.append(f"LOW_WIN_RATE:{snapshot.win_rate:.1%}")
        
        # High risk score
        if snapshot.risk_score > 75:
            profile.risk_flags.append(f"HIGH_RISK_SCORE:{snapshot.risk_score:.0f}")
        
        # Inconsistent performance
        if snapshot.consistency_score < 40:
            profile.risk_flags.append(f"INCONSISTENT:{snapshot.consistency_score:.0f}")
        
        # Update suspicious activity flag
        profile.suspicious_activity = len(profile.risk_flags) >= 3
    
    def _calculate_gas_cost(self, wallet_tx: WalletTransaction) -> Optional[Decimal]:
        """Calculate gas cost in USD for a transaction."""
        if not wallet_tx.gas_used or not wallet_tx.gas_price_gwei:
            return None
        
        # Mock ETH price - would use real pricing service
        eth_price_usd = Decimal("2500.0")
        gas_cost_eth = Decimal(wallet_tx.gas_used) * wallet_tx.gas_price_gwei / Decimal("1e9")
        
        return gas_cost_eth * eth_price_usd
    
    async def get_trader_performance(self, trader_address: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive performance data for a trader."""
        trader_address = trader_address.lower()
        
        if trader_address not in self._trader_profiles:
            return None
        
        profile = self._trader_profiles[trader_address]
        
        if not profile.current_performance:
            return {
                "address": trader_address,
                "status": "insufficient_data",
                "total_trades": len(profile.trades),
                "min_trades_needed": self._min_trades_for_analysis
            }
        
        perf = profile.current_performance
        
        return {
            "address": trader_address,
            "status": "active",
            "first_seen": profile.first_seen.isoformat(),
            "last_activity": profile.last_activity.isoformat(),
            "days_active": profile.total_days_active,
            "performance": {
                "total_trades": perf.total_trades,
                "win_rate": perf.win_rate,
                "total_pnl_usd": float(perf.total_pnl_usd),
                "total_volume_usd": float(perf.total_volume_usd),
                "avg_trade_size_usd": float(perf.avg_trade_size_usd),
                "max_drawdown_pct": perf.max_drawdown_pct,
                "sharpe_ratio": perf.sharpe_ratio,
                "profit_factor": perf.profit_factor,
                "trades_per_day": perf.trades_per_day,
                "consistency_score": perf.consistency_score,
                "risk_score": perf.risk_score,
                "confidence_level": perf.confidence_level
            },
            "risk_assessment": {
                "suspicious_activity": profile.suspicious_activity,
                "risk_flags": profile.risk_flags,
                "recommendation": self._get_copy_recommendation(profile)
            },
            "recent_trades": len([
                trade for trade in profile.trades[-10:] 
                if trade.timestamp >= datetime.now(timezone.utc) - timedelta(days=7)
            ])
        }
    
    def _get_copy_recommendation(self, profile: TraderProfile) -> str:
        """Get copy trading recommendation for a trader."""
        if not profile.current_performance:
            return "insufficient_data"
        
        perf = profile.current_performance
        
        if profile.suspicious_activity:
            return "avoid"
        
        if perf.win_rate >= 0.6 and perf.consistency_score >= 60 and perf.risk_score <= 60:
            return "recommended"
        elif perf.win_rate >= 0.45 and perf.consistency_score >= 40:
            return "cautious"
        else:
            return "avoid"
    
    async def get_top_performers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top performing traders sorted by a composite score."""
        performers = []
        
        for address, profile in self._trader_profiles.items():
            if not profile.current_performance or profile.suspicious_activity:
                continue
            
            perf = profile.current_performance
            
            # Calculate composite score
            score = (
                perf.win_rate * 40 +  # 40% weight on win rate
                min(1.0, float(perf.total_pnl_usd) / 1000) * 30 +  # 30% weight on PnL (capped)
                perf.consistency_score / 100 * 20 +  # 20% weight on consistency
                (100 - perf.risk_score) / 100 * 10  # 10% weight on low risk
            )
            
            performers.append({
                "address": address,
                "score": score,
                "performance": profile.current_performance
            })
        
        # Sort by score and return top performers
        performers.sort(key=lambda x: x["score"], reverse=True)
        
        return [
            await self.get_trader_performance(p["address"]) 
            for p in performers[:limit]
        ]
    
    async def cleanup_old_data(self, days_to_keep: int = 90) -> None:
        """Clean up old performance data to manage memory usage."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        
        for profile in self._trader_profiles.values():
            # Remove old trades
            profile.trades = [
                trade for trade in profile.trades 
                if trade.timestamp >= cutoff_date
            ]
            
            # Remove old performance snapshots
            profile.performance_history = [
                snapshot for snapshot in profile.performance_history
                if snapshot.timestamp >= cutoff_date
            ]
        
        logger.info(f"Cleaned up performance data older than {days_to_keep} days")


# Global trader performance tracker instance
trader_performance_tracker = TraderPerformanceTracker()