from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

import httpx
from pydantic import BaseModel, Field

from backend.app.chains.evm_client import EvmClient
from backend.app.core.runtime_state import runtime_state

logger = logging.getLogger(__name__)


class WalletTransaction(BaseModel):
    """
    Normalized transaction from any chain suitable for copy trading analysis.
    """
    
    tx_hash: str
    block_number: int
    timestamp: datetime
    from_address: str
    to_address: str
    
    # DEX and token details
    chain: str
    dex_name: str
    token_address: str
    token_symbol: Optional[str] = None
    pair_address: Optional[str] = None
    
    # Trade details
    action: str  # 'buy' or 'sell'
    amount_in: Decimal
    amount_out: Decimal
    amount_usd: Decimal
    
    # Context
    gas_used: Optional[int] = None
    gas_price_gwei: Optional[Decimal] = None
    is_mev: bool = False
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }


class WalletMonitor:
    """
    Monitor followed traders' wallet activities across multiple chains.
    Feeds copy trading signals into the strategy layer.
    """
    
    def __init__(self):
        self._http_client = httpx.AsyncClient(timeout=30.0)
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._followed_wallets: Set[str] = set()
        self._is_running = False
        
        # Chain clients (would be injected in production)
        self._evm_clients: Dict[str, EvmClient] = {}
        
        # Rate limiting
        self._request_semaphore = asyncio.Semaphore(10)
    
    async def start_monitoring(self, wallet_addresses: List[str]) -> None:
        """
        Start monitoring a list of wallet addresses across all supported chains.
        """
        logger.info("Starting wallet monitor for %d wallets", len(wallet_addresses))
        
        self._is_running = True
        self._followed_wallets.update(wallet_addresses)
        
        # Start monitoring tasks for each wallet
        for wallet in wallet_addresses:
            if wallet not in self._monitoring_tasks:
                task = asyncio.create_task(
                    self._monitor_wallet_loop(wallet),
                    name=f"monitor_{wallet[:8]}"
                )
                self._monitoring_tasks[wallet] = task
        
        logger.info("Wallet monitor started for %d wallets", len(self._monitoring_tasks))
    
    async def stop_monitoring(self, wallet_address: Optional[str] = None) -> None:
        """
        Stop monitoring specific wallet or all wallets.
        """
        if wallet_address:
            # Stop specific wallet
            if wallet_address in self._monitoring_tasks:
                self._monitoring_tasks[wallet_address].cancel()
                del self._monitoring_tasks[wallet_address]
                self._followed_wallets.discard(wallet_address)
                logger.info("Stopped monitoring wallet %s", wallet_address[:8])
        else:
            # Stop all monitoring
            self._is_running = False
            for task in self._monitoring_tasks.values():
                task.cancel()
            
            # Wait for all tasks to complete
            if self._monitoring_tasks:
                await asyncio.gather(
                    *self._monitoring_tasks.values(),
                    return_exceptions=True
                )
            
            self._monitoring_tasks.clear()
            self._followed_wallets.clear()
            logger.info("Stopped all wallet monitoring")
    
    async def _monitor_wallet_loop(self, wallet_address: str) -> None:
        """
        Continuous monitoring loop for a single wallet.
        """
        logger.info("Starting monitor loop for wallet %s", wallet_address[:8])
        
        last_block = await self._get_latest_block_number()
        
        while self._is_running and wallet_address in self._followed_wallets:
            try:
                # Check for new transactions
                new_txs = await self._fetch_recent_transactions(
                    wallet_address,
                    from_block=last_block
                )
                
                if new_txs:
                    logger.info(
                        "Found %d new transactions for wallet %s",
                        len(new_txs),
                        wallet_address[:8]
                    )
                    
                    # Process each transaction
                    for tx in new_txs:
                        if await self._is_copyable_transaction(tx):
                            await self._emit_copy_signal(tx)
                    
                    # Update last processed block
                    if new_txs:
                        last_block = max(tx.block_number for tx in new_txs)
                
                # Wait before next check
                await asyncio.sleep(15.0)  # Check every 15 seconds
                
            except Exception as e:
                logger.error(
                    "Error monitoring wallet %s: %s",
                    wallet_address[:8],
                    e
                )
                await asyncio.sleep(60.0)  # Wait longer on error
    
    async def _fetch_recent_transactions(
        self,
        wallet_address: str,
        from_block: int,
        chains: Optional[List[str]] = None
    ) -> List[WalletTransaction]:
        """
        Fetch recent transactions for a wallet across specified chains.
        """
        if not chains:
            chains = ["ethereum", "bsc", "base", "polygon"]
        
        all_transactions = []
        
        # Fetch from each chain in parallel
        tasks = [
            self._fetch_chain_transactions(wallet_address, chain, from_block)
            for chain in chains
        ]
        
        async with self._request_semaphore:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for chain, result in zip(chains, results):
            if isinstance(result, Exception):
                logger.warning(
                    "Failed to fetch %s transactions for %s: %s",
                    chain,
                    wallet_address[:8],
                    result
                )
            else:
                all_transactions.extend(result)
        
        # Sort by block number and timestamp
        all_transactions.sort(key=lambda tx: (tx.block_number, tx.timestamp))
        
        return all_transactions
    
    async def _fetch_chain_transactions(
        self,
        wallet_address: str,
        chain: str,
        from_block: int
    ) -> List[WalletTransaction]:
        """
        Fetch transactions from a specific chain.
        In production, this would use the actual chain clients and DEX event parsers.
        """
        # Mock implementation - would integrate with actual chain clients
        transactions = []
        
        if chain == "ethereum":
            # Would use Etherscan API or direct RPC calls
            transactions.extend(
                await self._parse_ethereum_transactions(wallet_address, from_block)
            )
        elif chain == "bsc":
            # Would use BscScan API
            transactions.extend(
                await self._parse_bsc_transactions(wallet_address, from_block)
            )
        elif chain == "base":
            # Would use Base RPC/explorer
            transactions.extend(
                await self._parse_base_transactions(wallet_address, from_block)
            )
        elif chain == "polygon":
            # Would use PolygonScan API
            transactions.extend(
                await self._parse_polygon_transactions(wallet_address, from_block)
            )
        
        return transactions
    
    async def _parse_ethereum_transactions(
        self,
        wallet_address: str,
        from_block: int
    ) -> List[WalletTransaction]:
        """
        Parse Ethereum DEX transactions using actual DEX event parsing.
        """
        # Mock implementation - would parse actual Uniswap/1inch logs
        return []
    
    async def _parse_bsc_transactions(
        self,
        wallet_address: str,
        from_block: int
    ) -> List[WalletTransaction]:
        """
        Parse BSC DEX transactions (PancakeSwap, etc.).
        """
        # Mock implementation - would parse actual PancakeSwap logs
        return []
    
    async def _parse_base_transactions(
        self,
        wallet_address: str,
        from_block: int
    ) -> List[WalletTransaction]:
        """
        Parse Base chain DEX transactions.
        """
        # Mock implementation - would parse Base DEX logs
        return []
    
    async def _parse_polygon_transactions(
        self,
        wallet_address: str,
        from_block: int
    ) -> List[WalletTransaction]:
        """
        Parse Polygon DEX transactions (QuickSwap, etc.).
        """
        # Mock implementation - would parse Polygon DEX logs
        return []
    
    async def _is_copyable_transaction(self, tx: WalletTransaction) -> bool:
        """
        Determine if a transaction is suitable for copy trading.
        Applies basic filters before sending to strategy layer.
        """
        # Skip very small trades
        if tx.amount_usd < Decimal("50.0"):
            return False
        
        # Skip very large trades (might be whale/institutional)
        if tx.amount_usd > Decimal("100000.0"):
            return False
        
        # Skip MEV transactions
        if tx.is_mev:
            return False
        
        # Only copy buy transactions initially
        # (sell logic would be more complex)
        if tx.action != "buy":
            return False
        
        # Must have token and pair info
        if not tx.token_address or not tx.pair_address:
            return False
        
        return True
    
    async def _emit_copy_signal(self, tx: WalletTransaction) -> None:
        """
        Emit copy trading signal to the strategy layer.
        This feeds into the same risk gates as autotrade signals.
        """
        signal_data = {
            "type": "copy_signal",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "wallet_monitor",
            "trader_address": tx.from_address,
            "original_tx": tx.dict(),
            "signal": {
                "chain": tx.chain,
                "dex_name": tx.dex_name,
                "token_address": tx.token_address,
                "token_symbol": tx.token_symbol,
                "pair_address": tx.pair_address,
                "action": tx.action,
                "original_amount_usd": float(tx.amount_usd),
                "urgency": "high",  # Copy trades need speed
            }
        }
        
        # Would send this to the strategy layer via message queue or direct call
        # For now, emit to runtime state for WebSocket broadcasting
        await runtime_state.emit_thought_log({
            "opportunity": {
                "pair": tx.pair_address,
                "symbol": f"{tx.token_symbol}/WETH",
                "chain": tx.chain,
                "dex": tx.dex_name
            },
            "discovery_signals": {
                "source": "copy_trading",
                "trader": f"{tx.from_address[:8]}...",
                "original_amount_usd": float(tx.amount_usd),
                "detection_delay_ms": 2000  # Mock delay
            },
            "decision": {
                "action": "evaluate_for_copy",
                "rationale": f"Copying {tx.token_symbol} buy from followed trader",
                "original_tx_hash": tx.tx_hash
            }
        })
        
        logger.info(
            "Emitted copy signal for %s: %s %s on %s",
            tx.from_address[:8],
            tx.action.upper(),
            tx.token_symbol,
            tx.chain
        )
    
    async def _get_latest_block_number(self) -> int:
        """
        Get latest block number from primary chain (Ethereum).
        """
        # Mock implementation - would use actual chain client
        return 19000000
    
    async def get_monitoring_status(self) -> Dict[str, Any]:
        """
        Get current monitoring status for dashboard.
        """
        return {
            "is_running": self._is_running,
            "followed_wallets": len(self._followed_wallets),
            "active_tasks": len(self._monitoring_tasks),
            "wallets": [
                {
                    "address": wallet,
                    "status": "active" if wallet in self._monitoring_tasks else "inactive",
                    "short_address": f"{wallet[:8]}...{wallet[-4:]}"
                }
                for wallet in self._followed_wallets
            ]
        }
    
    async def cleanup(self) -> None:
        """
        Cleanup resources when shutting down.
        """
        await self.stop_monitoring()
        await self._http_client.aclose()


# Global wallet monitor instance
wallet_monitor = WalletMonitor()