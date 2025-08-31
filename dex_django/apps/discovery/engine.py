# APP: backend
# FILE: backend/app/discovery/engine.py
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

import httpx
from django.core.cache import cache
from django.utils import timezone as django_timezone

from apps.storage.models import Token, Pair, Provider

logger = logging.getLogger("discovery")


@dataclass
class NewPairEvent:
    """Detected new trading pair event."""
    
    chain: str
    dex: str
    pair_address: str
    token0_address: str
    token1_address: str
    token0_symbol: str = ""
    token1_symbol: str = ""
    initial_liquidity_usd: Decimal = Decimal("0")
    block_number: int = 0
    tx_hash: str = ""
    detected_at: datetime = None
    
    def __post_init__(self) -> None:
        if self.detected_at is None:
            self.detected_at = datetime.now(timezone.utc)
    
    @property
    def is_significant(self) -> bool:
        """Check if this pair meets significance thresholds."""
        return self.initial_liquidity_usd >= Decimal("5000")  # $5K minimum
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API/WebSocket transmission."""
        return {
            "chain": self.chain,
            "dex": self.dex,
            "pair_address": self.pair_address,
            "token0_address": self.token0_address,
            "token1_address": self.token1_address,
            "token0_symbol": self.token0_symbol,
            "token1_symbol": self.token1_symbol,
            "initial_liquidity_usd": float(self.initial_liquidity_usd),
            "block_number": self.block_number,
            "tx_hash": self.tx_hash,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class DiscoveryConfig:
    """Configuration for discovery engine."""
    
    enabled: bool = True
    scan_interval_seconds: int = 5
    min_liquidity_usd: Decimal = Decimal("5000")
    max_pairs_per_scan: int = 50
    
    # Chain-specific settings
    chains_enabled: List[str] = None
    dexes_enabled: List[str] = None
    
    def __post_init__(self) -> None:
        if self.chains_enabled is None:
            self.chains_enabled = ["ethereum", "bsc", "base", "polygon"]
        if self.dexes_enabled is None:
            self.dexes_enabled = ["uniswap_v2", "uniswap_v3", "pancake_v2", "quickswap"]


class DiscoveryEngine:
    """
    Core discovery engine for detecting new trading opportunities.
    
    Responsibilities:
    - Monitor DEX APIs for new pair creation events
    - Filter pairs by liquidity and significance thresholds
    - Store discovered pairs in database
    - Emit discovery events for autotrading evaluation
    """
    
    def __init__(self) -> None:
        self.config = DiscoveryConfig()
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.seen_pairs: Set[str] = set()  # Track processed pairs
        self.last_scan_time: Optional[datetime] = None
        
        # HTTP client for API calls
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5)
        )
    
    async def start(self) -> None:
        """Start the discovery engine scanning loop."""
        if self.running:
            logger.warning("Discovery engine already running")
            return
        
        logger.info("Starting discovery engine")
        self.running = True
        self.task = asyncio.create_task(self._discovery_loop())
    
    async def stop(self) -> None:
        """Stop the discovery engine."""
        if not self.running:
            return
        
        logger.info("Stopping discovery engine")
        self.running = False
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        await self.http_client.aclose()
    
    async def _discovery_loop(self) -> None:
        """Main discovery scanning loop."""
        while self.running:
            try:
                await self._scan_for_new_pairs()
                await asyncio.sleep(self.config.scan_interval_seconds)
            except Exception as e:
                logger.error(f"Discovery loop error: {e}", exc_info=True)
                await asyncio.sleep(10)  # Back off on errors
    
    async def _scan_for_new_pairs(self) -> None:
        """Scan all enabled chains/DEXes for new pairs."""
        if not self.config.enabled:
            return
        
        scan_start = datetime.now(timezone.utc)
        new_pairs_found = 0
        
        try:
            # Scan each enabled chain
            for chain in self.config.chains_enabled:
                for dex in self.config.dexes_enabled:
                    try:
                        pairs = await self._scan_chain_dex(chain, dex)
                        new_pairs_found += len(pairs)
                        
                        # Process each discovered pair
                        for pair_event in pairs:
                            await self._process_new_pair(pair_event)
                    
                    except Exception as e:
                        logger.warning(f"Failed to scan {chain}/{dex}: {e}")
            
            self.last_scan_time = scan_start
            
            if new_pairs_found > 0:
                logger.info(f"Discovery scan completed: {new_pairs_found} new pairs found")
        
        except Exception as e:
            logger.error(f"Discovery scan failed: {e}", exc_info=True)
    
    async def _scan_chain_dex(self, chain: str, dex: str) -> List[NewPairEvent]:
        """Scan specific chain/DEX combination for new pairs."""
        # Implementation varies by DEX - starting with mock data
        
        if chain == "ethereum" and dex == "uniswap_v2":
            return await self._scan_uniswap_v2()
        elif chain == "bsc" and dex == "pancake_v2":
            return await self._scan_pancake_v2()
        else:
            # Mock implementation for other DEXes
            return await self._mock_scan(chain, dex)
    
    async def _scan_uniswap_v2(self) -> List[NewPairEvent]:
        """Scan Uniswap V2 for new pair creation events."""
        try:
            # Query The Graph API for recent PairCreated events
            query = """
            {
              pairCreateds(
                first: 20,
                orderBy: blockNumber,
                orderDirection: desc,
                where: { blockNumber_gt: %s }
              ) {
                id
                pair
                token0 { id, symbol, name }
                token1 { id, symbol, name }
                blockNumber
                transaction { id }
              }
            }
            """ % self._get_last_block("ethereum")
            
            # Mock response for now - replace with actual The Graph API call
            return await self._mock_uniswap_response()
        
        except Exception as e:
            logger.error(f"Uniswap V2 scan error: {e}")
            return []
    
    async def _scan_pancake_v2(self) -> List[NewPairEvent]:
        """Scan PancakeSwap V2 for new pair creation events."""
        # Similar implementation to Uniswap but for BSC
        return await self._mock_scan("bsc", "pancake_v2")
    
    async def _mock_scan(self, chain: str, dex: str) -> List[NewPairEvent]:
        """Mock scan implementation for testing."""
        # Generate mock pair events occasionally
        import random
        
        if random.random() < 0.1:  # 10% chance of finding a new pair
            return [
                NewPairEvent(
                    chain=chain,
                    dex=dex,
                    pair_address=f"0x{random.randint(10**39, 10**40-1):040x}",
                    token0_address=f"0x{random.randint(10**39, 10**40-1):040x}",
                    token1_address=f"0x{random.randint(10**39, 10**40-1):040x}",
                    token0_symbol=f"TKN{random.randint(1, 999)}",
                    token1_symbol="WETH" if chain == "ethereum" else "WBNB",
                    initial_liquidity_usd=Decimal(random.randint(1000, 50000)),
                    block_number=random.randint(18000000, 19000000),
                    tx_hash=f"0x{random.randint(10**63, 10**64-1):064x}",
                )
            ]
        return []
    
    async def _mock_uniswap_response(self) -> List[NewPairEvent]:
        """Mock Uniswap API response."""
        return await self._mock_scan("ethereum", "uniswap_v2")
    
    async def _process_new_pair(self, pair_event: NewPairEvent) -> None:
        """Process a discovered new pair event."""
        pair_key = f"{pair_event.chain}:{pair_event.dex}:{pair_event.pair_address}"
        
        # Skip if already processed
        if pair_key in self.seen_pairs:
            return
        
        self.seen_pairs.add(pair_key)
        
        # Check significance threshold
        if not pair_event.is_significant:
            logger.debug(f"Pair {pair_key} below significance threshold")
            return
        
        logger.info(f"Processing significant new pair: {pair_key} "
                   f"(${pair_event.initial_liquidity_usd})")
        
        try:
            # Store in database
            await self._store_pair_in_db(pair_event)
            
            # Emit discovery event for autotrading
            await self._emit_discovery_event(pair_event)
        
        except Exception as e:
            logger.error(f"Failed to process pair {pair_key}: {e}")
    
    async def _store_pair_in_db(self, pair_event: NewPairEvent) -> None:
        """Store discovered pair in database."""
        try:
            # Get or create tokens
            token0, _ = await Token.objects.aget_or_create(
                chain=pair_event.chain,
                address=pair_event.token0_address,
                defaults={
                    "symbol": pair_event.token0_symbol,
                    "name": pair_event.token0_symbol,
                }
            )
            
            token1, _ = await Token.objects.aget_or_create(
                chain=pair_event.chain,
                address=pair_event.token1_address,
                defaults={
                    "symbol": pair_event.token1_symbol,
                    "name": pair_event.token1_symbol,
                }
            )
            
            # Create pair record
            pair, created = await Pair.objects.aget_or_create(
                chain=pair_event.chain,
                dex=pair_event.dex,
                address=pair_event.pair_address,
                defaults={
                    "base_token": token0,
                    "quote_token": token1,
                }
            )
            
            if created:
                logger.info(f"Stored new pair in database: {pair}")
        
        except Exception as e:
            logger.error(f"Database storage error: {e}")
    
    async def _emit_discovery_event(self, pair_event: NewPairEvent) -> None:
        """Emit discovery event for autotrading evaluation."""
        # Cache the event for API access
        cache_key = f"discovery_event:{pair_event.pair_address}"
        cache.set(cache_key, pair_event.to_dict(), timeout=3600)  # 1 hour
        
        # TODO: Emit via WebSocket to connected clients
        # TODO: Trigger autotrading evaluation
        
        logger.info(f"Discovery event emitted: {pair_event.pair_address}")
    
    def _get_last_block(self, chain: str) -> int:
        """Get last processed block number for chain."""
        # Simple cache-based tracking - replace with persistent storage
        cache_key = f"last_block:{chain}"
        return cache.get(cache_key, 18000000)  # Default starting block
    
    def _set_last_block(self, chain: str, block_number: int) -> None:
        """Update last processed block number."""
        cache_key = f"last_block:{chain}"
        cache.set(cache_key, block_number, timeout=None)


# Global discovery engine instance
discovery_engine = DiscoveryEngine()