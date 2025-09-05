# APP: dex_django/apps/chains
# FILE: evm_client.py
"""
EVM Client for DEX Sniper Pro

Provides async blockchain interactions for Ethereum-compatible chains (Ethereum, BSC, Base, Polygon).
Handles RPC connections, transaction building, gas estimation, and contract interactions.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from eth_account import Account
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.types import TxParams, Wei

logger = logging.getLogger(__name__)


@dataclass
class ChainConfig:
    """Configuration for an EVM-compatible chain."""
    name: str
    chain_id: int
    rpc_urls: List[str]
    native_token: str
    block_time: float
    gas_price_multiplier: float = 1.2
    max_priority_fee_gwei: int = 2
    

@dataclass
class GasSnapshot:
    """Current gas pricing information."""
    base_fee_gwei: Decimal
    priority_fee_gwei: Decimal
    gas_price_gwei: Decimal
    timestamp: datetime
    block_number: int
    

@dataclass
class TransactionResult:
    """Result of a blockchain transaction."""
    tx_hash: str
    block_number: Optional[int] = None
    gas_used: Optional[int] = None
    gas_price_gwei: Optional[Decimal] = None
    status: str = "pending"  # pending, confirmed, failed
    error_message: Optional[str] = None


class EvmClient:
    """
    Async EVM client for multi-chain blockchain interactions.
    
    Supports Ethereum, BSC, Base, Polygon, and other EVM chains.
    Provides robust RPC connection management with failover.
    """
    
    # Predefined chain configurations
    CHAIN_CONFIGS = {
        "ethereum": ChainConfig(
            name="ethereum",
            chain_id=1,
            rpc_urls=[
                "https://eth.llamarpc.com",
                "https://ethereum.publicnode.com",
                "https://eth.drpc.org"
            ],
            native_token="ETH",
            block_time=12.0,
            max_priority_fee_gwei=2
        ),
        "bsc": ChainConfig(
            name="bsc", 
            chain_id=56,
            rpc_urls=[
                "https://bsc-dataseed1.binance.org",
                "https://bsc.publicnode.com",
                "https://bsc.drpc.org"
            ],
            native_token="BNB",
            block_time=3.0,
            max_priority_fee_gwei=1
        ),
        "base": ChainConfig(
            name="base",
            chain_id=8453,
            rpc_urls=[
                "https://mainnet.base.org",
                "https://base.publicnode.com",
                "https://base.drpc.org"
            ],
            native_token="ETH",
            block_time=2.0,
            max_priority_fee_gwei=1
        ),
        "polygon": ChainConfig(
            name="polygon",
            chain_id=137,
            rpc_urls=[
                "https://polygon.llamarpc.com",
                "https://polygon.publicnode.com", 
                "https://polygon.drpc.org"
            ],
            native_token="MATIC",
            block_time=2.0,
            max_priority_fee_gwei=30
        )
    }
    
    def __init__(self, chain: str, private_key: Optional[str] = None):
        """
        Initialize EVM client for specified chain.
        
        Args:
            chain: Chain name (ethereum, bsc, base, polygon)
            private_key: Optional private key for signing transactions
        """
        if chain not in self.CHAIN_CONFIGS:
            raise ValueError(f"Unsupported chain: {chain}. Must be one of: {list(self.CHAIN_CONFIGS.keys())}")
        
        self.chain = chain
        self.config = self.CHAIN_CONFIGS[chain]
        self.private_key = private_key
        self.account = Account.from_key(private_key) if private_key else None
        
        # HTTP client for RPC calls
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=10)
        )
        
        # RPC endpoint management
        self.current_rpc_index = 0
        self.failed_rpcs = set()
        
        logger.info(f"Initialized EVM client for {chain} (chain_id: {self.config.chain_id})")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()
    
    @property
    def current_rpc_url(self) -> str:
        """Get current RPC URL with failover logic."""
        available_rpcs = [
            (i, url) for i, url in enumerate(self.config.rpc_urls) 
            if i not in self.failed_rpcs
        ]
        
        if not available_rpcs:
            # Reset failed RPCs if all have failed
            self.failed_rpcs.clear()
            available_rpcs = list(enumerate(self.config.rpc_urls))
        
        if self.current_rpc_index >= len(available_rpcs):
            self.current_rpc_index = 0
        
        return available_rpcs[self.current_rpc_index][1]
    
    async def _rpc_call(self, method: str, params: List[Any] = None) -> Any:
        """
        Make an RPC call with automatic failover.
        
        Args:
            method: RPC method name
            params: Method parameters
            
        Returns:
            RPC response result
        """
        if params is None:
            params = []
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        
        max_retries = len(self.config.rpc_urls)
        
        for attempt in range(max_retries):
            rpc_url = self.current_rpc_url
            
            try:
                response = await self.http_client.post(rpc_url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                
                if "error" in data:
                    raise Exception(f"RPC error: {data['error']}")
                
                return data.get("result")
                
            except Exception as e:
                logger.warning(f"RPC call failed for {rpc_url}: {e}")
                self.failed_rpcs.add(self.current_rpc_index)
                self.current_rpc_index = (self.current_rpc_index + 1) % len(self.config.rpc_urls)
                
                if attempt == max_retries - 1:
                    raise Exception(f"All RPC endpoints failed for {method}")
    
    async def get_block_number(self) -> int:
        """Get current block number."""
        result = await self._rpc_call("eth_blockNumber")
        return int(result, 16)
    
    async def get_balance(self, address: str) -> Decimal:
        """
        Get native token balance for address.
        
        Args:
            address: Wallet address to check
            
        Returns:
            Balance in native tokens (ETH, BNB, etc.)
        """
        result = await self._rpc_call("eth_getBalance", [address, "latest"])
        wei_balance = int(result, 16)
        return Decimal(wei_balance) / Decimal(10**18)
    
    async def get_transaction_count(self, address: str) -> int:
        """Get nonce for address."""
        result = await self._rpc_call("eth_getTransactionCount", [address, "pending"])
        return int(result, 16)
    
    async def get_gas_snapshot(self) -> GasSnapshot:
        """
        Get current gas pricing information.
        
        Returns:
            GasSnapshot with current gas prices
        """
        try:
            # Get base fee from latest block
            latest_block = await self._rpc_call("eth_getBlockByNumber", ["latest", False])
            base_fee_hex = latest_block.get("baseFeePerGas", "0x0")
            base_fee_wei = int(base_fee_hex, 16)
            base_fee_gwei = Decimal(base_fee_wei) / Decimal(10**9)
            
            # Get suggested gas price
            gas_price_hex = await self._rpc_call("eth_gasPrice")
            gas_price_wei = int(gas_price_hex, 16)
            gas_price_gwei = Decimal(gas_price_wei) / Decimal(10**9)
            
            # Priority fee is gas price minus base fee, with a minimum
            priority_fee_gwei = max(
                gas_price_gwei - base_fee_gwei,
                Decimal(self.config.max_priority_fee_gwei)
            )
            
            return GasSnapshot(
                base_fee_gwei=base_fee_gwei,
                priority_fee_gwei=priority_fee_gwei,
                gas_price_gwei=gas_price_gwei,
                timestamp=datetime.now(timezone.utc),
                block_number=int(latest_block["number"], 16)
            )
            
        except Exception as e:
            logger.error(f"Failed to get gas snapshot: {e}")
            # Return fallback values
            return GasSnapshot(
                base_fee_gwei=Decimal("20"),
                priority_fee_gwei=Decimal(self.config.max_priority_fee_gwei),
                gas_price_gwei=Decimal("25"),
                timestamp=datetime.now(timezone.utc),
                block_number=0
            )
    
    async def estimate_gas(
        self, 
        to_address: str, 
        data: str = "0x", 
        value: int = 0,
        from_address: Optional[str] = None
    ) -> int:
        """
        Estimate gas required for a transaction.
        
        Args:
            to_address: Contract or recipient address
            data: Transaction data
            value: ETH value to send (in wei)
            from_address: Sender address
            
        Returns:
            Estimated gas limit
        """
        if from_address is None and self.account:
            from_address = self.account.address
        
        params = {
            "to": to_address,
            "data": data,
            "value": hex(value),
        }
        
        if from_address:
            params["from"] = from_address
        
        try:
            result = await self._rpc_call("eth_estimateGas", [params])
            estimated_gas = int(result, 16)
            
            # Add 20% buffer for safety
            return int(estimated_gas * 1.2)
            
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}")
            # Return conservative fallback
            return 200000
    
    async def call_contract(
        self, 
        contract_address: str, 
        data: str,
        block: str = "latest"
    ) -> str:
        """
        Make a read-only contract call.
        
        Args:
            contract_address: Contract address
            data: Encoded function call data
            block: Block number or "latest"
            
        Returns:
            Contract call result
        """
        params = {
            "to": contract_address,
            "data": data
        }
        
        result = await self._rpc_call("eth_call", [params, block])
        return result
    
    async def send_raw_transaction(self, signed_tx_hex: str) -> str:
        """
        Broadcast a signed transaction.
        
        Args:
            signed_tx_hex: Hex-encoded signed transaction
            
        Returns:
            Transaction hash
        """
        result = await self._rpc_call("eth_sendRawTransaction", [signed_tx_hex])
        return result
    
    async def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get transaction receipt.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            Transaction receipt or None if not found
        """
        try:
            result = await self._rpc_call("eth_getTransactionReceipt", [tx_hash])
            return result
        except:
            return None
    
    async def wait_for_transaction(
        self, 
        tx_hash: str, 
        timeout: int = 300,
        poll_interval: float = 2.0
    ) -> TransactionResult:
        """
        Wait for transaction confirmation.
        
        Args:
            tx_hash: Transaction hash to wait for
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds
            
        Returns:
            TransactionResult with final status
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                return TransactionResult(
                    tx_hash=tx_hash,
                    status="timeout",
                    error_message=f"Transaction not confirmed within {timeout}s"
                )
            
            # Get receipt
            receipt = await self.get_transaction_receipt(tx_hash)
            
            if receipt:
                status = "confirmed" if receipt.get("status") == "0x1" else "failed"
                
                return TransactionResult(
                    tx_hash=tx_hash,
                    block_number=int(receipt["blockNumber"], 16),
                    gas_used=int(receipt["gasUsed"], 16),
                    status=status,
                    error_message=None if status == "confirmed" else "Transaction reverted"
                )
            
            # Wait before next poll
            await asyncio.sleep(poll_interval)
    
    def build_transaction(
        self,
        to_address: str,
        value: int = 0,
        data: str = "0x",
        gas_limit: Optional[int] = None,
        gas_price_gwei: Optional[Decimal] = None,
        nonce: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Build transaction parameters.
        
        Args:
            to_address: Recipient address
            value: ETH value in wei
            data: Transaction data
            gas_limit: Gas limit
            gas_price_gwei: Gas price in gwei
            nonce: Transaction nonce
            
        Returns:
            Transaction parameters dict
        """
        tx_params = {
            "chainId": self.config.chain_id,
            "to": Web3.to_checksum_address(to_address),
            "value": value,
            "data": data,
        }
        
        if gas_limit:
            tx_params["gas"] = gas_limit
        
        if gas_price_gwei:
            tx_params["gasPrice"] = int(gas_price_gwei * 10**9)
        
        if nonce is not None:
            tx_params["nonce"] = nonce
        
        return tx_params


# Factory function for easy client creation
async def create_evm_client(chain: str, private_key: Optional[str] = None) -> EvmClient:
    """
    Factory function to create an EVM client.
    
    Args:
        chain: Chain name (ethereum, bsc, base, polygon)
        private_key: Optional private key for signing
        
    Returns:
        Initialized EvmClient
    """
    client = EvmClient(chain, private_key)
    return client


# Utility functions
def wei_to_ether(wei: int) -> Decimal:
    """Convert wei to ether."""
    return Decimal(wei) / Decimal(10**18)


def ether_to_wei(ether: Union[Decimal, float, str]) -> int:
    """Convert ether to wei."""
    return int(Decimal(ether) * Decimal(10**18))


def gwei_to_wei(gwei: Union[Decimal, float, str]) -> int:
    """Convert gwei to wei."""
    return int(Decimal(gwei) * Decimal(10**9))


def wei_to_gwei(wei: int) -> Decimal:
    """Convert wei to gwei."""
    return Decimal(wei) / Decimal(10**9)