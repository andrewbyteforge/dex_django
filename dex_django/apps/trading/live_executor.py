# APP: backend
# FILE: backend/app/trading/live_executor.py
from __future__ import annotations

import asyncio
import logging
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, List

import httpx
from web3 import AsyncWeb3
from web3.exceptions import ContractLogicError, TransactionNotFound
from eth_account import Account
from eth_account.signers.local import LocalAccount

from dex_django.dex.uniswap_v2 import UniswapV2Adapter
from dex_django.dex.uniswap_v3 import UniswapV3Adapter
from dex_django.chains.evm_client import EvmClient
from dex_django.core.runtime_state import runtime_state

logger = logging.getLogger("trading.live_executor")


class LiveExecutionEngine:
    """
    Live blockchain execution engine that performs actual on-chain trades.
    Handles DEX routing, transaction signing, gas management, and settlement.
    """
    
    def __init__(self):
        self._http_client = httpx.AsyncClient(timeout=30.0)
        self._evm_clients: Dict[str, EvmClient] = {}
        self._dex_adapters: Dict[str, Any] = {}
        self._account: Optional[LocalAccount] = None
        self._initialized = False
        
        # Gas strategy settings
        self._gas_multiplier = Decimal("1.2")  # 20% buffer
        self._max_gas_price_gwei = Decimal("100.0")
        
        # Execution settings
        self._max_retries = 3
        self._confirmation_blocks = 1
        self._timeout_seconds = 180
        
    async def initialize(self, private_key: Optional[str] = None) -> bool:
        """
        Initialize the live execution engine with wallet and chain connections.
        """
        try:
            logger.info("Initializing live execution engine...")
            
            # Initialize account if private key provided
            if private_key:
                self._account = Account.from_key(private_key)
                logger.info(f"Wallet loaded: {self._account.address}")
            else:
                logger.warning("No private key provided - live trading disabled")
            
            # Initialize chain clients
            await self._initialize_chain_clients()
            
            # Initialize DEX adapters
            await self._initialize_dex_adapters()
            
            self._initialized = True
            logger.info("Live execution engine initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize live execution engine: {e}")
            return False
    
    async def execute_trade(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        chain: str,
        dex: str,
        slippage_bps: int,
        recipient: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a live trade on the blockchain.
        """
        if not self._initialized:
            return {"success": False, "error": "Engine not initialized"}
        
        if not self._account:
            return {"success": False, "error": "No wallet configured"}
        
        trace_id = f"live_{int(datetime.now().timestamp())}"
        logger.info(f"[{trace_id}] Executing live trade: {amount_in} {token_in} -> {token_out} on {chain}")
        
        try:
            start_time = datetime.now()
            
            # Step 1: Get optimal route and quote
            route_result = await self._get_best_route(
                token_in, token_out, amount_in, chain, slippage_bps
            )
            
            if not route_result["success"]:
                return route_result
            
            route = route_result["route"]
            expected_out = route_result["amount_out"]
            
            # Step 2: Check and handle token approvals
            approval_result = await self._handle_approvals(
                token_in, amount_in, route["router"], chain
            )
            
            if not approval_result["success"]:
                return approval_result
            
            # Step 3: Build and sign transaction
            tx_result = await self._build_and_sign_transaction(
                route, amount_in, expected_out, slippage_bps, chain, recipient
            )
            
            if not tx_result["success"]:
                return tx_result
            
            signed_tx = tx_result["signed_tx"]
            
            # Step 4: Submit transaction to blockchain
            submit_result = await self._submit_transaction(signed_tx, chain)
            
            if not submit_result["success"]:
                return submit_result
            
            tx_hash = submit_result["tx_hash"]
            
            # Step 5: Wait for confirmation
            confirm_result = await self._wait_for_confirmation(tx_hash, chain)
            
            if not confirm_result["success"]:
                return confirm_result
            
            receipt = confirm_result["receipt"]
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Step 6: Parse results
            actual_out = await self._parse_swap_result(receipt, token_out)
            actual_slippage = self._calculate_slippage(expected_out, actual_out)
            
            result = {
                "success": True,
                "tx_hash": tx_hash,
                "amount_out": actual_out,
                "expected_out": expected_out,
                "gas_used": receipt["gasUsed"],
                "gas_price_gwei": float(receipt["effectiveGasPrice"]) / 1e9,
                "effective_slippage_bps": actual_slippage,
                "execution_time_ms": execution_time,
                "block_number": receipt["blockNumber"],
                "trace_id": trace_id
            }
            
            logger.info(f"[{trace_id}] Trade executed successfully: {tx_hash}")
            
            # Emit to thought log
            await runtime_state.emit_thought_log({
                "event": "live_trade_executed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trade": {
                    "tx_hash": tx_hash,
                    "chain": chain,
                    "dex": route["dex"],
                    "token_in": token_in,
                    "token_out": token_out,
                    "amount_in": float(amount_in),
                    "amount_out": float(actual_out),
                    "slippage_bps": actual_slippage,
                    "gas_used": receipt["gasUsed"],
                    "execution_time_ms": execution_time
                },
                "trace_id": trace_id
            })
            
            return result
            
        except Exception as e:
            logger.error(f"[{trace_id}] Live trade execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "trace_id": trace_id
            }
    
    async def _get_best_route(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        chain: str,
        slippage_bps: int
    ) -> Dict[str, Any]:
        """
        Find the best route across available DEXs.
        """
        try:
            best_route = None
            best_amount_out = Decimal("0")
            
            # Check available DEXs for this chain
            available_dexs = self._get_available_dexs(chain)
            
            for dex_name in available_dexs:
                try:
                    adapter = self._dex_adapters[f"{chain}_{dex_name}"]
                    
                    quote = await adapter.get_quote(
                        token_in=token_in,
                        token_out=token_out,
                        amount_in=amount_in,
                        slippage_bps=slippage_bps
                    )
                    
                    if quote["success"] and quote["amount_out"] > best_amount_out:
                        best_amount_out = quote["amount_out"]
                        best_route = {
                            "dex": dex_name,
                            "router": quote["router_address"],
                            "path": quote["path"],
                            "amount_out": quote["amount_out"],
                            "price_impact": quote.get("price_impact", 0)
                        }
                        
                except Exception as e:
                    logger.warning(f"Failed to get quote from {dex_name}: {e}")
                    continue
            
            if not best_route:
                return {"success": False, "error": "No valid routes found"}
            
            return {
                "success": True,
                "route": best_route,
                "amount_out": best_amount_out
            }
            
        except Exception as e:
            logger.error(f"Route finding failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_approvals(
        self,
        token_address: str,
        amount: Decimal,
        router_address: str,
        chain: str
    ) -> Dict[str, Any]:
        """
        Check and handle token approvals for DEX router.
        """
        try:
            # Skip approval for native tokens (ETH, BNB, etc.)
            if self._is_native_token(token_address, chain):
                return {"success": True}
            
            client = self._evm_clients[chain]
            
            # Check current allowance
            allowance = await client.get_token_allowance(
                token_address, self._account.address, router_address
            )
            
            # If allowance is sufficient, no approval needed
            if allowance >= amount:
                logger.info(f"Sufficient allowance: {allowance} >= {amount}")
                return {"success": True}
            
            # Need to approve - use maximum uint256 for efficiency
            max_uint256 = 2**256 - 1
            
            logger.info(f"Approving {token_address} for {router_address}")
            
            approval_tx = await client.build_approval_tx(
                token_address=token_address,
                spender=router_address,
                amount=max_uint256,
                from_address=self._account.address
            )
            
            # Sign and submit approval
            signed_approval = self._account.sign_transaction(approval_tx)
            
            approval_result = await self._submit_transaction(
                signed_approval.rawTransaction, chain
            )
            
            if not approval_result["success"]:
                return approval_result
            
            # Wait for approval confirmation
            await self._wait_for_confirmation(approval_result["tx_hash"], chain)
            
            logger.info(f"Approval confirmed: {approval_result['tx_hash']}")
            
            return {"success": True, "approval_tx": approval_result["tx_hash"]}
            
        except Exception as e:
            logger.error(f"Approval handling failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _build_and_sign_transaction(
        self,
        route: Dict[str, Any],
        amount_in: Decimal,
        expected_out: Decimal,
        slippage_bps: int,
        chain: str,
        recipient: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build and sign the swap transaction.
        """
        try:
            dex_name = route["dex"]
            adapter = self._dex_adapters[f"{chain}_{dex_name}"]
            
            # Build transaction data
            tx_data = await adapter.build_swap_tx(
                token_in=route["path"][0],
                token_out=route["path"][-1],
                amount_in=amount_in,
                amount_out_min=expected_out * (Decimal("10000") - Decimal(slippage_bps)) / Decimal("10000"),
                recipient=recipient or self._account.address,
                deadline=int((datetime.now().timestamp() + 1800))  # 30 minutes
            )
            
            if not tx_data["success"]:
                return tx_data
            
            # Get gas estimate
            client = self._evm_clients[chain]
            
            gas_estimate = await client.estimate_gas(tx_data["transaction"])
            gas_limit = int(gas_estimate * self._gas_multiplier)
            
            # Get current gas price
            gas_price = await client.get_gas_price()
            
            if gas_price > self._max_gas_price_gwei * Decimal("1e9"):
                return {
                    "success": False,
                    "error": f"Gas price too high: {gas_price / 1e9:.2f} gwei"
                }
            
            # Build final transaction
            transaction = {
                **tx_data["transaction"],
                "gas": gas_limit,
                "gasPrice": int(gas_price),
                "nonce": await client.get_nonce(self._account.address)
            }
            
            # Sign transaction
            signed_tx = self._account.sign_transaction(transaction)
            
            return {
                "success": True,
                "signed_tx": signed_tx.rawTransaction,
                "gas_estimate": gas_estimate,
                "gas_price_gwei": float(gas_price) / 1e9
            }
            
        except Exception as e:
            logger.error(f"Transaction building failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _submit_transaction(self, signed_tx: bytes, chain: str) -> Dict[str, Any]:
        """
        Submit signed transaction to the blockchain.
        """
        try:
            client = self._evm_clients[chain]
            
            tx_hash = await client.send_raw_transaction(signed_tx)
            
            logger.info(f"Transaction submitted: {tx_hash}")
            
            return {
                "success": True,
                "tx_hash": tx_hash
            }
            
        except Exception as e:
            logger.error(f"Transaction submission failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _wait_for_confirmation(
        self, 
        tx_hash: str, 
        chain: str
    ) -> Dict[str, Any]:
        """
        Wait for transaction confirmation.
        """
        try:
            client = self._evm_clients[chain]
            
            start_time = datetime.now()
            
            while (datetime.now() - start_time).seconds < self._timeout_seconds:
                try:
                    receipt = await client.get_transaction_receipt(tx_hash)
                    
                    if receipt and receipt.get("blockNumber"):
                        # Check if we have enough confirmations
                        current_block = await client.get_block_number()
                        confirmations = current_block - receipt["blockNumber"]
                        
                        if confirmations >= self._confirmation_blocks:
                            logger.info(f"Transaction confirmed: {tx_hash} ({confirmations} confirmations)")
                            return {
                                "success": True,
                                "receipt": receipt,
                                "confirmations": confirmations
                            }
                
                except TransactionNotFound:
                    pass
                
                await asyncio.sleep(2.0)  # Check every 2 seconds
            
            return {"success": False, "error": "Transaction confirmation timeout"}
            
        except Exception as e:
            logger.error(f"Confirmation waiting failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _parse_swap_result(self, receipt: Dict[str, Any], token_out: str) -> Decimal:
        """
        Parse actual amount received from transaction logs.
        """
        try:
            # Parse Transfer events to find actual amount received
            # This is a simplified version - production would parse DEX-specific events
            
            for log in receipt.get("logs", []):
                # Look for Transfer events to our address
                if (log.get("topics") and 
                    len(log["topics"]) >= 3 and 
                    log["topics"][0] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"):
                    
                    # This is a Transfer event - decode amount from data
                    amount_hex = log["data"][-64:]  # Last 32 bytes
                    amount = Decimal(int(amount_hex, 16))
                    
                    # Adjust for token decimals (assume 18 for simplicity)
                    return amount / Decimal("10") ** 18
            
            # Fallback - return 0 if can't parse
            logger.warning("Could not parse swap result from logs")
            return Decimal("0")
            
        except Exception as e:
            logger.error(f"Swap result parsing failed: {e}")
            return Decimal("0")
    
    def _calculate_slippage(self, expected: Decimal, actual: Decimal) -> int:
        """Calculate actual slippage in basis points."""
        if expected == 0:
            return 0
        
        slippage = abs((expected - actual) / expected)
        return int(slippage * 10000)  # Convert to basis points
    
    async def _initialize_chain_clients(self) -> None:
        """Initialize chain clients for all supported chains."""
        chains_config = {
            "ethereum": "https://eth.llamarpc.com",
            "bsc": "https://bsc-dataseed.binance.org",
            "base": "https://mainnet.base.org",
            "polygon": "https://polygon-rpc.com"
        }
        
        for chain, rpc_url in chains_config.items():
            try:
                client = EvmClient(chain, rpc_url)
                await client.initialize()
                self._evm_clients[chain] = client
                logger.info(f"Connected to {chain}")
            except Exception as e:
                logger.error(f"Failed to connect to {chain}: {e}")
    
    async def _initialize_dex_adapters(self) -> None:
        """Initialize DEX adapters for each chain."""
        dex_configs = {
            "ethereum": ["uniswap_v2", "uniswap_v3"],
            "bsc": ["pancakeswap_v2"],
            "base": ["uniswap_v3"],
            "polygon": ["quickswap"]
        }
        
        for chain, dexs in dex_configs.items():
            if chain in self._evm_clients:
                for dex in dexs:
                    try:
                        if dex == "uniswap_v2":
                            adapter = UniswapV2Adapter(self._evm_clients[chain])
                        elif dex == "uniswap_v3":
                            adapter = UniswapV3Adapter(self._evm_clients[chain])
                        else:
                            # Use V2 adapter as fallback
                            adapter = UniswapV2Adapter(self._evm_clients[chain])
                        
                        await adapter.initialize()
                        self._dex_adapters[f"{chain}_{dex}"] = adapter
                        logger.info(f"Initialized {dex} adapter for {chain}")
                        
                    except Exception as e:
                        logger.error(f"Failed to initialize {dex} on {chain}: {e}")
    
    def _get_available_dexs(self, chain: str) -> List[str]:
        """Get available DEXs for a chain."""
        available = []
        for key in self._dex_adapters.keys():
            if key.startswith(f"{chain}_"):
                dex_name = key.split("_", 1)[1]
                available.append(dex_name)
        return available
    
    def _is_native_token(self, token_address: str, chain: str) -> bool:
        """Check if token is native token (ETH, BNB, etc.)."""
        native_tokens = {
            "ethereum": "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            "bsc": "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            "base": "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            "polygon": "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        }
        
        return token_address.lower() == native_tokens.get(chain, "").lower()
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current engine status."""
        return {
            "initialized": self._initialized,
            "wallet_loaded": self._account is not None,
            "wallet_address": self._account.address if self._account else None,
            "connected_chains": list(self._evm_clients.keys()),
            "available_dexs": len(self._dex_adapters),
            "gas_settings": {
                "multiplier": float(self._gas_multiplier),
                "max_gas_price_gwei": float(self._max_gas_price_gwei)
            }
        }
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self._http_client.aclose()
        
        for client in self._evm_clients.values():
            await client.cleanup()


# Global live execution engine instance
live_executor = LiveExecutionEngine()