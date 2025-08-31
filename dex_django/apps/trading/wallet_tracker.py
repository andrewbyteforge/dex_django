# APP: backend
# FILE: backend/app/copy_trading/wallet_tracker.py
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum

import httpx

logger = logging.getLogger("copy_trading.wallet_tracker")


class WalletStatus(Enum):
    """Wallet tracking status."""
    ACTIVE = "active"
    PAUSED = "paused" 
    BLACKLISTED = "blacklisted"


class ChainType(Enum):
    """Supported chains for wallet tracking."""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    BASE = "base"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"


@dataclass
class TrackedWallet:
    """Configuration for a wallet being tracked."""
    address: str
    chain: ChainType
    nickname: str
    status: WalletStatus
    copy_percentage: Decimal  # 0.0 to 100.0
    min_trade_value_usd: Decimal
    max_trade_value_usd: Decimal
    added_at: datetime
    last_activity: Optional[datetime] = None
    success_rate: float = 0.0
    total_trades_copied: int = 0
    avg_profit_pct: float = 0.0


@dataclass
class WalletTransaction:
    """Detected transaction from tracked wallet."""
    tx_hash: str
    wallet_address: str
    chain: ChainType
    timestamp: datetime
    token_address: str
    token_symbol: str
    action: str  # "buy", "sell"
    amount_token: Decimal
    amount_usd: Decimal
    gas_fee_usd: Decimal
    dex_used: str
    confidence_score: float  # 0.0 to 1.0


