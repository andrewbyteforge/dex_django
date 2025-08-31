from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger("intelligence.crosschain")

class CrossChainAnalyzer:
    """Multi-chain arbitrage and opportunity correlation."""
    
    def __init__(self):
        self.tracked_tokens = [
            "WETH", "USDC", "USDT", "WBTC", "DAI", "LINK", "UNI", "AAVE"
        ]
        self.chain_configs = {
            "ethereum": {"bridge_time": 600, "bridge_cost": 0.01},
            "polygon": {"bridge_time": 300, "bridge_cost": 0.005},
            "arbitrum": {"bridge_time": 900, "bridge_cost": 0.003},
            "base": {"bridge_time": 300, "bridge_cost": 0.002},
            "bsc": {"bridge_time": 180, "bridge_cost": 0.001}
        }
    
    async def find_cross_chain_opportunities(self) -> List[Dict[str, Any]]:
        """Find arbitrage across chains - most competitors can't do this."""
        
        logger.info("Scanning cross-chain arbitrage opportunities")
        
        opportunities = []
        
        try:
            # Check same token on different chains
            for token in self.tracked_tokens:
                prices = await self._get_multi_chain_prices(token)
                
                if self._has_arbitrage_opportunity(prices):
                    bridge_costs = await self._calculate_bridge_costs(token, prices)
                    bridge_time = await self._estimate_bridge_time(prices["lowest"]["chain"], prices["highest"]["chain"])
                    
                    profit_after_costs = prices["spread_usd"] - bridge_costs["total_cost_usd"]
                    
                    if profit_after_costs > 50:  # Minimum profit threshold
                        opportunities.append({
                            "token": token,
                            "buy_chain": prices["lowest"]["chain"],
                            "sell_chain": prices["highest"]["chain"],
                            "buy_price": prices["lowest"]["price"],
                            "sell_price": prices["highest"]["price"],
                            "spread_percentage": prices["spread_percentage"],
                            "spread_usd": prices["spread_usd"],
                            "bridge_costs": bridge_costs,
                            "execution_time_minutes": bridge_time,
                            "estimated_profit_usd": profit_after_costs,
                            "risk_level": self._assess_arbitrage_risk(prices, bridge_costs),
                            "confidence": 0.75
                        })
            
            # Sort by profitability
            opportunities.sort(key=lambda x: x.get("estimated_profit_usd", 0), reverse=True)
            
            logger.info(f"Found {len(opportunities)} cross-chain opportunities")
            return opportunities[:10]  # Return top 10
            
        except Exception as e:
            logger.error(f"Cross-chain analysis failed: {e}")
            return []
    
    async def _get_multi_chain_prices(self, token: str) -> Dict[str, Any]:
        """Get token prices across all supported chains."""
        
        # Mock implementation - would call real price APIs
        import random
        
        base_price = 2000 + random.randint(-100, 100)  # Mock ETH price
        
        chain_prices = {}
        for chain in self.chain_configs.keys():
            # Add some random variation for arbitrage opportunities
            variation = random.uniform(-0.05, 0.05)  # +/- 5%
            chain_price = base_price * (1 + variation)
            
            chain_prices[chain] = {
                "price": chain_price,
                "liquidity_usd": random.randint(50000, 500000),
                "last_updated": datetime.now().isoformat()
            }
        
        # Find highest and lowest
        sorted_chains = sorted(chain_prices.items(), key=lambda x: x[1]["price"])
        lowest = {"chain": sorted_chains[0][0], **sorted_chains[0][1]}
        highest = {"chain": sorted_chains[-1][0], **sorted_chains[-1][1]}
        
        spread_percentage = ((highest["price"] - lowest["price"]) / lowest["price"]) * 100
        spread_usd = highest["price"] - lowest["price"]
        
        return {
            "token": token,
            "prices": chain_prices,
            "lowest": lowest,
            "highest": highest,
            "spread_percentage": spread_percentage,
            "spread_usd": spread_usd
        }
    
    def _has_arbitrage_opportunity(self, prices: Dict[str, Any]) -> bool:
        """Check if arbitrage opportunity exists."""
        return prices["spread_percentage"] > 1.0  # At least 1% spread
    
    async def _calculate_bridge_costs(self, token: str, prices: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate bridging costs between chains."""
        
        buy_chain = prices["lowest"]["chain"]
        sell_chain = prices["highest"]["chain"]
        
        buy_chain_config = self.chain_configs[buy_chain]
        sell_chain_config = self.chain_configs[sell_chain]
        
        # Bridge costs in ETH (simplified)
        bridge_cost_eth = buy_chain_config["bridge_cost"] + sell_chain_config["bridge_cost"]
        bridge_cost_usd = bridge_cost_eth * 2000  # Mock ETH price
        
        # Gas costs for swaps
        swap_gas_cost = 0.02 * 2000  # $40 total gas for both swaps
        
        return {
            "bridge_cost_eth": bridge_cost_eth,
            "bridge_cost_usd": bridge_cost_usd,
            "gas_cost_usd": swap_gas_cost,
            "total_cost_usd": bridge_cost_usd + swap_gas_cost,
            "break_even_spread": (bridge_cost_usd + swap_gas_cost) / prices["lowest"]["price"] * 100
        }
    
    async def _estimate_bridge_time(self, from_chain: str, to_chain: str) -> int:
        """Estimate bridge time in minutes."""
        
        from_time = self.chain_configs[from_chain]["bridge_time"]
        to_time = self.chain_configs[to_chain]["bridge_time"]
        
        # Total time is max of both chains plus buffer
        return max(from_time, to_time) // 60 + 5  # Convert to minutes and add buffer
    
    def _assess_arbitrage_risk(self, prices: Dict[str, Any], bridge_costs: Dict[str, Any]) -> str:
        """Assess risk level of arbitrage opportunity."""
        
        spread_percentage = prices["spread_percentage"]
        break_even_spread = bridge_costs["break_even_spread"]
        
        safety_margin = spread_percentage - break_even_spread
        
        if safety_margin > 3.0:
            return "low"
        elif safety_margin > 1.5:
            return "medium"
        else:
            return "high"


# Global instance
cross_chain_analyzer = CrossChainAnalyzer()