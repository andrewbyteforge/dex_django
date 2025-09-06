# APP: backend
# FILE: dex_django/apps/discovery/enhanced_discovery_system.py
"""
Enhanced Discovery System for DEX Sniper Pro

Monitors DEX routers to find profitable traders with realistic criteria.
Includes transaction decoding and P&L calculation.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from transaction_analyzer import transaction_analyzer, AnalysisStatus

logger = logging.getLogger("discovery.enhanced_system")


@dataclass
class EnhancedTraderProfile:
    """Enhanced trader profile with detailed metrics."""
    
    address: str
    chain: str
    
    # Trading metrics
    total_trades: int
    successful_trades: int
    failed_trades: int
    win_rate: float
    
    # Volume metrics
    total_volume_eth: Decimal
    avg_trade_size_eth: Decimal
    largest_trade_eth: Decimal
    
    # Profitability metrics
    estimated_profit_usd: float
    gas_spent_eth: Decimal
    net_profit_usd: float
    
    # Activity metrics
    first_trade: datetime
    last_trade: datetime
    active_days: int
    trades_per_day: float
    
    # DEX usage
    primary_dex: str
    dex_diversity: int  # Number of different DEXs used
    
    # Risk metrics
    max_position_eth: Decimal
    avg_hold_time: Optional[timedelta]
    
    # Scoring
    confidence_score: float
    profitability_score: float
    activity_score: float
    overall_score: float
    
    # Flags
    is_bot: bool
    is_mev: bool
    is_profitable: bool
    is_active: bool


class RouterMonitor:
    """Monitors DEX router contracts to find active traders."""
    
    # Major DEX routers on Ethereum
    ETHEREUM_ROUTERS = {
        "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D": "Uniswap V2",
        "0xE592427A0AEce92De3Edee1F18E0157C05861564": "Uniswap V3",
        "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45": "Uniswap Universal",
        "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F": "SushiSwap",
        "0x1111111254fb6c44bAC0beD2854e76F90643097d": "1inch V4",
        "0xDef1C0ded9bec7F1a1670819833240f027b25EfF": "0x Protocol",
    }
    
    # BSC routers (when you get the API key)
    BSC_ROUTERS = {
        "0x10ED43C718714eb63d5aA57B78B54704E256024E": "PancakeSwap V2",
        "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4": "PancakeSwap V3",
        "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506": "SushiSwap",
    }
    
    def __init__(self):
        self.discovered_traders: Dict[str, EnhancedTraderProfile] = {}
        self.monitoring_active = False
    
    async def discover_traders_from_routers(
        self,
        chain: str = "ethereum",
        hours_back: int = 24,
        min_trades: int = 3,
        min_win_rate: float = 60.0,
        min_confidence: float = 50.0  # Lowered from 60
    ) -> List[EnhancedTraderProfile]:
        """
        Discover traders by monitoring router contracts.
        
        This is more effective than monitoring pair contracts because
        all trades go through routers.
        """
        
        logger.info("=" * 60)
        logger.info("🚀 ENHANCED TRADER DISCOVERY")
        logger.info("=" * 60)
        
        routers = self.ETHEREUM_ROUTERS if chain == "ethereum" else {}
        
        if not routers:
            logger.warning(f"No routers configured for {chain}")
            return []
        
        all_traders = {}
        
        for router_address, router_name in routers.items():
            logger.info(f"\n🔍 Analyzing {router_name} router...")
            logger.info(f"   Address: {router_address}")
            
            # Get traders from this router
            result = await transaction_analyzer.find_traders_from_pair(
                pair_address=router_address,
                chain=chain,
                hours_back=hours_back,
                min_trades=1  # Get all traders first, filter later
            )
            
            if result.status == AnalysisStatus.SUCCESS and result.data:
                logger.info(f"   Found {len(result.data)} traders")
                
                # Process each trader
                for trader_data in result.data:
                    trader_address = trader_data['address']
                    
                    # Skip if already processed
                    if trader_address in all_traders:
                        # Update with better metrics if available
                        existing = all_traders[trader_address]
                        if trader_data['trades_count'] > existing['trades_count']:
                            all_traders[trader_address] = trader_data
                    else:
                        all_traders[trader_address] = trader_data
            else:
                logger.warning(f"   No traders found: {result.message}")
        
        # Convert to enhanced profiles and filter
        enhanced_traders = []
        
        for trader_address, trader_data in all_traders.items():
            # Apply filtering criteria
            if trader_data['trades_count'] < min_trades:
                continue
            
            if trader_data['win_rate'] < min_win_rate:
                continue
            
            if trader_data['confidence_score'] < min_confidence:
                continue
            
            # Create enhanced profile
            profile = self._create_enhanced_profile(trader_data)
            
            if profile.is_profitable:
                enhanced_traders.append(profile)
                logger.info(
                    f"✅ Profitable trader: {trader_address[:10]}... "
                    f"(Score: {profile.overall_score:.1f}, "
                    f"Trades: {profile.total_trades}, "
                    f"Win: {profile.win_rate:.1f}%)"
                )
        
        # Sort by overall score
        enhanced_traders.sort(key=lambda x: x.overall_score, reverse=True)
        
        logger.info("\n" + "=" * 60)
        logger.info(f"📊 DISCOVERY COMPLETE")
        logger.info(f"   Total traders analyzed: {len(all_traders)}")
        logger.info(f"   Profitable traders found: {len(enhanced_traders)}")
        if enhanced_traders:
            logger.info(f"   Best trader score: {enhanced_traders[0].overall_score:.1f}")
        logger.info("=" * 60)
        
        return enhanced_traders
    
    def _create_enhanced_profile(self, trader_data: Dict) -> EnhancedTraderProfile:
        """Create an enhanced profile from basic trader data."""
        
        # Calculate additional metrics
        total_volume_eth = Decimal(str(trader_data.get('total_value_moved_eth', 0)))
        trades_count = trader_data['trades_count']
        avg_trade_size = total_volume_eth / trades_count if trades_count > 0 else Decimal("0")
        
        # Calculate scores with adjusted weights
        confidence_score = trader_data['confidence_score']
        
        # Activity score (0-100)
        activity_score = min(100, trades_count * 5)  # 20 trades = 100 score
        
        # Profitability score based on win rate and estimated profit
        win_rate = trader_data['win_rate']
        profitability_score = (win_rate * 0.7) + (confidence_score * 0.3)
        
        # Overall score (weighted average)
        overall_score = (
            profitability_score * 0.5 +  # 50% weight on profitability
            activity_score * 0.3 +        # 30% weight on activity
            confidence_score * 0.2        # 20% weight on confidence
        )
        
        # Determine if trader is profitable with relaxed criteria
        is_profitable = (
            win_rate >= 60 and
            confidence_score >= 45 and  # Lowered threshold
            trades_count >= 2 and        # Lowered threshold
            overall_score >= 50          # Lowered threshold
        )
        
        # Check if likely a bot (high frequency, consistent sizes)
        is_bot = trades_count > 50  # Simple heuristic
        
        return EnhancedTraderProfile(
            address=trader_data['address'],
            chain=trader_data['chain'],
            total_trades=trades_count,
            successful_trades=trader_data.get('successful_trades', trades_count),
            failed_trades=trader_data.get('failed_trades', 0),
            win_rate=win_rate,
            total_volume_eth=total_volume_eth,
            avg_trade_size_eth=avg_trade_size,
            largest_trade_eth=avg_trade_size * 2,  # Estimate
            estimated_profit_usd=trader_data.get('total_profit_usd', 0),
            gas_spent_eth=Decimal(str(trader_data.get('total_gas_spent', 0))),
            net_profit_usd=trader_data.get('total_profit_usd', 0),
            first_trade=datetime.now(timezone.utc) - timedelta(days=1),
            last_trade=trader_data.get('last_trade', datetime.now(timezone.utc)),
            active_days=1,
            trades_per_day=trades_count,
            primary_dex=trader_data.get('most_used_dex', 'Unknown'),
            dex_diversity=trader_data.get('unique_methods', 1),
            max_position_eth=avg_trade_size * 2,
            avg_hold_time=None,
            confidence_score=confidence_score,
            profitability_score=profitability_score,
            activity_score=activity_score,
            overall_score=overall_score,
            is_bot=is_bot,
            is_mev=False,
            is_profitable=is_profitable,
            is_active=True
        )


class TransactionDecoder:
    """Decodes DEX transactions to extract swap details."""
    
    # Common swap method signatures
    SWAP_METHODS = {
        "0x7ff36ab5": "swapExactETHForTokens",
        "0x18cbafe5": "swapExactTokensForETH",
        "0x38ed1739": "swapExactTokensForTokens",
        "0xfb3bdb41": "swapETHForExactTokens",
        "0x5c11d795": "swapExactTokensForTokensSupportingFeeOnTransferTokens",
        "0x791ac947": "swapExactTokensForETHSupportingFeeOnTransferTokens",
        "0xb6f9de95": "swapExactETHForTokensSupportingFeeOnTransferTokens",
    }
    
    def decode_swap_transaction(self, tx_input: str) -> Optional[Dict[str, Any]]:
        """
        Decode a swap transaction to extract details.
        
        This is simplified - in production you'd use web3.py to properly
        decode the ABI.
        """
        
        if not tx_input or len(tx_input) < 10:
            return None
        
        method_id = tx_input[:10]
        method_name = self.SWAP_METHODS.get(method_id)
        
        if not method_name:
            return None
        
        # Simplified decoding
        return {
            "method": method_name,
            "is_buy": "ForTokens" in method_name,
            "is_sell": "ForETH" in method_name and "Exact" not in method_name,
            "supports_fee_on_transfer": "FeeOnTransfer" in method_name
        }


class ProfitCalculator:
    """Calculates estimated P&L for traders."""
    
    def __init__(self):
        self.eth_price = 2000  # Simplified - would fetch from price oracle
    
    def calculate_trade_pnl(
        self,
        entry_price: Decimal,
        exit_price: Optional[Decimal],
        amount: Decimal,
        gas_cost: Decimal
    ) -> Decimal:
        """
        Calculate P&L for a trade.
        
        In production, this would:
        1. Fetch historical prices
        2. Track entry/exit points
        3. Calculate slippage
        4. Include MEV costs
        """
        
        if not exit_price:
            # Open position - no P&L yet
            return Decimal("0")
        
        # Calculate gross profit
        price_change = exit_price - entry_price
        gross_profit = (price_change / entry_price) * amount
        
        # Subtract gas costs
        net_profit = gross_profit - gas_cost
        
        return net_profit


async def run_enhanced_discovery():
    """Run the enhanced discovery system."""
    
    logger.info("\n🚀 Starting Enhanced Discovery System\n")
    
    # Initialize components
    monitor = RouterMonitor()
    decoder = TransactionDecoder()
    calculator = ProfitCalculator()
    
    # Discover traders with relaxed criteria
    traders = await monitor.discover_traders_from_routers(
        chain="ethereum",
        hours_back=6,  # Last 6 hours
        min_trades=2,   # Lowered from 3
        min_win_rate=55.0,  # Lowered from 60
        min_confidence=45.0  # Lowered from 60
    )
    
    if traders:
        logger.info("\n" + "=" * 60)
        logger.info("🏆 TOP TRADERS FOUND")
        logger.info("=" * 60)
        
        for i, trader in enumerate(traders[:10], 1):  # Top 10
            logger.info(f"\n{i}. Trader: {trader.address}")
            logger.info(f"   Overall Score: {trader.overall_score:.1f}")
            logger.info(f"   Total Trades: {trader.total_trades}")
            logger.info(f"   Win Rate: {trader.win_rate:.1f}%")
            logger.info(f"   Volume: {trader.total_volume_eth:.4f} ETH")
            logger.info(f"   Primary DEX: {trader.primary_dex}")
            logger.info(f"   Is Bot: {'Yes' if trader.is_bot else 'No'}")
            
            # Save to database or tracking system
            # await save_trader_to_database(trader)
    else:
        logger.warning("\n⚠️ No profitable traders found with current criteria")
        logger.info("Consider:")
        logger.info("  1. Extending the time window (hours_back)")
        logger.info("  2. Lowering minimum requirements")
        logger.info("  3. Checking different routers")
    
    return traders


async def monitor_routers_continuously():
    """Continuously monitor routers for new traders."""
    
    logger.info("🔄 Starting continuous router monitoring...")
    
    monitor = RouterMonitor()
    
    while True:
        try:
            # Discover new traders every 30 minutes
            traders = await monitor.discover_traders_from_routers(
                chain="ethereum",
                hours_back=1,  # Just last hour for continuous monitoring
                min_trades=1,   # Any active trader
                min_win_rate=50.0,
                min_confidence=40.0
            )
            
            if traders:
                logger.info(f"Found {len(traders)} new active traders")
                
                # Process new traders
                for trader in traders:
                    if trader.address not in monitor.discovered_traders:
                        monitor.discovered_traders[trader.address] = trader
                        logger.info(f"🆕 New trader: {trader.address[:10]}...")
                        
                        # Emit event for copy trading system
                        # await emit_new_trader_event(trader)
            
            # Wait before next scan
            await asyncio.sleep(1800)  # 30 minutes
            
        except Exception as e:
            logger.error(f"Error in continuous monitoring: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error


if __name__ == "__main__":
    # Run the enhanced discovery
    asyncio.run(run_enhanced_discovery())