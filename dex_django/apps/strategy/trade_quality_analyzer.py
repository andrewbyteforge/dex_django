# APP: backend
# FILE: backend/app/strategy/trade_quality_analyzer.py
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from dex_django.storage.copy_trading_repo import create_copy_trading_repositories
from dex_django.core.database import get_db

logger = logging.getLogger("strategy.trade_quality")


class TradeQuality(Enum):
    """Trade quality classifications."""
    EXCELLENT = "excellent"  # 80-100 score
    GOOD = "good"           # 60-79 score
    AVERAGE = "average"     # 40-59 score
    POOR = "poor"          # 0-39 score


@dataclass
class QualityMetrics:
    """Comprehensive quality metrics for a trader."""
    overall_score: float  # 0-100
    quality_level: TradeQuality
    
    # Performance metrics
    win_rate: float
    total_trades: int
    profitable_trades: int
    avg_profit_pct: float
    total_pnl_usd: Decimal
    
    # Consistency metrics
    consistency_score: float  # How consistent are the profits
    drawdown_score: float    # Maximum drawdown penalty
    activity_score: float    # Trading frequency and recency
    
    # Risk metrics
    risk_adjusted_return: float  # Return per unit of risk
    volatility: float           # Standard deviation of returns
    sharpe_ratio: float        # Risk-adjusted performance
    
    # Advanced metrics
    trend_following_ability: float  # Ability to follow trends
    market_timing_score: float     # Entry/exit timing quality
    token_selection_score: float   # Quality of token picks
    
    # Reliability metrics
    execution_reliability: float   # How often trades execute successfully
    detection_speed: float        # How quickly we detect their trades
    
    # Meta metrics
    days_tracked: int
    last_activity_days_ago: int
    recommendation: str  # Text recommendation


