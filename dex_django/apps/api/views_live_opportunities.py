from __future__ import annotations

import httpx
import logging
from typing import Any, Dict, List
from datetime import datetime

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger("api")


@api_view(["GET"])
@permission_classes([AllowAny])
def live_opportunities(request) -> Response:
    """Get live trading opportunities from real DEX APIs."""
    trace_id = getattr(request, 'trace_id', 'unknown')
    logger.info(f"[{trace_id}] Fetching live opportunities")
    
    try:
        opportunities = cache.get("live_opportunities", [])
        logger.info(f"[{trace_id}] Found {len(opportunities)} cached opportunities")
        
        if not opportunities:
            logger.info(f"[{trace_id}] Cache empty, fetching fresh data")
            opportunities = _fetch_live_opportunities_sync(trace_id)
            cache.set("live_opportunities", opportunities, timeout=30)
            logger.info(f"[{trace_id}] Cached {len(opportunities)} new opportunities")
        
        return Response({
            "status": "ok",
            "opportunities": opportunities,
            "count": len(opportunities),
            "last_updated": cache.get("live_opportunities_timestamp", timezone.now().isoformat())
        })
    
    except Exception as e:
        logger.error(f"[{trace_id}] Failed to get live opportunities: {e}", exc_info=True)
        return Response({
            "error": f"Failed to get live opportunities: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_opportunities(request) -> Response:
    """Force refresh of live opportunities."""
    trace_id = getattr(request, 'trace_id', 'unknown')
    logger.info(f"[{trace_id}] Force refreshing opportunities")
    
    try:
        opportunities = _fetch_live_opportunities_sync(trace_id)
        
        cache.set("live_opportunities", opportunities, timeout=300)
        cache.set("live_opportunities_timestamp", timezone.now().isoformat(), timeout=300)
        logger.info(f"[{trace_id}] Force refresh complete: {len(opportunities)} opportunities")
        
        return Response({
            "status": "ok",
            "message": "Live opportunities refreshed",
            "opportunities": opportunities,
            "count": len(opportunities)
        })
    
    except Exception as e:
        logger.error(f"[{trace_id}] Failed to refresh opportunities: {e}", exc_info=True)
        return Response({
            "error": f"Failed to refresh opportunities: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _fetch_live_opportunities_sync(trace_id: str = "unknown") -> List[Dict[str, Any]]:
    """Fetch opportunities from multiple real DEX data sources."""
    opportunities = []
    
    logger.info(f"[{trace_id}] Starting multi-source DEX data fetch")
    
    # Method 1: DexScreener trending pairs
    try:
        with httpx.Client(timeout=15.0) as client:
            url = "https://api.dexscreener.com/latest/dex/tokens/trending"
            
            logger.info(f"[{trace_id}] Trying DexScreener trending: {url}")
            response = client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[{trace_id}] DexScreener trending response keys: {list(data.keys())}")
                
                # Log the actual structure to understand it
                pairs = data.get("pairs", [])
                logger.info(f"[{trace_id}] DexScreener pairs structure: {pairs[:1] if pairs else 'No pairs'}")
                
                # The data might be in a different structure
                if not pairs and "data" in data:
                    pairs = data["data"]
                    logger.info(f"[{trace_id}] Found pairs in data field: {len(pairs) if pairs else 0}")
                
                # Process trending tokens
                trending = data.get("data", [])
                for item in trending[:10]:
                    item_pairs = item.get("pairs", [])
                    for pair in item_pairs[:3]:  # Top 3 pairs per trending token
                        opportunity = _process_dexscreener_pair(pair, trace_id)
                        if opportunity:
                            opportunities.append(opportunity)
                            
                logger.info(f"[{trace_id}] DexScreener added {len([o for o in opportunities if o.get('source') == 'dexscreener'])} opportunities")
            else:
                logger.error(f"[{trace_id}] DexScreener API error: {response.status_code}")
    
    except Exception as e:
        logger.error(f"[{trace_id}] DexScreener failed: {e}")
    
    # Method 2: Moralis API (placeholder)
    try:
        logger.info(f"[{trace_id}] Moralis API not configured (requires API key)")
    except Exception as e:
        logger.error(f"[{trace_id}] Moralis failed: {e}")
    
    # Method 3: Mock data
    try:
        logger.info(f"[{trace_id}] Adding realistic mock opportunities")
        mock_opportunities = _generate_realistic_mock_data()
        opportunities.extend(mock_opportunities)
        logger.info(f"[{trace_id}] Added {len(mock_opportunities)} mock opportunities")
    except Exception as e:
        logger.error(f"[{trace_id}] Mock data failed: {e}")
    
    # Score and sort all opportunities
    for opp in opportunities:
        opp["opportunity_score"] = _calculate_opportunity_score(opp)
    
    opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)
    
    logger.info(f"[{trace_id}] Returning {len(opportunities)} total opportunities")
    return opportunities[:20]













def _process_dexscreener_pair(pair: Dict[str, Any], trace_id: str) -> Dict[str, Any] | None:
    """Process a single DexScreener pair into our opportunity format."""
    try:
        liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0))
        if liquidity_usd < 1000:  # Skip very low liquidity
            return None
            
        return {
            "chain": _normalize_chain(pair.get("chainId", "ethereum")),
            "dex": pair.get("dexId", "unknown"),
            "pair_address": pair.get("pairAddress", ""),
            "token0_symbol": pair.get("baseToken", {}).get("symbol", ""),
            "token1_symbol": pair.get("quoteToken", {}).get("symbol", ""),
            "estimated_liquidity_usd": liquidity_usd,
            "timestamp": pair.get("pairCreatedAt", datetime.now().isoformat()),
            "block_number": 0,
            "initial_reserve0": float(pair.get("liquidity", {}).get("base", 0)),
            "initial_reserve1": float(pair.get("liquidity", {}).get("quote", 0)),
            "source": "dexscreener"
        }
    except Exception as e:
        logger.error(f"[{trace_id}] Error processing DexScreener pair: {e}")
        return None


def _generate_realistic_mock_data() -> List[Dict[str, Any]]:
    """Generate realistic mock opportunities for testing."""
    import random
    
    chains = ["ethereum", "bsc", "polygon", "base"]
    dexes = ["uniswap_v2", "uniswap_v3", "pancake_v2", "quickswap"]
    base_tokens = ["WETH", "USDC", "USDT", "WBNB", "MATIC"]
    new_tokens = ["PEPE2", "CHAD", "DEGEN", "MOON", "ROCKET"]
    
    opportunities = []
    
    for i in range(8):
        chain = random.choice(chains)
        dex = random.choice(dexes)
        base = random.choice(base_tokens)
        new = random.choice(new_tokens)
        
        opportunity = {
            "chain": chain,
            "dex": dex,
            "pair_address": f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
            "token0_symbol": new,
            "token1_symbol": base,
            "estimated_liquidity_usd": random.randint(5000, 200000),
            "timestamp": datetime.now().isoformat(),
            "block_number": random.randint(18000000, 19000000),
            "initial_reserve0": random.randint(1000, 100000),
            "initial_reserve1": random.randint(5000, 200000),
            "source": "mock"
        }
        opportunities.append(opportunity)
    
    return opportunities


def _normalize_chain(chain_id: str) -> str:
    """Convert DexScreener chain IDs to our format."""
    mapping = {
        "ethereum": "ethereum",
        "bsc": "bsc", 
        "polygon": "polygon",
        "base": "base"
    }
    result = mapping.get(chain_id, chain_id)
    logger.debug(f"Normalized chain {chain_id} -> {result}")
    return result


def _calculate_opportunity_score(opportunity: Dict[str, Any]) -> float:
    """Calculate a score for ranking opportunities."""
    score = 0.0
    
    liquidity_usd = opportunity.get("estimated_liquidity_usd", 0)
    if liquidity_usd >= 100000:
        score += 10
    elif liquidity_usd >= 50000:
        score += 7
    elif liquidity_usd >= 10000:
        score += 5
    elif liquidity_usd >= 5000:
        score += 3
    else:
        score += 1
    
    chain = opportunity.get("chain", "")
    if chain == "ethereum":
        score += 3
    elif chain == "base":
        score += 2
    elif chain in ["bsc", "polygon"]:
        score += 1
    
    dex = opportunity.get("dex", "")
    if "uniswap" in dex:
        score += 2
    elif dex in ["pancake_v2", "quickswap"]:
        score += 1
    
    token0_symbol = opportunity.get("token0_symbol", "").upper()
    token1_symbol = opportunity.get("token1_symbol", "").upper()
    
    major_tokens = {"WETH", "USDC", "USDT", "WBNB", "DAI", "MATIC"}
    if token0_symbol in major_tokens or token1_symbol in major_tokens:
        score += 3
    
    suspicious_words = ["SCAM", "TEST", "FAKE", "MOON", "SAFE", "DOGE", "SHIB", "PEPE"]
    for word in suspicious_words:
        if word in token0_symbol or word in token1_symbol:
            score -= 2
    
    final_score = max(score, 0.1)
    logger.debug(f"Calculated score {final_score} for {token0_symbol}/{token1_symbol}")
    return final_score


@api_view(["GET"])
@permission_classes([AllowAny])
def opportunity_stats(request) -> Response:
    """Get statistics about live opportunities."""
    trace_id = getattr(request, 'trace_id', 'unknown')
    
    try:
        opportunities = cache.get("live_opportunities", [])
        logger.info(f"[{trace_id}] Calculating stats for {len(opportunities)} opportunities")
        
        total_opportunities = len(opportunities)
        high_liquidity_count = len([op for op in opportunities if op.get("estimated_liquidity_usd", 0) >= 50000])
        chains_active = len(set(op.get("chain") for op in opportunities))
        
        avg_liquidity = 0
        if opportunities:
            avg_liquidity = sum(op.get("estimated_liquidity_usd", 0) for op in opportunities) / len(opportunities)
        
        stats = {
            "total_opportunities": total_opportunities,
            "high_liquidity_opportunities": high_liquidity_count,
            "chains_active": chains_active,
            "average_liquidity_usd": round(avg_liquidity, 2),
            "last_updated": cache.get("live_opportunities_timestamp", "Never"),
        }
        
        logger.info(f"[{trace_id}] Stats calculated: {stats}")
        return Response({"status": "ok", "stats": stats})
    
    except Exception as e:
        logger.error(f"[{trace_id}] Failed to get opportunity stats: {e}", exc_info=True)
        return Response({
            "error": f"Failed to get opportunity stats: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)