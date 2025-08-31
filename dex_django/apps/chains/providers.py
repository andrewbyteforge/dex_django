from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx
from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.exceptions import Web3Exception

# Using your existing Django storage models
from apps.storage.models import Provider

logger = logging.getLogger("api")


@dataclass
class ChainConfig:
    """Chain configuration with native token and common addresses."""
    chain_id: int
    name: str
    native_symbol: str
    native_decimals: int
    rpc_urls: List[str]
    block_time_ms: int
    gas_limit_default: int
    
    # Common contract addresses
    weth_address: Optional[str] = None
    usdc_address: Optional[str] = None
    router_v2_address: Optional[str] = None
    router_v3_address: Optional[str] = None


class Web3ProviderManager:
    """
    Manages Web3 connections across multiple chains with failover support.
    Handles provider rotation and connection health monitoring.
    """
    
    CHAIN_CONFIGS = {
        "ethereum": ChainConfig(
            chain_id=1,
            name="ethereum",
            native_symbol="ETH",
            native_decimals=18,
            rpc_urls=[],  # Will be populated from database
            block_time_ms=12000,
            gas_limit_default=300000,
            weth_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            usdc_address="0xA0b86a33E6441C4C66f36aC6F7b8Aa6Da38Df51F",
        ),
        "bsc": ChainConfig(
            chain_id=56,
            name="bsc",
            native_symbol="BNB",
            native_decimals=18,
            rpc_urls=[],
            block_time_ms=3000,
            gas_limit_default=200000,
            weth_address="0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
            usdc_address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            router_v2_address="0x10ED43C718714eb63d5aA57B78B54704E256024E",  # PancakeSwap
        ),
        "base": ChainConfig(
            chain_id=8453,
            name="base",
            native_symbol="ETH",
            native_decimals=18,
            rpc_urls=[],
            block_time_ms=2000,
            gas_limit_default=200000,
            weth_address="0x4200000000000000000000000000000000000006",
            usdc_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        ),
    }
    
    def __init__(self):
        self._providers: Dict[str, List[AsyncWeb3]] = {}
        self._current_provider_index: Dict[str, int] = {}
        self._provider_health: Dict[str, Dict[int, bool]] = {}
    
    async def initialize(self) -> None:
        """Initialize Web3 providers from database configuration."""
        try:
            # Load RPC providers from your existing Django models
            from django.core.management import setup_environ
            import django
            from django.conf import settings
            
            # Initialize Django ORM for FastAPI
            if not settings.configured:
                django.setup()
            
            rpc_providers = Provider.objects.filter(
                kind=Provider.Kind.RPC,
                enabled=True
            ).order_by('id')
            
            chain_urls = {}
            for provider in rpc_providers:
                # Extract chain from provider name or URL
                chain = self._detect_chain_from_provider(provider)
                if chain:
                    if chain not in chain_urls:
                        chain_urls[chain] = []
                    chain_urls[chain].append(provider.url)
            
            # Initialize Web3 instances for each chain
            for chain, urls in chain_urls.items():
                if chain in self.CHAIN_CONFIGS:
                    await self._init_chain_providers(chain, urls)
                    
            logger.info("Web3 provider manager initialized with %d chains", len(self._providers))
            
        except Exception:
            logger.exception("Failed to initialize Web3 provider manager")
            raise
    
    def _detect_chain_from_provider(self, provider: Provider) -> Optional[str]:
        """Detect blockchain from provider name or URL."""
        name_lower = provider.name.lower()
        url_lower = provider.url.lower()
        
        if "ethereum" in name_lower or "eth" in name_lower or "mainnet" in url_lower:
            return "ethereum"
        elif "bsc" in name_lower or "binance" in name_lower or "bsc" in url_lower:
            return "bsc"
        elif "base" in name_lower or "base" in url_lower:
            return "base"
        elif "polygon" in name_lower or "matic" in url_lower:
            return "polygon"
        
        return None
    
    async def _init_chain_providers(self, chain: str, rpc_urls: List[str]) -> None:
        """Initialize Web3 providers for a specific chain."""
        try:
            providers = []
            for url in rpc_urls:
                try:
                    provider = AsyncWeb3(AsyncHTTPProvider(url))
                    # Test connection
                    await asyncio.wait_for(provider.eth.get_block_number(), timeout=5.0)
                    providers.append(provider)
                    logger.info("Connected to %s RPC: %s", chain, url[:50] + "...")
                except Exception as e:
                    logger.warning("Failed to connect to %s RPC %s: %s", chain, url[:50], e)
            
            if providers:
                self._providers[chain] = providers
                self._current_provider_index[chain] = 0
                self._provider_health[chain] = {i: True for i in range(len(providers))}
                
        except Exception:
            logger.exception("Failed to initialize providers for chain %s", chain)
    
    async def get_provider(self, chain: str) -> Optional[AsyncWeb3]:
        """Get active Web3 provider for a chain with automatic failover."""
        if chain not in self._providers or not self._providers[chain]:
            return None
        
        providers = self._providers[chain]
        current_idx = self._current_provider_index[chain]
        
        # Try current provider first
        if self._provider_health[chain].get(current_idx, False):
            return providers[current_idx]
        
        # Find next healthy provider
        for i in range(len(providers)):
            if self._provider_health[chain].get(i, False):
                self._current_provider_index[chain] = i
                return providers[i]
        
        # All providers unhealthy - try to reconnect
        await self._health_check_chain(chain)
        return providers[0] if providers else None
    
    async def get_balance(self, chain: str, address: str) -> Optional[Decimal]:
        """Get native token balance for an address."""
        provider = await self.get_provider(chain)
        if not provider:
            return None
        
        try:
            balance_wei = await provider.eth.get_balance(address)
            config = self.CHAIN_CONFIGS[chain]
            return Decimal(balance_wei) / Decimal(10 ** config.native_decimals)
        except Exception as e:
            logger.warning("Failed to get balance for %s on %s: %s", address, chain, e)
            return None
    
    def get_chain_config(self, chain: str) -> Optional[ChainConfig]:
        """Get configuration for a specific chain."""
        return self.CHAIN_CONFIGS.get(chain)


# Global instance
web3_manager = Web3ProviderManager()