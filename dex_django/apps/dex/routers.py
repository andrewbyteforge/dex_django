from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from web3 import AsyncWeb3
from web3.contract import AsyncContract
from web3.exceptions import ContractLogicError, Web3Exception
from django.db import models

# Using your existing apps structure
from apps.chains.providers import web3_manager, ChainConfig
from apps.storage.models import Token, Pair

logger = logging.getLogger("api")


@dataclass
class SwapQuote:
    """Quote for a token swap operation."""
    amount_in: Decimal
    amount_out: Decimal
    amount_out_min: Decimal
    path: List[str]
    gas_estimate: int
    gas_price: int
    slippage_bps: int
    price_impact_bps: int
    router_address: str
    dex: str


@dataclass
class SwapParams:
    """Parameters for executing a swap."""
    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out_min: Decimal
    recipient: str
    deadline: int
    path: List[str]


class UniswapV2Router:
    """
    Uniswap V2 compatible router (works with PancakeSwap, SushiSwap, etc.).
    Handles quote calculation and swap execution.
    """
    
    # Uniswap V2 Router ABI (minimal required functions)
    ROUTER_ABI = [
        {
            "inputs": [
                {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                {"internalType": "address[]", "name": "path", "type": "address[]"}
            ],
            "name": "getAmountsOut",
            "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                {"internalType": "address[]", "name": "path", "type": "address[]"},
                {"internalType": "address", "name": "to", "type": "address"},
                {"internalType": "uint256", "name": "deadline", "type": "uint256"}
            ],
            "name": "swapExactETHForTokens",
            "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
            "stateMutability": "payable",
            "type": "function"
        },
        {
            "inputs": [
                {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                {"internalType": "address[]", "name": "path", "type": "address[]"},
                {"internalType": "address", "name": "to", "type": "address"},
                {"internalType": "uint256", "name": "deadline", "type": "uint256"}
            ],
            "name": "swapExactTokensForETH",
            "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                {"internalType": "address[]", "name": "path", "type": "address[]"},
                {"internalType": "address", "name": "to", "type": "address"},
                {"internalType": "uint256", "name": "deadline", "type": "uint256"}
            ],
            "name": "swapExactTokensForTokens",
            "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
            "stateMutability": "nonpayable",
            "type": "function"
        }
    ]
    
    def __init__(self, chain: str, router_address: str, dex_name: str):
        self.chain = chain
        self.router_address = router_address
        self.dex_name = dex_name
    
    async def get_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_bps: int = 300
    ) -> Optional[SwapQuote]:
        """Get swap quote with price impact and slippage calculation."""
        try:
            provider = await web3_manager.get_provider(self.chain)
            if not provider:
                logger.warning("No Web3 provider available for chain %s", self.chain)
                return None
            
            # Get router contract
            router_contract = provider.eth.contract(
                address=provider.to_checksum_address(self.router_address),
                abi=self.ROUTER_ABI
            )
            
            # Build swap path
            path = await self._build_swap_path(token_in, token_out)
            if not path:
                return None
            
            # Convert amount to wei
            token_in_obj = await self._get_token_info(token_in)
            if not token_in_obj:
                return None
            
            amount_in_wei = int(amount_in * Decimal(10 ** token_in_obj.decimals))
            
            # Get amounts out
            amounts_out = await router_contract.functions.getAmountsOut(
                amount_in_wei, 
                [provider.to_checksum_address(addr) for addr in path]
            ).call()
            
            if not amounts_out or len(amounts_out) < 2:
                return None
            
            # Convert output amount
            token_out_obj = await self._get_token_info(token_out)
            if not token_out_obj:
                return None
            
            amount_out = Decimal(amounts_out[-1]) / Decimal(10 ** token_out_obj.decimals)
            
            # Calculate slippage
            amount_out_min = amount_out * (Decimal(10000 - slippage_bps) / Decimal(10000))
            
            # Estimate gas
            gas_estimate = await self._estimate_swap_gas(
                provider, router_contract, token_in, token_out, amount_in_wei, path
            )
            
            # Get gas price
            gas_prices = await web3_manager.estimate_gas_price(self.chain)
            gas_price = gas_prices.get("fast", 0) if gas_prices else 0
            
            # Calculate price impact (simplified)
            price_impact_bps = await self._calculate_price_impact(
                token_in, token_out, amount_in, amount_out
            )
            
            return SwapQuote(
                amount_in=amount_in,
                amount_out=amount_out,
                amount_out_min=amount_out_min,
                path=path,
                gas_estimate=gas_estimate,
                gas_price=gas_price,
                slippage_bps=slippage_bps,
                price_impact_bps=price_impact_bps,
                router_address=self.router_address,
                dex=self.dex_name
            )
            
        except Exception as e:
            logger.warning("Failed to get quote for %s -> %s on %s: %s", 
                         token_in, token_out, self.dex_name, e)
            return None
    
    async def _build_swap_path(self, token_in: str, token_out: str) -> Optional[List[str]]:
        """Build optimal swap path between tokens."""
        chain_config = web3_manager.get_chain_config(self.chain)
        if not chain_config:
            return None
        
        # Direct path first
        if await self._pair_exists(token_in, token_out):
            return [token_in, token_out]
        
        # Try path through WETH/WBNB
        if chain_config.weth_address:
            weth = chain_config.weth_address
            if (await self._pair_exists(token_in, weth) and 
                await self._pair_exists(weth, token_out)):
                return [token_in, weth, token_out]
        
        # Try path through USDC
        if chain_config.usdc_address:
            usdc = chain_config.usdc_address
            if (await self._pair_exists(token_in, usdc) and 
                await self._pair_exists(usdc, token_out)):
                return [token_in, usdc, token_out]
        
        logger.warning("No swap path found for %s -> %s on %s", 
                      token_in, token_out, self.chain)
        return None
    
    async def _pair_exists(self, token_a: str, token_b: str) -> bool:
        """Check if a trading pair exists using your Django models."""
        try:
            # Initialize Django ORM if needed
            import django
            from django.conf import settings
            if not settings.configured:
                django.setup()
            
            # Check database first using your existing Pair model
            pair = Pair.objects.filter(
                chain__name=self.chain,
                dex=self.dex_name.lower()
            ).filter(
                models.Q(
                    base_token__address__iexact=token_a,
                    quote_token__address__iexact=token_b
                ) | models.Q(
                    base_token__address__iexact=token_b,
                    quote_token__address__iexact=token_a
                )
            ).first()
            
            return pair is not None
            
        except Exception:
            # Fallback to assume pair exists for common tokens
            return True
    
    async def _get_token_info(self, address: str) -> Optional[Token]:
        """Get token information from your Django database."""
        try:
            # Initialize Django ORM if needed
            import django
            from django.conf import settings
            if not settings.configured:
                django.setup()
            
            return Token.objects.filter(
                chain__name=self.chain,
                address__iexact=address
            ).first()
        except Exception:
            return None
    
    async def _estimate_swap_gas(
        self,
        provider: AsyncWeb3,
        router_contract: AsyncContract,
        token_in: str,
        token_out: str,
        amount_in_wei: int,
        path: List[str]
    ) -> int:
        """Estimate gas for swap transaction."""
        try:
            chain_config = web3_manager.get_chain_config(self.chain)
            if not chain_config:
                return 300000
            
            # Use different methods based on whether we're swapping ETH/native token
            is_eth_in = token_in.lower() == chain_config.weth_address.lower()
            is_eth_out = token_out.lower() == chain_config.weth_address.lower()
            
            if is_eth_in:
                # ETH -> Token swap
                gas_estimate = await router_contract.functions.swapExactETHForTokens(
                    0,  # amountOutMin (0 for estimate)
                    [provider.to_checksum_address(addr) for addr in path],
                    provider.to_checksum_address("0x" + "0" * 40),  # dummy address
                    int(asyncio.get_event_loop().time()) + 3600  # deadline
                ).estimate_gas({'value': amount_in_wei})
            elif is_eth_out:
                # Token -> ETH swap
                gas_estimate = await router_contract.functions.swapExactTokensForETH(
                    amount_in_wei,
                    0,
                    [provider.to_checksum_address(addr) for addr in path],
                    provider.to_checksum_address("0x" + "0" * 40),
                    int(asyncio.get_event_loop().time()) + 3600
                ).estimate_gas()
            else:
                # Token -> Token swap
                gas_estimate = await router_contract.functions.swapExactTokensForTokens(
                    amount_in_wei,
                    0,
                    [provider.to_checksum_address(addr) for addr in path],
                    provider.to_checksum_address("0x" + "0" * 40),
                    int(asyncio.get_event_loop().time()) + 3600
                ).estimate_gas()
            
            return int(gas_estimate * 1.2)  # Add 20% buffer
            
        except Exception as e:
            logger.warning("Gas estimation failed, using default: %s", e)
            return chain_config.gas_limit_default if chain_config else 300000
    
    async def _calculate_price_impact(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        amount_out: Decimal
    ) -> int:
        """Calculate price impact in basis points (simplified)."""
        try:
            # Get small amount quote for reference price
            small_amount = amount_in / Decimal(100)  # 1% of trade size
            small_quote = await self.get_quote(token_in, token_out, small_amount, 0)
            
            if not small_quote:
                return 9999  # High impact if we can't calculate
            
            # Calculate price per token
            small_price = small_quote.amount_out / small_quote.amount_in
            large_price = amount_out / amount_in
            
            # Price impact as basis points
            price_impact = abs(1 - (large_price / small_price)) * 10000
            return min(int(price_impact), 9999)
            
        except Exception:
            return 9999  # Return high impact on error


