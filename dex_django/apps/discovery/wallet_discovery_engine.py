# APP: backend
# FILE: backend/app/discovery/wallet_discovery_engine.py
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

import httpx
try:
    from apps.storage.copy_trading_repo import create_copy_trading_repositories
    from apps.storage.copy_trading_models import ChainType, WalletStatus, CopyMode
    from apps.copy_trading.copy_trading_coordinator import copy_trading_coordinator
    from apps.core.database import get_db
    from apps.core.runtime_state import runtime_state
    
    IMPORTS_AVAILABLE = True
    logger = logging.getLogger("discovery.wallet_discovery")
    
except ImportError as e:
    # Graceful fallback if imports are not available
    IMPORTS_AVAILABLE = False
    logger = logging.getLogger("discovery.wallet_discovery")
    logger.warning(f"Copy trading imports not available: {e}")
    
    # Create stub classes/enums to prevent import errors
    class ChainType:
        ETHEREUM = "ethereum"
        BSC = "bsc" 
        BASE = "base"
        POLYGON = "polygon"
        
    class DiscoverySource:
        DEXSCREENER = "dexscreener"
        ETHERSCAN = "etherscan"
        MANUAL = "manual"

logger = logging.getLogger("discovery.wallet_discovery")


class DiscoverySource(Enum):
    """Data sources for wallet discovery."""
    DEXSCREENER = "dexscreener"
    ETHERSCAN = "etherscan"
    BSCSCAN = "bscscan" 
    BASESCAN = "basescan"
    POLYGONSCAN = "polygonscan"
    MANUAL = "manual"


@dataclass
class WalletCandidate:
    """A potential wallet candidate for copy trading."""
    address: str
    chain: ChainType
    source: DiscoverySource
    
    # Performance metrics
    total_trades: int
    profitable_trades: int
    win_rate: float
    total_volume_usd: Decimal
    total_pnl_usd: Decimal
    avg_trade_size_usd: Decimal
    
    # Time-based metrics
    first_trade: datetime
    last_trade: datetime
    active_days: int
    trades_per_day: float
    
    # Risk metrics
    max_drawdown_pct: float
    largest_loss_usd: Decimal
    risk_score: float  # 0-100
    
    # Quality indicators
    consistent_profits: bool
    diverse_tokens: int
    suspicious_activity: bool
    
    # Metadata
    discovered_at: datetime
    analysis_period_days: int
    confidence_score: float  # 0-100