class WalletTracker:
    """Tracks multiple wallets across chains for copy trading opportunities."""
    
    def __init__(self):
        self.tracked_wallets: Dict[str, TrackedWallet] = {}
        self.recent_transactions: List[WalletTransaction] = []
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.running = False
        self.polling_interval = 15  # seconds
        
        # Chain-specific RPC endpoints (placeholder - should come from config)
        self.rpc_endpoints = {
            ChainType.ETHEREUM: "https://eth.llamarpc.com",
            ChainType.BSC: "https://bsc-dataseed.binance.org",
            ChainType.BASE: "https://mainnet.base.org",
            ChainType.POLYGON: "https://polygon-rpc.com",
            ChainType.ARBITRUM: "https://arb1.arbitrum.io/rpc"
        }
    
    async def add_wallet(
        self,
        address: str,
        chain: ChainType,
        nickname: str,
        copy_percentage: float = 5.0,
        min_trade_value_usd: float = 100.0,
        max_trade_value_usd: float = 2000.0
    ) -> bool:
        """Add a wallet to track for copy trading."""
        try:
            # Validate wallet address format
            if not self._is_valid_address(address, chain):
                logger.error(f"Invalid wallet address format: {address}")
                return False
            
            # Check if wallet already tracked
            wallet_key = f"{chain.value}:{address.lower()}"
            if wallet_key in self.tracked_wallets:
                logger.warning(f"Wallet {address} on {chain.value} already being tracked")
                return False
            
            # Create tracked wallet entry
            tracked_wallet = TrackedWallet(
                address=address.lower(),
                chain=chain,
                nickname=nickname,
                status=WalletStatus.ACTIVE,
                copy_percentage=Decimal(str(copy_percentage)),
                min_trade_value_usd=Decimal(str(min_trade_value_usd)),
                max_trade_value_usd=Decimal(str(max_trade_value_usd)),
                added_at=datetime.now(timezone.utc)
            )
            
            self.tracked_wallets[wallet_key] = tracked_wallet
            logger.info(f"Added wallet {nickname} ({address}) on {chain.value} for tracking")
            
            # Fetch recent transaction history for baseline
            await self._fetch_wallet_history(tracked_wallet)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add wallet {address}: {e}")
            return False
    
    async def remove_wallet(self, address: str, chain: ChainType) -> bool:
        """Remove a wallet from tracking."""
        wallet_key = f"{chain.value}:{address.lower()}"
        if wallet_key in self.tracked_wallets:
            wallet = self.tracked_wallets.pop(wallet_key)
            logger.info(f"Removed wallet {wallet.nickname} from tracking")
            return True
        return False
    
    async def start_monitoring(self) -> None:
        """Start continuous wallet monitoring."""
        if self.running:
            logger.warning("Wallet monitoring already running")
            return
            
        self.running = True
        logger.info(f"Starting wallet monitoring for {len(self.tracked_wallets)} wallets")
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
    
    async def stop_monitoring(self) -> None:
        """Stop wallet monitoring."""
        self.running = False
        logger.info("Stopping wallet monitoring")
    
    async def get_recent_transactions(self, limit: int = 50) -> List[WalletTransaction]:
        """Get recent transactions from tracked wallets."""
        # Sort by timestamp descending
        sorted_txs = sorted(
            self.recent_transactions,
            key=lambda tx: tx.timestamp,
            reverse=True
        )
        return sorted_txs[:limit]
    
    async def get_wallet_performance(self, address: str, chain: ChainType) -> Optional[Dict[str, Any]]:
        """Get performance metrics for a specific wallet."""
        wallet_key = f"{chain.value}:{address.lower()}"
        wallet = self.tracked_wallets.get(wallet_key)
        
        if not wallet:
            return None
        
        # Calculate performance metrics
        wallet_txs = [
            tx for tx in self.recent_transactions 
            if tx.wallet_address.lower() == address.lower() and tx.chain == chain
        ]
        
        if not wallet_txs:
            return {
                "nickname": wallet.nickname,
                "total_trades": 0,
                "success_rate": 0.0,
                "avg_profit_pct": 0.0,
                "last_activity": None
            }
        
        # Simple performance calculation (buy/sell pairs)
        buy_trades = [tx for tx in wallet_txs if tx.action == "buy"]
        sell_trades = [tx for tx in wallet_txs if tx.action == "sell"]
        
        return {
            "nickname": wallet.nickname,
            "total_trades": len(wallet_txs),
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "success_rate": wallet.success_rate,
            "avg_profit_pct": wallet.avg_profit_pct,
            "last_activity": wallet.last_activity.isoformat() if wallet.last_activity else None
        }
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop that checks all tracked wallets."""
        while self.running:
            try:
                if not self.tracked_wallets:
                    await asyncio.sleep(self.polling_interval)
                    continue
                
                logger.debug(f"Checking {len(self.tracked_wallets)} tracked wallets")
                
                # Check each wallet for new transactions
                tasks = []
                for wallet in self.tracked_wallets.values():
                    if wallet.status == WalletStatus.ACTIVE:
                        tasks.append(self._check_wallet_activity(wallet))
                
                # Execute checks concurrently
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Clean old transactions (keep last 24 hours)
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                self.recent_transactions = [
                    tx for tx in self.recent_transactions 
                    if tx.timestamp > cutoff
                ]
                
                await asyncio.sleep(self.polling_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.polling_interval)
    
    async def _check_wallet_activity(self, wallet: TrackedWallet) -> None:
        """Check for new transactions from a specific wallet."""
        try:
            # Get recent transactions for this wallet
            new_txs = await self._fetch_recent_transactions(wallet)
            
            for tx in new_txs:
                # Skip if we already have this transaction
                existing = any(
                    existing_tx.tx_hash == tx.tx_hash 
                    for existing_tx in self.recent_transactions
                )
                if existing:
                    continue
                
                # Filter by trade value thresholds
                if tx.amount_usd < wallet.min_trade_value_usd:
                    logger.debug(f"Skipping small trade: ${tx.amount_usd}")
                    continue
                    
                if tx.amount_usd > wallet.max_trade_value_usd:
                    logger.debug(f"Skipping large trade: ${tx.amount_usd}")
                    continue
                
                # Add to recent transactions
                self.recent_transactions.append(tx)
                wallet.last_activity = tx.timestamp
                
                logger.info(
                    f"New trade from {wallet.nickname}: "
                    f"{tx.action.upper()} ${tx.amount_usd:.2f} {tx.token_symbol}"
                )
                
                # TODO: Trigger copy trading logic here
                # This would call into the strategy engine with the transaction
                
        except Exception as e:
            logger.error(f"Failed to check wallet {wallet.address}: {e}")
    
    async def _fetch_wallet_history(self, wallet: TrackedWallet) -> None:
        """Fetch historical transactions for initial setup."""
        try:
            # Fetch last 10 transactions for baseline
            transactions = await self._fetch_recent_transactions(wallet, limit=10)
            for tx in transactions:
                if tx.timestamp > datetime.now(timezone.utc) - timedelta(hours=24):
                    self.recent_transactions.append(tx)
                    
            logger.info(f"Loaded {len(transactions)} recent transactions for {wallet.nickname}")
            
        except Exception as e:
            logger.error(f"Failed to fetch history for {wallet.address}: {e}")
    
    async def _fetch_recent_transactions(
        self, 
        wallet: TrackedWallet, 
        limit: int = 5
    ) -> List[WalletTransaction]:
        """Fetch recent transactions from blockchain for a wallet."""
        # This is a simplified implementation - in production you'd use:
        # - Etherscan/BSCScan APIs for transaction history
        # - DEX-specific subgraphs (Uniswap, PancakeSwap, etc.)
        # - Or direct RPC calls with event filtering
        
        transactions = []
        
        try:
            # Placeholder implementation - would integrate with actual APIs
            logger.debug(f"Fetching transactions for {wallet.address} on {wallet.chain.value}")
            
            # TODO: Implement actual API calls to:
            # - Etherscan API for Ethereum/Polygon
            # - BSCScan API for BSC  
            # - Basescan API for Base
            # - Parse DEX swap events from transaction logs
            
        except Exception as e:
            logger.error(f"API call failed for {wallet.address}: {e}")
        
        return transactions
    
    def _is_valid_address(self, address: str, chain: ChainType) -> bool:
        """Validate wallet address format for the given chain."""
        if not address:
            return False
            
        # Basic EVM address validation (40 hex chars + 0x prefix)
        if chain in [ChainType.ETHEREUM, ChainType.BSC, ChainType.BASE, 
                    ChainType.POLYGON, ChainType.ARBITRUM]:
            return (
                address.startswith("0x") and 
                len(address) == 42 and
                all(c in "0123456789abcdefABCDEF" for c in address[2:])
            )
        
        return False
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()
        self.running = False