class DexRouterManager:
    """
    Manages multiple DEX routers and provides unified interface for trading.
    Handles router selection and quote comparison.
    """
    
    def __init__(self):
        self._routers: Dict[str, Dict[str, UniswapV2Router]] = {}
    
    async def initialize(self) -> None:
        """Initialize DEX routers for supported chains."""
        try:
            # BSC routers
            self._routers["bsc"] = {
                "pancakeswap": UniswapV2Router(
                    "bsc", "0x10ED43C718714eb63d5aA57B78B54704E256024E", "pancakeswap"
                ),
            }
            
            # Base routers
            self._routers["base"] = {
                "uniswap": UniswapV2Router(
                    "base", "0x4752ba5dbc23f44d87826276bf6fd6b1c372ad24", "uniswap"
                ),
            }
            
            # Ethereum routers (for larger trades)
            self._routers["ethereum"] = {
                "uniswap": UniswapV2Router(
                    "ethereum", "0x7a250d5630b4cf539739df2c5dacb4c659f2488d", "uniswap"
                ),
            }
            
            logger.info("DEX router manager initialized with %d chains", len(self._routers))
            
        except Exception:
            logger.exception("Failed to initialize DEX router manager")
            raise
    
    async def get_best_quote(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_bps: int = 300
    ) -> Optional[SwapQuote]:
        """Get best quote across all available DEXes on a chain."""
        if chain not in self._routers:
            return None
        
        quotes = []
        
        # Get quotes from all routers
        for dex_name, router in self._routers[chain].items():
            try:
                quote = await router.get_quote(token_in, token_out, amount_in, slippage_bps)
                if quote:
                    quotes.append(quote)
            except Exception as e:
                logger.warning("Failed to get quote from %s on %s: %s", dex_name, chain, e)
        
        if not quotes:
            return None
        
        # Return quote with highest output amount
        return max(quotes, key=lambda q: q.amount_out)
    
    async def get_router(self, chain: str, dex: str) -> Optional[UniswapV2Router]:
        """Get specific router instance."""
        return self._routers.get(chain, {}).get(dex)


# Global instance
dex_manager = DexRouterManager()