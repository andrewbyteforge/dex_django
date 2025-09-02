# APP: backend
# FILE: dex_django/apps/discovery/wallet_monitor.py
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
        
        # DEX contract addresses for filtering
        self._dex_contracts = {
            "ethereum": {
                "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D": "uniswap_v2",  # Uniswap V2 Router
                "0xE592427A0AEce92De3Edee1F18E0157C05861564": "uniswap_v3",  # Uniswap V3 Router
                "0x1111111254fb6c44bAC0beD2854e76F90643097d": "1inch",      # 1inch Router
                "0xDef1C0ded9bec7F1a1670819833240f027b25EfF": "0x",        # 0x Exchange
            },
            "bsc": {
                "0x10ED43C718714eb63d5aA57B78B54704E256024E": "pancakeswap_v2",
                "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4": "pancakeswap_v3",
            },
            "base": {
                "0x4752ba5DBc23f44D87826276BF6Fd6b1C372aD24": "baseswap",
                "0x327Df1E6de05895d2ab08513aaDD9313Fe505d86": "aerodrome",
            },
            "polygon": {
                "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff": "quickswap",
                "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506": "sushiswap",
            }
        }
    
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
        Fetch transactions from a specific chain using blockchain explorers.
        """
        transactions = []
        
        try:
            if chain == "ethereum":
                transactions = await self._parse_ethereum_transactions(wallet_address, from_block)
            elif chain == "bsc":
                transactions = await self._parse_bsc_transactions(wallet_address, from_block)
            elif chain == "base":
                transactions = await self._parse_base_transactions(wallet_address, from_block)
            elif chain == "polygon":
                transactions = await self._parse_polygon_transactions(wallet_address, from_block)
                
        except Exception as e:
            logger.error("Error fetching %s transactions: %s", chain, e)
            
        return transactions
    
    async def _parse_ethereum_transactions(
        self,
        wallet_address: str,
        from_block: int
    ) -> List[WalletTransaction]:
        """
        Parse Ethereum DEX transactions using Etherscan API and DEX event parsing.
        """
        try:
            # Use Etherscan API to get recent transactions
            url = "https://api.etherscan.io/api"
            params = {
                "module": "account",
                "action": "txlist",
                "address": wallet_address,
                "startblock": from_block,
                "endblock": "latest",
                "sort": "desc",
                "apikey": "YourEtherscanAPIKey"  # Would be from config
            }
            
            async with self._request_semaphore:
                response = await self._http_client.get(url, params=params)
                data = response.json()
            
            if data["status"] != "1":
                logger.warning("Etherscan API error: %s", data.get("message"))
                return []
            
            transactions = []
            
            for tx in data.get("result", [])[:20]:  # Limit to recent 20
                # Only process transactions to known DEX contracts
                if tx["to"] and tx["to"].lower() in self._dex_contracts.get("ethereum", {}):
                    parsed_tx = await self._parse_ethereum_dex_transaction(tx)
                    if parsed_tx:
                        transactions.append(parsed_tx)
            
            return transactions
            
        except Exception as e:
            logger.error("Error parsing Ethereum transactions: %s", e)
            return []
    
    async def _parse_ethereum_dex_transaction(self, tx_data: Dict[str, Any]) -> Optional[WalletTransaction]:
        """Parse individual Ethereum DEX transaction."""
        try:
            dex_name = self._dex_contracts["ethereum"].get(tx_data["to"].lower(), "unknown")
            
            # Mock parsing - in production would decode transaction input and logs
            return WalletTransaction(
                tx_hash=tx_data["hash"],
                block_number=int(tx_data["blockNumber"]),
                timestamp=datetime.fromtimestamp(int(tx_data["timeStamp"]), timezone.utc),
                from_address=tx_data["from"].lower(),
                to_address=tx_data["to"].lower(),
                chain="ethereum",
                dex_name=dex_name,
                token_address="0xa0b86a33e6441e8ce7863a78653c87c8ccb1e86c",  # Mock WETH
                token_symbol="WETH",
                pair_address="0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc",  # Mock pair
                action="buy",
                amount_in=Decimal(tx_data["value"]) / Decimal("10") ** 18,
                amount_out=Decimal("100.0"),  # Mock
                amount_usd=Decimal("1000.0"),  # Mock
                gas_used=int(tx_data["gasUsed"]),
                gas_price_gwei=Decimal(tx_data["gasPrice"]) / Decimal("10") ** 9,
                is_mev=False
            )
        except Exception as e:
            logger.error("Error parsing Ethereum DEX transaction: %s", e)
            return None
    
    async def _parse_bsc_transactions(
        self,
        wallet_address: str,
        from_block: int
    ) -> List[WalletTransaction]:
        """
        Parse BSC DEX transactions using BscScan API.
        """
        try:
            url = "https://api.bscscan.com/api"
            params = {
                "module": "account",
                "action": "txlist",
                "address": wallet_address,
                "startblock": from_block,
                "endblock": "latest",
                "sort": "desc",
                "apikey": "YourBscScanAPIKey"  # Would be from config
            }
            
            async with self._request_semaphore:
                response = await self._http_client.get(url, params=params)
                data = response.json()
            
            if data["status"] != "1":
                return []
            
            transactions = []
            for tx in data.get("result", [])[:20]:
                if tx["to"] and tx["to"].lower() in self._dex_contracts.get("bsc", {}):
                    parsed_tx = await self._parse_bsc_dex_transaction(tx)
                    if parsed_tx:
                        transactions.append(parsed_tx)
            
            return transactions
            
        except Exception as e:
            logger.error("Error parsing BSC transactions: %s", e)
            return []
    
    async def _parse_bsc_dex_transaction(self, tx_data: Dict[str, Any]) -> Optional[WalletTransaction]:
        """Parse individual BSC DEX transaction."""
        try:
            dex_name = self._dex_contracts["bsc"].get(tx_data["to"].lower(), "unknown")
            
            return WalletTransaction(
                tx_hash=tx_data["hash"],
                block_number=int(tx_data["blockNumber"]),
                timestamp=datetime.fromtimestamp(int(tx_data["timeStamp"]), timezone.utc),
                from_address=tx_data["from"].lower(),
                to_address=tx_data["to"].lower(),
                chain="bsc",
                dex_name=dex_name,
                token_address="0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c",  # Mock WBNB
                token_symbol="WBNB",
                pair_address="0x58f876857a02d6762e0101bb5c46a8c1ed44dc16",  # Mock pair
                action="buy",
                amount_in=Decimal(tx_data["value"]) / Decimal("10") ** 18,
                amount_out=Decimal("50.0"),  # Mock
                amount_usd=Decimal("500.0"),  # Mock
                gas_used=int(tx_data["gasUsed"]),
                gas_price_gwei=Decimal(tx_data["gasPrice"]) / Decimal("10") ** 9,
                is_mev=False
            )
        except Exception as e:
            logger.error("Error parsing BSC DEX transaction: %s", e)
            return None
    
    async def _parse_base_transactions(
        self,
        wallet_address: str,
        from_block: int
    ) -> List[WalletTransaction]:
        """
        Parse Base chain DEX transactions using Base explorer.
        """
        # Mock implementation - would integrate with Base explorer API
        return []
    
    async def _parse_polygon_transactions(
        self,
        wallet_address: str,
        from_block: int
    ) -> List[WalletTransaction]:
        """
        Parse Polygon DEX transactions using PolygonScan API.
        """
        # Mock implementation - would integrate with PolygonScan API
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
        if tx.action != "buy":
            return False
        
        # Must have token and pair info
        if not tx.token_address or not tx.pair_address:
            return False
        
        # Skip if token symbol is missing
        if not tx.token_symbol:
            return False
        
        return True
    
    async def _emit_copy_signal(self, tx: WalletTransaction) -> None:
        """
        Emit copy trading signal to the strategy layer.
        This feeds into the copy trading strategy for evaluation.
        """
        try:
            # Import copy trading strategy here to avoid circular imports
            from backend.app.strategy.copy_trading_strategy import copy_trading_strategy
            
            # Get trader config (would be from database in production)
            trader_config = {
                "wallet_address": tx.from_address,
                "copy_percentage": Decimal("5.0"),
                "max_copy_amount_usd": Decimal("1000.0"),
                "enabled": True
            }
            
            # Process the transaction through copy trading strategy
            execution_result = await copy_trading_strategy.process_wallet_transaction(
                tx, trader_config
            )
            
            if execution_result:
                logger.info(
                    "Copy trade executed: %s -> %s (%s)",
                    tx.tx_hash[:10],
                    execution_result.tx_hash or "FAILED",
                    "SUCCESS" if execution_result.success else execution_result.failure_reason
                )
            
        except Exception as e:
            logger.error("Error processing copy signal: %s", e)
        
        # Also emit thought log for UI
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
                "detection_delay_ms": 2000  # Estimated delay
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
        try:
            url = "https://api.etherscan.io/api"
            params = {
                "module": "proxy",
                "action": "eth_blockNumber",
                "apikey": "YourEtherscanAPIKey"
            }
            
            response = await self._http_client.get(url, params=params)
            data = response.json()
            
            if "result" in data:
                return int(data["result"], 16)  # Convert hex to int
                
        except Exception as e:
            logger.error("Error getting latest block number: %s", e)
        
        # Fallback to mock block number
        return 19000000
    
    async def get_monitoring_status(self) -> Dict[str, Any]:
        """
        Get current monitoring status for dashboard.
        """
        return {
            "is_running": self._is_running,
            "followed_wallets": len(self._followed_wallets),
            "active_tasks": len(self._monitoring_tasks),
            "chains_supported": list(self._dex_contracts.keys()),
            "wallets": [
                {
                    "address": wallet,
                    "status": "active" if wallet in self._monitoring_tasks else "inactive",
                    "short_address": f"{wallet[:8]}...{wallet[-4:]}"
                }
                for wallet in self._followed_wallets
            ],
            "total_dex_contracts": sum(len(contracts) for contracts in self._dex_contracts.values())
        }
    
    async def add_wallet(self, wallet_address: str) -> bool:
        """
        Add a single wallet to monitoring.
        """
        try:
            wallet_address = wallet_address.lower()
            
            if wallet_address not in self._followed_wallets:
                self._followed_wallets.add(wallet_address)
                
                if self._is_running:
                    task = asyncio.create_task(
                        self._monitor_wallet_loop(wallet_address),
                        name=f"monitor_{wallet_address[:8]}"
                    )
                    self._monitoring_tasks[wallet_address] = task
                
                logger.info("Added wallet %s to monitoring", wallet_address[:8])
                return True
            
            return False
            
        except Exception as e:
            logger.error("Error adding wallet: %s", e)
            return False
    
    async def remove_wallet(self, wallet_address: str) -> bool:
        """
        Remove a single wallet from monitoring.
        """
        try:
            wallet_address = wallet_address.lower()
            
            if wallet_address in self._followed_wallets:
                await self.stop_monitoring(wallet_address)
                logger.info("Removed wallet %s from monitoring", wallet_address[:8])
                return True
            
            return False
            
        except Exception as e:
            logger.error("Error removing wallet: %s", e)
            return False
    
    async def cleanup(self) -> None:
        """
        Cleanup resources when shutting down.
        """
        await self.stop_monitoring()
        await self._http_client.aclose()


# Global wallet monitor instance
wallet_monitor = WalletMonitor()