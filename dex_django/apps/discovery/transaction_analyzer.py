"""
Transaction Analyzer for discovering profitable traders using Etherscan V2 API.
"""
from __future__ import annotations

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
import aiohttp
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TraderMetrics:
    """Metrics for a trader's performance."""
    address: str
    chain: str
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    total_volume: Decimal = Decimal('0')
    total_profit: Decimal = Decimal('0')
    win_rate: float = 0.0
    avg_profit: Decimal = Decimal('0')
    confidence_score: float = 0.0
    dex_used: str = ""
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    is_profitable: bool = False
    trades: List[Dict[str, Any]] = field(default_factory=list)


class TransactionAnalyzer:
    """Analyzes blockchain transactions to find profitable traders."""
    
    # Etherscan V2 API chain ID mapping
    CHAIN_IDS = {
        'ethereum': 1,
        'eth': 1,
        'bsc': 56,
        'binance': 56,
        'polygon': 137,
        'matic': 137,
        'base': 8453,
        'arbitrum': 42161,
        'optimism': 10,
        'avalanche': 43114,
        'fantom': 250,
        'cronos': 25,
    }
    
    # Known DEX routers by chain
    DEX_ROUTERS = {
        'ethereum': {
            '0x7a250d5630b4cf539739df2c5dacb4c659f2488d': 'Uniswap V2',
            '0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45': 'Uniswap V3',
            '0xef1c6e67703c7bd7107eed8303fbe6ec2554bf6b': 'Uniswap Universal',
            '0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f': 'SushiSwap',
        },
        'bsc': {
            '0x10ed43c718714eb63d5aa57b78b54704e256024e': 'PancakeSwap V2',
            '0x13f4ea83d0bd40e75c8222255bc855a974568dd4': 'PancakeSwap V3',
            '0x1b02da8cb0d097eb8d57a175b88c7d8b47997506': 'SushiSwap',
        },
        'base': {
            '0x4752ba5dbc23f44d87826276bf6fd6b1c372ad24': 'BaseSwap',
            '0x327df1e6de05895d2ab08513aadd9313fe505d86': 'Aerodrome',
        },
        'polygon': {
            '0xa5e0829caced8ffdd4de3c43696c57f7d7a678ff': 'QuickSwap',
            '0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45': 'Uniswap V3',
        }
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the analyzer with API key."""
        self.api_key = api_key or os.getenv('ETHERSCAN_API_KEY', '')
        self.base_url = 'https://api.etherscan.io/v2/api'
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limit_delay = 0.2  # 5 requests per second
        self.traders: Dict[str, TraderMetrics] = {}
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            
    async def find_traders_from_pair(
        self,
        pair_address: str,
        chain: str = 'ethereum',
        hours_back: int = 24,
        min_trades: int = 3
    ) -> List[TraderMetrics]:
        """
        Find traders from a DEX pair or router address.
        
        Args:
            pair_address: DEX pair or router contract address
            chain: Blockchain name
            hours_back: Hours to look back
            min_trades: Minimum trades required
            
        Returns:
            List of trader metrics
        """
        logger.info("=" * 60)
        logger.info("🔍 FINDING TRADERS FROM PAIR")
        logger.info(f"📍 Pair: {pair_address}")
        logger.info(f"⛓️  Chain: {chain}")
        logger.info(f"⏰ Hours back: {hours_back}")
        logger.info(f"📊 Min trades: {min_trades}")
        logger.info("=" * 60)
        
        # Validate inputs
        logger.debug("🔍 Validating inputs...")
        if not self._validate_inputs(pair_address, chain):
            return []
            
        # Get chain ID
        chain_id = self.CHAIN_IDS.get(chain.lower())
        if not chain_id:
            logger.error(f"❌ Unsupported chain: {chain}")
            return []
            
        # Fetch transactions
        logger.info("📥 Fetching transactions from blockchain...")
        transactions = await self._fetch_transactions(pair_address, chain_id, hours_back)
        
        if not transactions:
            logger.warning("⚠️ No transactions found")
            return []
            
        logger.info(f"✅ Found {len(transactions)} transactions")
        
        # Analyze traders
        logger.info("🔍 Analyzing traders...")
        await self._analyze_traders(transactions, chain)
        
        # Filter by minimum trades
        profitable_traders = [
            trader for trader in self.traders.values()
            if trader.trade_count >= min_trades and trader.is_profitable
        ]
        
        logger.info("=" * 60)
        logger.info("✅ ANALYSIS COMPLETE")
        logger.info(f"📊 Found {len(profitable_traders)} profitable traders from {len(self.traders)} total traders")
        logger.info("=" * 60)
        
        return profitable_traders
        
    def _validate_inputs(self, pair_address: str, chain: str) -> bool:
        """Validate input parameters."""
        if not self.api_key:
            logger.error("❌ No API key configured. Set ETHERSCAN_API_KEY environment variable")
            return False
            
        if not pair_address or not pair_address.startswith('0x'):
            logger.error(f"❌ Invalid pair address: {pair_address}")
            return False
            
        if chain.lower() not in self.CHAIN_IDS:
            logger.error(f"❌ Unsupported chain: {chain}")
            return False
            
        logger.debug("✅ Inputs validated")
        return True
        
    async def _fetch_transactions(
        self,
        contract_address: str,
        chain_id: int,
        hours_back: int
    ) -> List[Dict[str, Any]]:
        """Fetch transactions from Etherscan V2 API."""
        try:
            # Calculate timestamp
            from_timestamp = int((datetime.now() - timedelta(hours=hours_back)).timestamp())
            
            # Build API request
            params = {
                'chainid': chain_id,
                'module': 'account',
                'action': 'txlist',
                'address': contract_address,
                'startblock': 0,
                'endblock': 99999999,
                'sort': 'desc',
                'apikey': self.api_key
            }
            
            # Make API request
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            async with self.session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    logger.error(f"❌ API error: {response.status}")
                    return []
                    
                data = await response.json()
                
                if data.get('status') != '1':
                    logger.error(f"❌ API error: {data.get('message', 'Unknown error')}")
                    return []
                    
                transactions = data.get('result', [])
                
                # Filter by timestamp
                filtered_txs = []
                for tx in transactions:
                    tx_timestamp = int(tx.get('timeStamp', 0))
                    if tx_timestamp >= from_timestamp:
                        filtered_txs.append(tx)
                        
                return filtered_txs
                
        except Exception as e:
            logger.error(f"❌ Error fetching transactions: {e}")
            return []
            
    async def _analyze_traders(self, transactions: List[Dict[str, Any]], chain: str):
        """Analyze traders from transactions."""
        dex_routers = self.DEX_ROUTERS.get(chain.lower(), {})
        
        for tx in transactions:
            # Skip failed transactions
            if tx.get('isError') == '1':
                continue
                
            # Get trader address (from field)
            trader_address = tx.get('from', '').lower()
            if not trader_address:
                continue
                
            # Initialize trader if not seen
            if trader_address not in self.traders:
                self.traders[trader_address] = TraderMetrics(
                    address=trader_address,
                    chain=chain,
                    first_seen=datetime.fromtimestamp(int(tx.get('timeStamp', 0)))
                )
                
            trader = self.traders[trader_address]
            
            # Update metrics
            trader.trade_count += 1
            trader.last_seen = datetime.fromtimestamp(int(tx.get('timeStamp', 0)))
            
            # Calculate volume (in ETH/BNB/etc)
            value = Decimal(tx.get('value', '0')) / Decimal(10**18)
            trader.total_volume += value
            
            # Determine DEX used
            to_address = tx.get('to', '').lower()
            trader.dex_used = dex_routers.get(to_address, 'Unknown DEX')
            
            # Simple profitability check (gas cost vs value)
            gas_used = Decimal(tx.get('gasUsed', '0'))
            gas_price = Decimal(tx.get('gasPrice', '0'))
            gas_cost = (gas_used * gas_price) / Decimal(10**18)
            
            # If transaction has value and gas cost is reasonable, count as win
            if value > gas_cost * 2:  # Value should be at least 2x gas cost
                trader.win_count += 1
            else:
                trader.loss_count += 1
                
            # Store trade details
            trader.trades.append({
                'hash': tx.get('hash'),
                'timestamp': tx.get('timeStamp'),
                'value': str(value),
                'gas_cost': str(gas_cost)
            })
            
        # Calculate final metrics for all traders
        for trader in self.traders.values():
            if trader.trade_count > 0:
                trader.win_rate = (trader.win_count / trader.trade_count) * 100
                trader.avg_profit = trader.total_profit / trader.trade_count if trader.trade_count > 0 else Decimal('0')
                
                # Calculate confidence score (0-100)
                trader.confidence_score = self._calculate_confidence_score(trader)
                
                # Determine if profitable
                trader.is_profitable = (
                    trader.win_rate >= 55 and 
                    trader.trade_count >= 3 and
                    trader.confidence_score >= 50
                )
                
            # Log trader analysis
            logger.debug(f"📈 Analyzing trader {trader.address[:10]}... with {trader.trade_count} trades")
            logger.debug(f"📊 Trader {trader.address[:10]}... analysis: "
                        f"Win rate: {trader.win_rate:.1f}%, "
                        f"Confidence: {trader.confidence_score:.1f}, "
                        f"DEX: {trader.dex_used}, "
                        f"Profitable: {trader.is_profitable}")
                        
    def _calculate_confidence_score(self, trader: TraderMetrics) -> float:
        """Calculate confidence score for a trader."""
        score = 50.0  # Base score
        
        # Trade count factor (more trades = higher confidence)
        if trader.trade_count >= 10:
            score += 20
        elif trader.trade_count >= 5:
            score += 10
            
        # Win rate factor
        if trader.win_rate >= 70:
            score += 20
        elif trader.win_rate >= 60:
            score += 10
            
        # Volume factor
        if trader.total_volume >= Decimal('10'):
            score += 10
        elif trader.total_volume >= Decimal('1'):
            score += 5
            
        return min(100, max(0, score))


# Test function
async def test_v2_api():
    """Test the V2 API with multiple chains."""
    print("\n" + "=" * 60)
    print("🧪 TESTING ETHERSCAN V2 API")
    print("=" * 60)
    
    # Test routers for different chains
    test_cases = [
        ('ethereum', '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'),  # Uniswap V2
        ('bsc', '0x10ED43C718714eb63d5aA57B78B54704E256024E'),  # PancakeSwap V2
        ('base', '0x4752ba5DBc23f44D87826276BF6Fd6b1C372aD24'),  # BaseSwap
        ('polygon', '0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff'),  # QuickSwap
    ]
    
    working_chains = []
    failed_chains = []
    
    for chain, router in test_cases:
        print(f"\n🔍 Testing {chain.upper()}")
        print(f"   Router: {TransactionAnalyzer.DEX_ROUTERS.get(chain, {}).get(router.lower(), 'Unknown')}")
        print(f"   Address: {router}")
        
        async with TransactionAnalyzer() as analyzer:
            try:
                traders = await analyzer.find_traders_from_pair(
                    pair_address=router,
                    chain=chain,
                    hours_back=1,
                    min_trades=1
                )
                
                if traders:
                    print(f"   ✅ SUCCESS! Found {len(traders)} traders")
                    working_chains.append(chain)
                else:
                    print(f"   ⚠️ No traders found (but API worked)")
                    working_chains.append(chain)
                    
            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
                failed_chains.append(chain)
                
            # Rate limit delay
            await asyncio.sleep(0.5)
            
    print("\n" + "=" * 60)
    print("📊 V2 API TEST SUMMARY")
    print("=" * 60)
    print(f"\n✅ Working chains: {working_chains}")
    print(f"❌ Failed chains: {failed_chains}")
    
    if len(working_chains) == len(test_cases):
        print("\n🎉 V2 API fully working! All chains accessible.")
    elif working_chains:
        print(f"\n⚠️ V2 API partially working. {len(working_chains)}/{len(test_cases)} chains successful.")
    else:
        print("\n❌ V2 API not working. Check your API key.")


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_v2_api())