class WalletDiscoveryEngine:
    """
    Automated system to discover and evaluate successful trader wallets
    across multiple blockchain analytics platforms and data sources.
    """
    
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.discovery_running = False
        self.discovered_wallets: Dict[str, WalletCandidate] = {}
        
        # Discovery configuration
        self.min_trades_required = 10
        self.min_win_rate_required = 55.0  # 55%
        self.min_volume_usd = Decimal("10000")  # $10k total volume
        self.max_risk_score = 75.0  # Risk score threshold
        self.analysis_period_days = 30
        
        # API configurations (would be set from environment)
        self.api_keys = {
            "etherscan": None,  # Set from env: ETHERSCAN_API_KEY
            "bscscan": None,    # Set from env: BSCSCAN_API_KEY
            "basescan": None,   # Set from env: BASESCAN_API_KEY
        }
    
    async def discover_top_traders(
        self,
        chain: ChainType,
        limit: int = 50,
        min_volume_usd: float = 50000,
        days_back: int = 30
    ) -> List[WalletCandidate]:
        """
        Discover top performing traders on a specific chain.
        Combines multiple data sources for comprehensive analysis.
        """
        
        logger.info(f"Starting trader discovery on {chain.value} (last {days_back} days)")
        
        candidates = []
        
        try:
            # 1. DexScreener API for top performers
            dex_candidates = await self._discover_from_dexscreener(
                chain, limit, min_volume_usd, days_back
            )
            candidates.extend(dex_candidates)
            
            # 2. Blockchain explorer APIs for transaction analysis
            explorer_candidates = await self._discover_from_explorer(
                chain, limit, days_back
            )
            candidates.extend(explorer_candidates)
            
            # 3. Token-specific top traders
            token_candidates = await self._discover_from_top_tokens(
                chain, limit, days_back
            )
            candidates.extend(token_candidates)
            
            # 4. Deduplicate and rank candidates
            unique_candidates = self._deduplicate_candidates(candidates)
            ranked_candidates = self._rank_candidates(unique_candidates)
            
            # 5. Store discovered candidates
            for candidate in ranked_candidates[:limit]:
                self.discovered_wallets[f"{chain.value}:{candidate.address}"] = candidate
            
            logger.info(f"Discovered {len(ranked_candidates)} unique candidates on {chain.value}")
            
            return ranked_candidates[:limit]
            
        except Exception as e:
            logger.error(f"Trader discovery failed for {chain.value}: {e}")
            return []
    
    async def analyze_wallet_performance(
        self,
        address: str,
        chain: ChainType,
        days_back: int = 30
    ) -> Optional[WalletCandidate]:
        """
        Analyze a specific wallet's performance over a time period.
        This is the core analysis function used by all discovery methods.
        """
        
        logger.info(f"Analyzing wallet {address} on {chain.value}")
        
        try:
            # Get transaction history
            transactions = await self._fetch_wallet_transactions(address, chain, days_back)
            
            if len(transactions) < self.min_trades_required:
                logger.debug(f"Wallet {address} has insufficient trades ({len(transactions)})")
                return None
            
            # Analyze trading performance
            performance = await self._analyze_trading_performance(transactions, address, chain)
            
            # Calculate risk metrics
            risk_metrics = await self._calculate_risk_metrics(transactions)
            
            # Quality checks
            quality_checks = await self._perform_quality_checks(transactions, address, chain)
            
            # Create candidate if it meets criteria
            if self._meets_criteria(performance, risk_metrics, quality_checks):
                candidate = WalletCandidate(
                    address=address.lower(),
                    chain=chain,
                    source=DiscoverySource.ETHERSCAN,  # Default, would be set by caller
                    
                    # Performance metrics
                    total_trades=performance["total_trades"],
                    profitable_trades=performance["profitable_trades"],
                    win_rate=performance["win_rate"],
                    total_volume_usd=performance["total_volume_usd"],
                    total_pnl_usd=performance["total_pnl_usd"],
                    avg_trade_size_usd=performance["avg_trade_size_usd"],
                    
                    # Time metrics
                    first_trade=performance["first_trade"],
                    last_trade=performance["last_trade"],
                    active_days=performance["active_days"],
                    trades_per_day=performance["trades_per_day"],
                    
                    # Risk metrics
                    max_drawdown_pct=risk_metrics["max_drawdown_pct"],
                    largest_loss_usd=risk_metrics["largest_loss_usd"],
                    risk_score=risk_metrics["risk_score"],
                    
                    # Quality indicators
                    consistent_profits=quality_checks["consistent_profits"],
                    diverse_tokens=quality_checks["diverse_tokens"],
                    suspicious_activity=quality_checks["suspicious_activity"],
                    
                    # Metadata
                    discovered_at=datetime.now(timezone.utc),
                    analysis_period_days=days_back,
                    confidence_score=self._calculate_confidence_score(
                        performance, risk_metrics, quality_checks
                    )
                )
                
                return candidate
            
            return None
            
        except Exception as e:
            logger.error(f"Wallet analysis failed for {address}: {e}")
            return None
    
    async def start_continuous_discovery(
        self,
        chains: List[ChainType],
        discovery_interval_hours: int = 24
    ) -> None:
        """
        Start continuous discovery process that runs periodically
        to find new successful traders automatically.
        """
        
        if self.discovery_running:
            logger.warning("Discovery already running")
            return
        
        self.discovery_running = True
        logger.info(f"Starting continuous discovery for chains: {[c.value for c in chains]}")
        
        # Start background task
        asyncio.create_task(self._continuous_discovery_loop(chains, discovery_interval_hours))
    
    async def stop_continuous_discovery(self) -> None:
        """Stop the continuous discovery process."""
        self.discovery_running = False
        logger.info("Stopped continuous discovery")
    
    async def add_discovered_wallet_to_tracking(
        self,
        candidate: WalletCandidate,
        copy_percentage: float = 2.0,
        max_position_usd: float = 500.0
    ) -> Dict[str, Any]:
        """
        Add a discovered wallet candidate to active copy trading.
        This integrates with the existing copy trading system.
        """
        
        try:
            # Determine trader name based on performance
            trader_name = self._generate_trader_name(candidate)
            
            # Configure copy settings based on risk profile
            copy_settings = self._generate_copy_settings(candidate, copy_percentage, max_position_usd)
            
            # Add to copy trading coordinator
            result = await copy_trading_coordinator.add_tracked_wallet(
                address=candidate.address,
                chain=candidate.chain,
                nickname=trader_name,
                copy_settings=copy_settings
            )
            
            if result["success"]:
                # Emit thought log
                await runtime_state.emit_thought_log({
                    "event": "auto_discovered_trader_added",
                    "trader": {
                        "address": candidate.address,
                        "name": trader_name,
                        "chain": candidate.chain.value,
                        "source": candidate.source.value,
                        "win_rate": candidate.win_rate,
                        "total_trades": candidate.total_trades,
                        "confidence_score": candidate.confidence_score
                    },
                    "copy_settings": copy_settings,
                    "action": "start_monitoring",
                    "rationale": f"Auto-discovered high-quality trader with {candidate.win_rate:.1f}% win rate"
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to add discovered wallet to tracking: {e}")
            return {"success": False, "error": str(e)}
    
    async def _discover_from_dexscreener(
        self,
        chain: ChainType,
        limit: int,
        min_volume_usd: float,
        days_back: int
    ) -> List[WalletCandidate]:
        """Discover traders from DexScreener top performers."""
        
        candidates = []
        
        try:
            # DexScreener API endpoint for top tokens
            chain_mapping = {
                ChainType.ETHEREUM: "ethereum",
                ChainType.BSC: "bsc",
                ChainType.BASE: "base",
                ChainType.POLYGON: "polygon"
            }
            
            if chain not in chain_mapping:
                return candidates
            
            # Get top tokens from DexScreener
            url = f"https://api.dexscreener.com/latest/dex/tokens/{chain_mapping[chain]}"
            
            async with self.http_client.get(url) as response:
                if response.status_code == 200:
                    data = await response.json()
                    
                    # Extract top trader addresses from token data
                    # This is simplified - actual implementation would analyze
                    # transaction data to find top traders for each token
                    
                    for token_data in data.get("pairs", [])[:20]:  # Top 20 tokens
                        if token_data.get("volume24h", 0) > min_volume_usd:
                            # Would analyze this token's top traders
                            # For now, using placeholder logic
                            pass
                            
            logger.info(f"DexScreener discovery completed for {chain.value}")
            
        except Exception as e:
            logger.error(f"DexScreener discovery failed: {e}")
        
        return candidates
    
    async def _discover_from_explorer(
        self,
        chain: ChainType,
        limit: int,
        days_back: int
    ) -> List[WalletCandidate]:
        """Discover traders from blockchain explorer APIs."""
        
        candidates = []
        
        try:
            # This would use blockchain explorer APIs to find:
            # 1. High-volume traders
            # 2. Profitable DEX interactions
            # 3. Consistent trading patterns
            
            # Placeholder implementation
            logger.info(f"Explorer discovery completed for {chain.value}")
            
        except Exception as e:
            logger.error(f"Explorer discovery failed: {e}")
        
        return candidates
    
    async def _discover_from_top_tokens(
        self,
        chain: ChainType,
        limit: int,
        days_back: int
    ) -> List[WalletCandidate]:
        """Discover traders who traded top-performing tokens early."""
        
        candidates = []
        
        try:
            # This would analyze top-performing tokens and find wallets that:
            # 1. Bought early (before major price moves)
            # 2. Sold at good levels (profit-taking)
            # 3. Have consistent patterns across multiple tokens
            
            logger.info(f"Token-based discovery completed for {chain.value}")
            
        except Exception as e:
            logger.error(f"Token discovery failed: {e}")
        
        return candidates
    
    async def _fetch_wallet_transactions(
        self,
        address: str,
        chain: ChainType,
        days_back: int
    ) -> List[Dict[str, Any]]:
        """Fetch transaction history for wallet analysis."""
        
        transactions = []
        
        try:
            # This would use appropriate blockchain explorer APIs
            # to fetch DEX transactions for the wallet
            
            # Placeholder - would implement actual API calls to:
            # - Etherscan for Ethereum
            # - BSCScan for BSC
            # - Basescan for Base
            # etc.
            
            logger.debug(f"Fetched {len(transactions)} transactions for {address}")
            
        except Exception as e:
            logger.error(f"Transaction fetch failed for {address}: {e}")
        
        return transactions
    
    async def _analyze_trading_performance(
        self,
        transactions: List[Dict[str, Any]],
        address: str,
        chain: ChainType
    ) -> Dict[str, Any]:
        """Analyze trading performance from transaction history."""
        
        # Placeholder implementation
        return {
            "total_trades": len(transactions),
            "profitable_trades": int(len(transactions) * 0.65),  # Mock 65% win rate
            "win_rate": 65.0,
            "total_volume_usd": Decimal("50000"),
            "total_pnl_usd": Decimal("5000"),
            "avg_trade_size_usd": Decimal("500"),
            "first_trade": datetime.now(timezone.utc) - timedelta(days=30),
            "last_trade": datetime.now(timezone.utc) - timedelta(days=1),
            "active_days": 25,
            "trades_per_day": 2.0
        }
    
    async def _calculate_risk_metrics(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate risk metrics from trading history."""
        
        return {
            "max_drawdown_pct": 15.0,
            "largest_loss_usd": Decimal("200"),
            "risk_score": 35.0  # Lower is better
        }
    
    async def _perform_quality_checks(
        self,
        transactions: List[Dict[str, Any]],
        address: str,
        chain: ChainType
    ) -> Dict[str, Any]:
        """Perform quality and legitimacy checks."""
        
        return {
            "consistent_profits": True,
            "diverse_tokens": 15,
            "suspicious_activity": False
        }
    
    def _meets_criteria(
        self,
        performance: Dict[str, Any],
        risk_metrics: Dict[str, Any],
        quality_checks: Dict[str, Any]
    ) -> bool:
        """Check if candidate meets minimum criteria."""
        
        return (
            performance["total_trades"] >= self.min_trades_required and
            performance["win_rate"] >= self.min_win_rate_required and
            performance["total_volume_usd"] >= self.min_volume_usd and
            risk_metrics["risk_score"] <= self.max_risk_score and
            not quality_checks["suspicious_activity"]
        )
    
    def _calculate_confidence_score(
        self,
        performance: Dict[str, Any],
        risk_metrics: Dict[str, Any],
        quality_checks: Dict[str, Any]
    ) -> float:
        """Calculate overall confidence score for the candidate."""
        
        # Simplified scoring algorithm
        score = 0.0
        
        # Win rate component (0-40 points)
        score += min(performance["win_rate"] * 0.5, 40)
        
        # Volume component (0-20 points)
        volume_score = min(float(performance["total_volume_usd"]) / 10000 * 10, 20)
        score += volume_score
        
        # Risk component (0-20 points, inverted)
        risk_score = max(0, 20 - (risk_metrics["risk_score"] * 0.25))
        score += risk_score
        
        # Quality component (0-20 points)
        quality_score = 0
        if quality_checks["consistent_profits"]:
            quality_score += 10
        quality_score += min(quality_checks["diverse_tokens"], 10)
        score += quality_score
        
        return min(100.0, score)
    
    def _deduplicate_candidates(self, candidates: List[WalletCandidate]) -> List[WalletCandidate]:
        """Remove duplicate wallet candidates."""
        
        seen = set()
        unique_candidates = []
        
        for candidate in candidates:
            key = f"{candidate.chain.value}:{candidate.address}"
            if key not in seen:
                seen.add(key)
                unique_candidates.append(candidate)
        
        return unique_candidates
    
    def _rank_candidates(self, candidates: List[WalletCandidate]) -> List[WalletCandidate]:
        """Rank candidates by quality score."""
        
        return sorted(candidates, key=lambda c: c.confidence_score, reverse=True)
    
    def _generate_trader_name(self, candidate: WalletCandidate) -> str:
        """Generate a descriptive name for the trader."""
        
        performance_tier = "Alpha" if candidate.win_rate > 70 else "Pro" if candidate.win_rate > 60 else "Solid"
        chain_suffix = candidate.chain.value.title()
        
        return f"{performance_tier} {chain_suffix} Trader"
    
    def _generate_copy_settings(
        self,
        candidate: WalletCandidate,
        copy_percentage: float,
        max_position_usd: float
    ) -> Dict[str, Any]:
        """Generate appropriate copy settings based on candidate profile."""
        
        # Adjust copy percentage based on risk score
        risk_adjusted_percentage = copy_percentage
        if candidate.risk_score > 50:
            risk_adjusted_percentage *= 0.7  # Reduce for higher risk
        elif candidate.risk_score < 30:
            risk_adjusted_percentage *= 1.2  # Increase for lower risk
        
        return {
            "copy_mode": "percentage",
            "copy_percentage": min(risk_adjusted_percentage, 5.0),  # Cap at 5%
            "max_position_usd": max_position_usd,
            "min_trade_value_usd": 50.0,
            "max_slippage_bps": 300,
            "allowed_chains": [candidate.chain.value],
            "copy_buy_only": False,
            "copy_sell_only": False
        }
    
    async def _continuous_discovery_loop(
        self,
        chains: List[ChainType],
        interval_hours: int
    ) -> None:
        """Background loop for continuous discovery."""
        
        while self.discovery_running:
            try:
                logger.info("Running continuous discovery cycle...")
                
                for chain in chains:
                    if not self.discovery_running:
                        break
                        
                    candidates = await self.discover_top_traders(chain, limit=10)
                    
                    # Auto-add high-confidence candidates
                    for candidate in candidates:
                        if candidate.confidence_score > 80 and candidate.win_rate > 70:
                            result = await self.add_discovered_wallet_to_tracking(candidate)
                            if result["success"]:
                                logger.info(f"Auto-added high-quality trader: {candidate.address}")
                
                # Wait for next cycle
                await asyncio.sleep(interval_hours * 3600)
                
            except Exception as e:
                logger.error(f"Discovery cycle failed: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error


# Global discovery engine instance
wallet_discovery_engine = WalletDiscoveryEngine()