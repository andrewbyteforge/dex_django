from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime

import httpx
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("wallet")

@dataclass
class WalletBalance:
    """Wallet balance information."""
    chain: str
    address: str
    native_balance: Decimal
    native_symbol: str
    token_balances: Dict[str, Decimal]
    last_updated: str

@dataclass
class TransactionRequest:
    """Transaction request for manual approval."""
    transaction_id: str
    chain: str
    from_address: str
    to_address: str
    value: str
    data: str
    gas_limit: int
    gas_price: str
    estimated_cost: Decimal
    trade_summary: Dict[str, Any]

class WalletService:
    """Service for wallet operations across chains."""
    
    def __init__(self):
        self.rpc_endpoints = {
            "ethereum": "https://eth.llamarpc.com",
            "base": "https://mainnet.base.org",
            "polygon": "https://polygon.llamarpc.com", 
            "bsc": "https://bsc-dataseed.binance.org",
            "solana": "https://api.mainnet-beta.solana.com"
        }
        
        # Major token contracts per chain
        self.token_contracts = {
            "ethereum": {
                "USDC": "0xa0b86a33e6b84e7e1d29c2e3dd19e93bb9a1e6e4",
                "USDT": "0xdac17f958d2ee523a2206206994597c13d831ec7",
                "WETH": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                "DAI": "0x6b175474e89094c44da98b954eedeac495271d0f"
            },
            "base": {
                "USDC": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
                "WETH": "0x4200000000000000000000000000000000000006"
            },
            "polygon": {
                "USDC": "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",
                "USDT": "0xc2132d05d31c914a87c6611c10748aeb04b58e8f",
                "WETH": "0x7ceb23fd6f8a0e6e1bb73b1e9986c26dbb8f84e4",
                "WMATIC": "0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270"
            },
            "bsc": {
                "USDC": "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
                "USDT": "0x55d398326f99059ff775485246999027b3197955",
                "WBNB": "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c",
                "BUSD": "0xe9e7cea3dedca5984780bafc599bd69add087d56"
            },
            "solana": {
                "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
            }
        }
    
    async def get_wallet_balances(
        self, 
        chain: str, 
        address: str
    ) -> WalletBalance:
        """Get comprehensive wallet balance for a specific chain."""
        trace_id = f"balance_{chain}_{address[:8]}"
        logger.info(f"[{trace_id}] Fetching balances for {chain}")
        
        try:
            if chain == "solana":
                return await self._get_solana_balances(address, trace_id)
            else:
                return await self._get_evm_balances(chain, address, trace_id)
                
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to fetch balances: {e}")
            # Return empty balance on error
            return WalletBalance(
                chain=chain,
                address=address,
                native_balance=Decimal("0"),
                native_symbol=self._get_native_symbol(chain),
                token_balances={},
                last_updated=timezone.now().isoformat()
            )
    
    async def _get_evm_balances(
        self, 
        chain: str, 
        address: str, 
        trace_id: str
    ) -> WalletBalance:
        """Get EVM chain balances using RPC calls."""
        
        rpc_url = self.rpc_endpoints.get(chain)
        if not rpc_url:
            raise ValueError(f"Unsupported chain: {chain}")
        
        native_balance = Decimal("0")
        token_balances = {}
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Get native balance
                native_payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_getBalance",
                    "params": [address, "latest"],
                    "id": 1
                }
                
                logger.debug(f"[{trace_id}] Fetching native balance from {rpc_url}")
                response = await client.post(rpc_url, json=native_payload)
                
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        # Convert wei to ether
                        wei_balance = int(data["result"], 16)
                        native_balance = Decimal(wei_balance) / Decimal(10**18)
                        logger.debug(f"[{trace_id}] Native balance: {native_balance}")
                
                # Get token balances
                token_contracts = self.token_contracts.get(chain, {})
                
                for token_symbol, contract_address in token_contracts.items():
                    try:
                        # ERC20 balanceOf call
                        balance_data = f"0x70a08231000000000000000000000000{address[2:].lower()}"
                        
                        token_payload = {
                            "jsonrpc": "2.0",
                            "method": "eth_call",
                            "params": [{
                                "to": contract_address,
                                "data": balance_data
                            }, "latest"],
                            "id": 2
                        }
                        
                        token_response = await client.post(rpc_url, json=token_payload)
                        
                        if token_response.status_code == 200:
                            token_data = token_response.json()
                            if "result" in token_data and token_data["result"] != "0x":
                                # Most tokens use 18 decimals, but USDC/USDT use 6
                                decimals = 6 if token_symbol in ["USDC", "USDT"] else 18
                                raw_balance = int(token_data["result"], 16)
                                token_balance = Decimal(raw_balance) / Decimal(10**decimals)
                                
                                if token_balance > 0:
                                    token_balances[token_symbol] = token_balance
                                    logger.debug(f"[{trace_id}] {token_symbol} balance: {token_balance}")
                                    
                    except Exception as e:
                        logger.debug(f"[{trace_id}] Failed to fetch {token_symbol} balance: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"[{trace_id}] RPC request failed: {e}")
            raise
        
        return WalletBalance(
            chain=chain,
            address=address,
            native_balance=native_balance,
            native_symbol=self._get_native_symbol(chain),
            token_balances=token_balances,
            last_updated=timezone.now().isoformat()
        )
    
    async def _get_solana_balances(
        self, 
        address: str, 
        trace_id: str
    ) -> WalletBalance:
        """Get Solana balances using RPC calls."""
        
        rpc_url = self.rpc_endpoints["solana"]
        native_balance = Decimal("0")
        token_balances = {}
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Get SOL balance
                sol_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getBalance",
                    "params": [address]
                }
                
                logger.debug(f"[{trace_id}] Fetching SOL balance")
                response = await client.post(rpc_url, json=sol_payload)
                
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        # Convert lamports to SOL
                        lamports = data["result"]["value"]
                        native_balance = Decimal(lamports) / Decimal(10**9)
                        logger.debug(f"[{trace_id}] SOL balance: {native_balance}")
                
                # Get SPL token accounts
                token_payload = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "getTokenAccountsByOwner",
                    "params": [
                        address,
                        {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                        {"encoding": "jsonParsed"}
                    ]
                }
                
                token_response = await client.post(rpc_url, json=token_payload)
                
                if token_response.status_code == 200:
                    token_data = token_response.json()
                    if "result" in token_data:
                        token_accounts = token_data["result"]["value"]
                        
                        for account in token_accounts:
                            try:
                                parsed_info = account["account"]["data"]["parsed"]["info"]
                                mint = parsed_info["mint"]
                                amount = Decimal(parsed_info["tokenAmount"]["amount"])
                                decimals = parsed_info["tokenAmount"]["decimals"]
                                
                                # Convert to human readable amount
                                token_amount = amount / Decimal(10**decimals)
                                
                                if token_amount > 0:
                                    # Map known token mints to symbols
                                    token_symbol = self._get_solana_token_symbol(mint)
                                    if token_symbol:
                                        token_balances[token_symbol] = token_amount
                                        logger.debug(f"[{trace_id}] {token_symbol} balance: {token_amount}")
                                        
                            except Exception as e:
                                logger.debug(f"[{trace_id}] Failed to parse token account: {e}")
                                continue
                                
        except Exception as e:
            logger.error(f"[{trace_id}] Solana RPC request failed: {e}")
            raise
        
        return WalletBalance(
            chain="solana",
            address=address,
            native_balance=native_balance,
            native_symbol="SOL",
            token_balances=token_balances,
            last_updated=timezone.now().isoformat()
        )
    
    async def prepare_swap_transaction(
        self,
        chain: str,
        from_address: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_bps: int = 300
    ) -> TransactionRequest:
        """Prepare a swap transaction for manual wallet approval."""
        trace_id = f"prep_tx_{chain}_{int(datetime.now().timestamp())}"
        
        logger.info(
            f"[{trace_id}] Preparing swap: {amount_in} {token_in} → {token_out} "
            f"on {chain} for {from_address[:8]}..."
        )
        
        try:
            # This would integrate with your DEX routing logic
            # For now, return a mock transaction
            mock_transaction = TransactionRequest(
                transaction_id=trace_id,
                chain=chain,
                from_address=from_address,
                to_address=self._get_router_address(chain),
                value="0" if token_in != self._get_native_symbol(chain) else str(amount_in),
                data="0x" + "00" * 100,  # Mock calldata
                gas_limit=150000,
                gas_price=await self._estimate_gas_price(chain),
                estimated_cost=Decimal("0.02"),  # Mock gas cost
                trade_summary={
                    "token_in": token_in,
                    "token_out": token_out,
                    "amount_in": str(amount_in),
                    "estimated_amount_out": str(amount_in * Decimal("0.99")),  # Mock 1% slippage
                    "slippage_bps": slippage_bps,
                    "route": f"{token_in} → {token_out}",
                    "dex": "uniswap_v3"
                }
            )
            
            logger.info(f"[{trace_id}] Transaction prepared successfully")
            return mock_transaction
            
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to prepare transaction: {e}")
            raise
    
    def _get_native_symbol(self, chain: str) -> str:
        """Get native token symbol for chain."""
        symbols = {
            "ethereum": "ETH",
            "base": "ETH", 
            "polygon": "MATIC",
            "bsc": "BNB",
            "solana": "SOL"
        }
        return symbols.get(chain, "ETH")
    
    def _get_router_address(self, chain: str) -> str:
        """Get DEX router address for chain."""
        routers = {
            "ethereum": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",  # Uniswap V3
            "base": "0x2626664c2603336E57B271c5C0b26F421741e481",      # Uniswap V3
            "polygon": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",   # Uniswap V3
            "bsc": "0x10ED43C718714eb63d5aA57B78B54704E256024E",       # PancakeSwap V2
            "solana": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"     # Jupiter
        }
        return routers.get(chain, "0x0000000000000000000000000000000000000000")
    
    async def _estimate_gas_price(self, chain: str) -> str:
        """Estimate current gas price for chain."""
        try:
            rpc_url = self.rpc_endpoints.get(chain)
            if not rpc_url or chain == "solana":
                return "20000000000"  # 20 gwei default
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_gasPrice",
                    "params": [],
                    "id": 1
                }
                
                response = await client.post(rpc_url, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        return data["result"]
                        
        except Exception as e:
            logger.debug(f"Failed to estimate gas price for {chain}: {e}")
        
        return "20000000000"  # 20 gwei fallback
    
    def _get_solana_token_symbol(self, mint: str) -> Optional[str]:
        """Map Solana token mint to symbol."""
        mint_to_symbol = {
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
            "So11111111111111111111111111111111111111112": "WSOL"
        }
        return mint_to_symbol.get(mint)


# Global wallet service instance
wallet_service = WalletService()