class TradeQualityAnalyzer:
    """
    Advanced system to analyze and score the quality of tracked traders.
    Uses multiple metrics to identify high-alpha traders worth copying.
    """
    
    def __init__(self):
        self.scoring_weights = {
            "win_rate": 0.25,           # 25% weight on win rate
            "profitability": 0.20,      # 20% weight on total profits
            "consistency": 0.15,        # 15% weight on consistency
            "activity": 0.10,           # 10% weight on activity level
            "risk_management": 0.10,    # 10% weight on risk control
            "market_timing": 0.10,      # 10% weight on timing skills
            "reliability": 0.10         # 10% weight on execution reliability
        }
    
    async def analyze_trader_quality(
        self,
        trader_id: str,
        analysis_period_days: int = 30
    ) -> QualityMetrics:
        """
        Perform comprehensive quality analysis of a tracked trader.
        Returns detailed metrics and overall quality score.
        """
        
        logger.info(f"Analyzing trader quality for {trader_id}")
        
        try:
            async with get_db() as session:
                repos = create_copy_trading_repositories(session)
                
                # Get trader info
                trader = await repos["wallets"].get_wallet_by_id(trader_id)
                if not trader:
                    raise ValueError(f"Trader {trader_id} not found")
                
                # Get transaction history
                transactions = await repos["transactions"].get_wallet_transaction_history(
                    trader_id, days_back=analysis_period_days
                )
                
                # Get copy trade history
                copy_trades = await repos["copy_trades"].get_copy_trades(
                    wallet_id=trader_id, limit=200
                )
                
                # Calculate all metrics
                performance_metrics = await self._calculate_performance_metrics(
                    transactions, copy_trades
                )
                consistency_metrics = await self._calculate_consistency_metrics(
                    transactions, copy_trades
                )
                risk_metrics = await self._calculate_risk_metrics(
                    transactions, copy_trades
                )
                advanced_metrics = await self._calculate_advanced_metrics(
                    transactions, copy_trades
                )
                reliability_metrics = await self._calculate_reliability_metrics(
                    copy_trades
                )
                
                # Calculate overall score
                overall_score = await self._calculate_overall_score(
                    performance_metrics,
                    consistency_metrics,
                    risk_metrics,
                    advanced_metrics,
                    reliability_metrics
                )
                
                # Determine quality level
                quality_level = self._get_quality_level(overall_score)
                
                # Generate recommendation
                recommendation = await self._generate_recommendation(
                    overall_score, quality_level, performance_metrics, 
                    consistency_metrics, risk_metrics
                )
                
                return QualityMetrics(
                    overall_score=overall_score,
                    quality_level=quality_level,
                    win_rate=performance_metrics.get("win_rate", 0.0),
                    total_trades=performance_metrics.get("total_trades", 0),
                    profitable_trades=performance_metrics.get("profitable_trades", 0),
                    avg_profit_pct=performance_metrics.get("avg_profit_pct", 0.0),
                    total_pnl_usd=performance_metrics.get("total_pnl_usd", Decimal("0")),
                    consistency_score=consistency_metrics.get("consistency_score", 0.0),
                    drawdown_score=consistency_metrics.get("drawdown_score", 0.0),
                    activity_score=consistency_metrics.get("activity_score", 0.0),
                    risk_adjusted_return=risk_metrics.get("risk_adjusted_return", 0.0),
                    volatility=risk_metrics.get("volatility", 0.0),
                    sharpe_ratio=risk_metrics.get("sharpe_ratio", 0.0),
                    trend_following_ability=advanced_metrics.get("trend_following", 0.0),
                    market_timing_score=advanced_metrics.get("market_timing", 0.0),
                    token_selection_score=advanced_metrics.get("token_selection", 0.0),
                    execution_reliability=reliability_metrics.get("execution_reliability", 0.0),
                    detection_speed=reliability_metrics.get("detection_speed", 0.0),
                    days_tracked=len(set(tx.timestamp.date() for tx in transactions)),
                    last_activity_days_ago=reliability_metrics.get("days_since_last_activity", 999),
                    recommendation=recommendation
                )
                
        except Exception as e:
            logger.error(f"Failed to analyze trader quality: {e}")
            # Return default metrics on error
            return QualityMetrics(
                overall_score=0.0,
                quality_level=TradeQuality.POOR,
                win_rate=0.0, total_trades=0, profitable_trades=0,
                avg_profit_pct=0.0, total_pnl_usd=Decimal("0"),
                consistency_score=0.0, drawdown_score=0.0, activity_score=0.0,
                risk_adjusted_return=0.0, volatility=0.0, sharpe_ratio=0.0,
                trend_following_ability=0.0, market_timing_score=0.0,
                token_selection_score=0.0, execution_reliability=0.0,
                detection_speed=0.0, days_tracked=0,
                last_activity_days_ago=999,
                recommendation="Analysis failed - insufficient data"
            )
    
    async def _calculate_performance_metrics(
        self, 
        transactions: List[Any], 
        copy_trades: List[Any]
    ) -> Dict[str, Any]:
        """Calculate basic performance metrics."""
        
        if not copy_trades:
            return {
                "win_rate": 0.0,
                "total_trades": 0,
                "profitable_trades": 0,
                "avg_profit_pct": 0.0,
                "total_pnl_usd": Decimal("0")
            }
        
        # Calculate from closed copy trades (those with P&L)
        closed_trades = [trade for trade in copy_trades if trade.position_closed and trade.pnl_usd is not None]
        
        total_trades = len(copy_trades)
        profitable_trades = len([trade for trade in closed_trades if trade.pnl_usd > 0])
        
        win_rate = (profitable_trades / len(closed_trades) * 100) if closed_trades else 0.0
        
        total_pnl = sum(trade.pnl_usd for trade in closed_trades if trade.pnl_usd)
        avg_profit_pct = (sum(trade.pnl_percentage for trade in closed_trades if trade.pnl_percentage) / len(closed_trades)) if closed_trades else 0.0
        
        return {
            "win_rate": min(win_rate, 100.0),  # Cap at 100%
            "total_trades": total_trades,
            "profitable_trades": profitable_trades,
            "avg_profit_pct": avg_profit_pct,
            "total_pnl_usd": total_pnl or Decimal("0")
        }
    
    async def _calculate_consistency_metrics(
        self, 
        transactions: List[Any], 
        copy_trades: List[Any]
    ) -> Dict[str, Any]:
        """Calculate consistency and stability metrics."""
        
        if not copy_trades:
            return {
                "consistency_score": 0.0,
                "drawdown_score": 0.0,
                "activity_score": 0.0
            }
        
        # Consistency based on standard deviation of returns
        closed_trades = [trade for trade in copy_trades if trade.position_closed and trade.pnl_percentage is not None]
        
        if len(closed_trades) < 3:
            consistency_score = 0.0
            drawdown_score = 0.0
        else:
            returns = [float(trade.pnl_percentage) for trade in closed_trades]
            avg_return = sum(returns) / len(returns)
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            std_dev = variance ** 0.5
            
            # Lower standard deviation = higher consistency (inverted score)
            consistency_score = max(0, 100 - (std_dev * 2))  # Scale and invert
            
            # Calculate maximum drawdown
            cumulative_returns = []
            running_total = 0
            for ret in returns:
                running_total += ret
                cumulative_returns.append(running_total)
            
            peak = cumulative_returns[0]
            max_drawdown = 0
            for value in cumulative_returns:
                if value > peak:
                    peak = value
                drawdown = peak - value
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            # Score inversely proportional to drawdown
            drawdown_score = max(0, 100 - (max_drawdown * 2))
        
        # Activity score based on trading frequency and recency
        if transactions:
            days_active = len(set(tx.timestamp.date() for tx in transactions))
            last_activity = max(tx.timestamp for tx in transactions)
            days_since_last = (datetime.now(timezone.utc) - last_activity).days
            
            # Higher score for more active and more recent
            activity_score = min(100, (days_active * 2) - days_since_last)
            activity_score = max(0, activity_score)
        else:
            activity_score = 0.0
        
        return {
            "consistency_score": consistency_score,
            "drawdown_score": drawdown_score,
            "activity_score": activity_score
        }
    
    async def _calculate_risk_metrics(
        self, 
        transactions: List[Any], 
        copy_trades: List[Any]
    ) -> Dict[str, Any]:
        """Calculate risk-adjusted performance metrics."""
        
        closed_trades = [trade for trade in copy_trades if trade.position_closed and trade.pnl_percentage is not None]
        
        if len(closed_trades) < 5:
            return {
                "risk_adjusted_return": 0.0,
                "volatility": 0.0,
                "sharpe_ratio": 0.0
            }
        
        returns = [float(trade.pnl_percentage) for trade in closed_trades]
        avg_return = sum(returns) / len(returns)
        
        # Calculate volatility (standard deviation)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        volatility = variance ** 0.5
        
        # Calculate Sharpe ratio (assuming risk-free rate of 0)
        sharpe_ratio = (avg_return / volatility) if volatility > 0 else 0.0
        
        # Risk-adjusted return score
        risk_adjusted_return = max(0, min(100, (sharpe_ratio * 20) + 50))  # Scale to 0-100
        
        return {
            "risk_adjusted_return": risk_adjusted_return,
            "volatility": volatility,
            "sharpe_ratio": sharpe_ratio
        }
    
    async def _calculate_advanced_metrics(
        self, 
        transactions: List[Any], 
        copy_trades: List[Any]
    ) -> Dict[str, Any]:
        """Calculate advanced trading skill metrics."""
        
        if len(transactions) < 10:
            return {
                "trend_following": 50.0,  # Neutral score
                "market_timing": 50.0,
                "token_selection": 50.0
            }
        
        # Trend following ability - look at buy low / sell high patterns
        buy_transactions = [tx for tx in transactions if tx.action == "buy"]
        sell_transactions = [tx for tx in transactions if tx.action == "sell"]
        
        trend_following_score = 75.0  # Base score - would need price data for accurate calculation
        
        # Market timing - analyze transaction timing relative to market conditions
        # This would require market data integration
        market_timing_score = 60.0  # Placeholder
        
        # Token selection - diversity and quality of tokens traded
        unique_tokens = set(tx.token_address for tx in transactions)
        token_diversity = min(100, len(unique_tokens) * 5)  # More diversity = higher score
        
        # Quality based on whether tokens had significant price movements
        token_selection_score = min(100, token_diversity + 20)  # Placeholder calculation
        
        return {
            "trend_following": trend_following_score,
            "market_timing": market_timing_score,
            "token_selection": token_selection_score
        }
    
    async def _calculate_reliability_metrics(
        self, 
        copy_trades: List[Any]
    ) -> Dict[str, Any]:
        """Calculate execution and reliability metrics."""
        
        if not copy_trades:
            return {
                "execution_reliability": 0.0,
                "detection_speed": 0.0,
                "days_since_last_activity": 999
            }
        
        # Execution reliability - percentage of successful trades
        executed_trades = len([trade for trade in copy_trades if trade.status.value == "executed"])
        execution_reliability = (executed_trades / len(copy_trades) * 100) if copy_trades else 0.0
        
        # Detection speed - average execution delay
        delay_times = [trade.execution_delay_seconds for trade in copy_trades 
                      if trade.execution_delay_seconds is not None]
        
        if delay_times:
            avg_delay = sum(delay_times) / len(delay_times)
            # Score inversely proportional to delay (lower delay = higher score)
            detection_speed = max(0, 100 - (avg_delay / 2))  # Scale based on seconds
        else:
            detection_speed = 50.0  # Neutral score
        
        # Days since last activity
        if copy_trades:
            latest_trade = max(copy_trades, key=lambda x: x.created_at)
            days_since_last = (datetime.now(timezone.utc) - latest_trade.created_at).days
        else:
            days_since_last = 999
        
        return {
            "execution_reliability": execution_reliability,
            "detection_speed": detection_speed,
            "days_since_last_activity": days_since_last
        }
    
    async def _calculate_overall_score(
        self,
        performance_metrics: Dict[str, Any],
        consistency_metrics: Dict[str, Any],
        risk_metrics: Dict[str, Any],
        advanced_metrics: Dict[str, Any],
        reliability_metrics: Dict[str, Any]
    ) -> float:
        """Calculate weighted overall quality score."""
        
        # Component scores (0-100 scale)
        win_rate_score = min(100, performance_metrics.get("win_rate", 0) * 1.2)  # Slight bonus
        
        # Profitability score based on total P&L and trade count
        total_pnl = float(performance_metrics.get("total_pnl_usd", 0))
        total_trades = performance_metrics.get("total_trades", 0)
        
        if total_trades > 0:
            avg_pnl_per_trade = total_pnl / total_trades
            profitability_score = min(100, max(0, (avg_pnl_per_trade * 2) + 50))
        else:
            profitability_score = 0.0
        
        # Other component scores
        consistency_score = consistency_metrics.get("consistency_score", 0)
        activity_score = consistency_metrics.get("activity_score", 0)
        risk_mgmt_score = risk_metrics.get("risk_adjusted_return", 0)
        timing_score = advanced_metrics.get("market_timing", 50)
        reliability_score = reliability_metrics.get("execution_reliability", 0)
        
        # Apply weights
        overall_score = (
            win_rate_score * self.scoring_weights["win_rate"] +
            profitability_score * self.scoring_weights["profitability"] +
            consistency_score * self.scoring_weights["consistency"] +
            activity_score * self.scoring_weights["activity"] +
            risk_mgmt_score * self.scoring_weights["risk_management"] +
            timing_score * self.scoring_weights["market_timing"] +
            reliability_score * self.scoring_weights["reliability"]
        )
        
        return min(100.0, max(0.0, overall_score))
    
    def _get_quality_level(self, score: float) -> TradeQuality:
        """Convert numeric score to quality level."""
        if score >= 80:
            return TradeQuality.EXCELLENT
        elif score >= 60:
            return TradeQuality.GOOD
        elif score >= 40:
            return TradeQuality.AVERAGE
        else:
            return TradeQuality.POOR
    
    async def _generate_recommendation(
        self,
        overall_score: float,
        quality_level: TradeQuality,
        performance_metrics: Dict[str, Any],
        consistency_metrics: Dict[str, Any],
        risk_metrics: Dict[str, Any]
    ) -> str:
        """Generate human-readable recommendation."""
        
        total_trades = performance_metrics.get("total_trades", 0)
        win_rate = performance_metrics.get("win_rate", 0)
        total_pnl = performance_metrics.get("total_pnl_usd", Decimal("0"))
        
        if total_trades < 5:
            return "⏳ Insufficient data - need more trading history for reliable assessment"
        
        if quality_level == TradeQuality.EXCELLENT:
            return f"🌟 Excellent trader! {win_rate:.1f}% win rate with ${float(total_pnl):.0f} profit. Highly recommended for copying."
        elif quality_level == TradeQuality.GOOD:
            return f"✅ Good trader with solid performance. {win_rate:.1f}% win rate. Consider copying with moderate allocation."
        elif quality_level == TradeQuality.AVERAGE:
            return f"⚖️ Average performance trader. {win_rate:.1f}% win rate. Copy with caution and small allocation."
        else:
            return f"⚠️ Poor performance trader. {win_rate:.1f}% win rate with ${float(total_pnl):.0f} P&L. Not recommended for copying."
    
    async def get_top_quality_traders(
        self, 
        limit: int = 10
    ) -> List[Tuple[str, QualityMetrics]]:
        """Get top quality traders sorted by overall score."""
        
        try:
            async with get_db() as session:
                repos = create_copy_trading_repositories(session)
                
                # Get all active traders
                active_traders = await repos["wallets"].get_active_wallets()
                
                # Analyze each trader
                trader_scores = []
                for trader in active_traders:
                    metrics = await self.analyze_trader_quality(trader.id)
                    trader_scores.append((trader.id, metrics))
                
                # Sort by overall score descending
                trader_scores.sort(key=lambda x: x[1].overall_score, reverse=True)
                
                return trader_scores[:limit]
                
        except Exception as e:
            logger.error(f"Failed to get top quality traders: {e}")
            return []


# Global trade quality analyzer instance
trade_quality_analyzer = TradeQualityAnalyzer()