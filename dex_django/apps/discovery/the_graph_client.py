# APP: backend
# FILE: dex_django/apps/discovery/the_graph_client.py
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("discovery")


@dataclass
class LivePairEvent:
    """Live pair creation event from The Graph."""
    
    chain: str
    dex: str
    pair_address: str
    token0_address: str
    token1_address: str
    token0_symbol: str
    token1_symbol: str
    block_number: int
    tx_hash: str
    timestamp: datetime
    initial_reserve0: Decimal = Decimal("0")
    initial_reserve1: Decimal = Decimal("0")
    
    @property
    def estimated_liquidity_usd(self) -> Decimal:
        """Estimate USD liquidity - simplified calculation."""
        # This is a rough estimate - would need price oracles for accuracy
        if self.token1_symbol in ["WETH", "ETH"]:
            return self.initial_reserve1 * Decimal("2500")  # Assume $2500 ETH
        elif self.token1_symbol in ["WBNB", "BNB"]:
            return self.initial_reserve1 * Decimal("300")   # Assume $300 BNB
        elif self.token1_symbol in ["USDC", "USDT", "DAI"]:
            return self.initial_reserve1 * Decimal("2")     # Stablecoin pairs
        return Decimal("0")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API transmission."""
        return {
            "chain": self.chain,
            "dex": self.dex,
            "pair_address": self.pair_address,
            "token0_address": self.token0_address,
            "token1_address": self.token1_address,
            "token0_symbol": self.token0_symbol,
            "token1_symbol": self.token1_symbol,
            "block_number": self.block_number,
            "tx_hash": self.tx_hash,
            "timestamp": self.timestamp.isoformat(),
            "estimated_liquidity_usd": float(self.estimated_liquidity_usd),
            "initial_reserve0": float(self.initial_reserve0),
            "initial_reserve1": float(self.initial_reserve1),
        }


class TheGraphClient:
    """Client for querying The Graph Protocol subgraphs."""
    
    # The Graph subgraph endpoints
    SUBGRAPHS = {
        "ethereum": {
            "uniswap_v2": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2",
            "uniswap_v3": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3",
        },
        "bsc": {
            "pancake_v2": "https://api.thegraph.com/subgraphs/name/pancakeswap/exchange",
        },
        "polygon": {
            "quickswap": "https://api.thegraph.com/subgraphs/name/sameepsi/quickswap06",
        },
        "base": {
            "uniswap_v3": "https://api.thegraph.com/subgraphs/name/messari/uniswap-v3-base",
        }
    }
    
    def __init__(self) -> None:
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            limits=httpx.Limits(max_connections=10)
        )
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.http_client.aclose()
    
    async def get_recent_pairs(
        self, 
        chain: str, 
        dex: str, 
        min_block: int = 0,
        limit: int = 20
    ) -> List[LivePairEvent]:
        """Get recent pair creation events from a specific chain/DEX."""
        
        if chain not in self.SUBGRAPHS or dex not in self.SUBGRAPHS[chain]:
            logger.warning(f"No subgraph available for {chain}/{dex}")
            return []
        
        subgraph_url = self.SUBGRAPHS[chain][dex]
        
        try:
            if dex in ["uniswap_v2", "pancake_v2"]:
                return await self._query_v2_pairs(subgraph_url, chain, dex, min_block, limit)
            elif dex in ["uniswap_v3"]:
                return await self._query_v3_pairs(subgraph_url, chain, dex, min_block, limit)
            else:
                logger.warning(f"Unsupported DEX type: {dex}")
                return []
                
        except Exception as e:
            logger.error(f"Error querying {chain}/{dex}: {e}")
            return []
    
    async def _query_v2_pairs(
        self, 
        subgraph_url: str, 
        chain: str, 
        dex: str, 
        min_block: int, 
        limit: int
    ) -> List[LivePairEvent]:
        """Query Uniswap V2 style subgraph for pair creation events."""
        
        query = """
        {
          pairs(
            first: %d,
            orderBy: createdAtBlockNumber,
            orderDirection: desc,
            where: { createdAtBlockNumber_gt: %d }
          ) {
            id
            token0 {
              id
              symbol
              name
            }
            token1 {
              id
              symbol  
              name
            }
            reserve0
            reserve1
            createdAtBlockNumber
            createdAtTimestamp
            txCount
            volumeUSD
          }
        }
        """ % (limit, min_block)
        
        response = await self._execute_query(subgraph_url, query)
        
        if not response or "data" not in response:
            return []
        
        pairs_data = response["data"].get("pairs", [])
        events = []
        
        for pair_data in pairs_data:
            try:
                event = LivePairEvent(
                    chain=chain,
                    dex=dex,
                    pair_address=pair_data["id"],
                    token0_address=pair_data["token0"]["id"],
                    token1_address=pair_data["token1"]["id"],
                    token0_symbol=pair_data["token0"]["symbol"] or "UNK",
                    token1_symbol=pair_data["token1"]["symbol"] or "UNK",
                    block_number=int(pair_data["createdAtBlockNumber"]),
                    tx_hash="",  # Not available in this query
                    timestamp=datetime.fromtimestamp(
                        int(pair_data["createdAtTimestamp"]), 
                        tz=timezone.utc
                    ),
                    initial_reserve0=Decimal(pair_data["reserve0"] or "0"),
                    initial_reserve1=Decimal(pair_data["reserve1"] or "0"),
                )
                
                # Only include pairs with some liquidity
                if event.estimated_liquidity_usd >= Decimal("1000"):
                    events.append(event)
                    
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Error parsing pair data: {e}")
                continue
        
        return events
    
    async def _query_v3_pairs(
        self, 
        subgraph_url: str, 
        chain: str, 
        dex: str, 
        min_block: int, 
        limit: int
    ) -> List[LivePairEvent]:
        """Query Uniswap V3 style subgraph for pool creation events."""
        
        query = """
        {
          pools(
            first: %d,
            orderBy: createdAtBlockNumber,
            orderDirection: desc,
            where: { createdAtBlockNumber_gt: %d }
          ) {
            id
            token0 {
              id
              symbol
              name
            }
            token1 {
              id
              symbol
              name  
            }
            feeTier
            liquidity
            totalValueLockedUSD
            createdAtBlockNumber
            createdAtTimestamp
            txCount
          }
        }
        """ % (limit, min_block)
        
        response = await self._execute_query(subgraph_url, query)
        
        if not response or "data" not in response:
            return []
        
        pools_data = response["data"].get("pools", [])
        events = []
        
        for pool_data in pools_data:
            try:
                # Convert total value locked to liquidity estimate
                tvl_usd = Decimal(pool_data.get("totalValueLockedUSD", "0"))
                
                event = LivePairEvent(
                    chain=chain,
                    dex=dex,
                    pair_address=pool_data["id"],
                    token0_address=pool_data["token0"]["id"],
                    token1_address=pool_data["token1"]["id"],
                    token0_symbol=pool_data["token0"]["symbol"] or "UNK",
                    token1_symbol=pool_data["token1"]["symbol"] or "UNK",
                    block_number=int(pool_data["createdAtBlockNumber"]),
                    tx_hash="",  # Not available in this query
                    timestamp=datetime.fromtimestamp(
                        int(pool_data["createdAtTimestamp"]), 
                        tz=timezone.utc
                    ),
                    initial_reserve0=Decimal("0"),  # V3 uses different liquidity model
                    initial_reserve1=Decimal("0"),
                )
                
                # Use TVL as liquidity estimate for V3
                if tvl_usd >= Decimal("1000"):
                    events.append(event)
                    
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Error parsing pool data: {e}")
                continue
        
        return events
    
    async def _execute_query(self, subgraph_url: str, query: str) -> Optional[Dict[str, Any]]:
        """Execute GraphQL query against subgraph."""
        try:
            response = await self.http_client.post(
                subgraph_url,
                json={"query": query},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"Subgraph query failed: {response.status_code}")
                return None
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Subgraph request error: {e}")
            return None


# Global client instance
graph_client = TheGraphClient()