# APP: backend
# FILE: dex_django/apps/api/views_live_opportunities.py
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

import httpx
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
    """Get live trading opportunities with shorter cache time."""
    trace_id = getattr(request, 'trace_id', 'unknown')
    logger.info(f"[{trace_id}] Fetching live opportunities")
    
    try:
        # Check for very recent data first (5 second cache)
        cache_key = "live_opportunities"
        timestamp_key = "live_opportunities_timestamp"
        
        opportunities = cache.get(cache_key, [])
        last_updated = cache.get(timestamp_key)
        
        # Force refresh if data is older than 10 seconds or empty
        should_refresh = (
            not opportunities or 
            not last_updated or
            (timezone.now() - datetime.fromisoformat(last_updated.replace('Z', '+00:00'))).total_seconds() > 10
        )
        
        if should_refresh:
            logger.info(f"[{trace_id}] Cache expired, fetching fresh data")
            opportunities = _fetch_live_opportunities_sync(trace_id)
            
            # Cache with shorter TTL (10 seconds)
            cache.set(cache_key, opportunities, timeout=10)  
            cache.set(timestamp_key, timezone.now().isoformat(), timeout=10)
            
            logger.info(f"[{trace_id}] Cached {len(opportunities)} fresh opportunities")
        else:
            logger.info(f"[{trace_id}] Using cached data from {last_updated}")
        
        return Response({
            "status": "ok",
            "opportunities": opportunities,
            "count": len(opportunities),
            "last_updated": cache.get(timestamp_key, timezone.now().isoformat()),
            "cache_hit": not should_refresh
        })
    
    except Exception as e:
        logger.error(f"[{trace_id}] Failed to get live opportunities: {e}", exc_info=True)
        return Response({
            "error": f"Failed to get live opportunities: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_opportunities(request) -> Response:
    """Force refresh of live opportunities and update cache."""
    trace_id = getattr(request, "trace_id", "unknown")
    logger.info("[%s] Force refreshing opportunities", trace_id)

    try:
        opportunities = _fetch_live_opportunities_sync(trace_id)
        cache.set("live_opportunities", opportunities, timeout=300)
        cache.set(
            "live_opportunities_timestamp",
            timezone.now().isoformat(),
            timeout=300,
        )
        logger.info(
            "[%s] Force refresh complete: %d opportunities",
            trace_id,
            len(opportunities),
        )

        return Response(
            {
                "status": "ok",
                "message": "Live opportunities refreshed",
                "opportunities": opportunities,
                "count": len(opportunities),
            }
        )

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "[%s] Failed to refresh opportunities: %s", trace_id, exc, exc_info=True
        )
        return Response(
            {"error": f"Failed to refresh opportunities: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def _fetch_live_opportunities_sync(trace_id: str = "unknown") -> List[Dict[str, Any]]:
    """Fetch opportunities from multiple real DEX data sources (synchronous version)."""
    opportunities = []
    
    logger.info(f"[{trace_id}] Starting multi-source DEX data fetch")
    
    # Method 1: DexScreener trending pairs (REAL DATA)
    try:
        import requests
        
        url = "https://api.dexscreener.com/latest/dex/tokens/trending"
        logger.info(f"[{trace_id}] Fetching DexScreener trending: {url}")
        
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            trending = data.get("data", [])
            
            for item in trending[:10]:  # Process top 10 trending tokens
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
    
    # Method 2: DexScreener new pairs (REAL DATA)
    try:
        import requests
        
        # Get recently created pairs
        url = "https://api.dexscreener.com/latest/dex/pairs/ethereum"
        logger.info(f"[{trace_id}] Fetching DexScreener new pairs")
        
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            pairs = data.get("pairs", [])
            
            # Filter for recently created pairs with decent liquidity
            recent_pairs = []
            for pair in pairs:
                liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0))
                if liquidity_usd >= 10000:  # Minimum liquidity filter
                    recent_pairs.append(pair)
            
            # Sort by liquidity and take top 10
            recent_pairs.sort(key=lambda x: float(x.get("liquidity", {}).get("usd", 0)), reverse=True)
            
            for pair in recent_pairs[:10]:
                opportunity = _process_dexscreener_pair(pair, trace_id)
                if opportunity:
                    opportunities.append(opportunity)
                    
            logger.info(f"[{trace_id}] DexScreener new pairs added {len(recent_pairs)} opportunities")
    
    except Exception as e:
        logger.error(f"[{trace_id}] DexScreener new pairs failed: {e}")
    
    # Method 3: Jupiter API for Solana (REAL DATA)
    try:
        import requests
        
        # Get popular tokens from Jupiter
        url = "https://token.jup.ag/strict"
        logger.info(f"[{trace_id}] Fetching Jupiter token list")
        
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            tokens = response.json()
            
            # Filter for tokens with good liquidity indicators
            popular_tokens = [t for t in tokens if t.get('symbol') and len(t.get('symbol', '')) <= 10][:20]
            
            for token in popular_tokens:
                try:
                    # Create opportunity from Jupiter data
                    opportunity = {
                        "chain": "solana",
                        "dex": "jupiter",
                        "pair_address": f"jupiter_{token['address']}",
                        "token0_symbol": token['symbol'],
                        "token1_symbol": "SOL",
                        "estimated_liquidity_usd": 50000,  # Jupiter aggregates liquidity
                        "timestamp": datetime.now().isoformat(),
                        "block_number": 0,
                        "initial_reserve0": 0,
                        "initial_reserve1": 0,
                        "source": "jupiter"
                    }
                    opportunities.append(opportunity)
                    
                except Exception as e:
                    logger.debug(f"[{trace_id}] Error processing Jupiter token {token.get('symbol')}: {e}")
                    continue
                    
            logger.info(f"[{trace_id}] Jupiter added {len([o for o in opportunities if o.get('source') == 'jupiter'])} opportunities")
    
    except Exception as e:
        logger.error(f"[{trace_id}] Jupiter API failed: {e}")
    
    # Method 4: CoinGecko trending for additional context (REAL DATA)
    try:
        import requests
        
        url = "https://api.coingecko.com/api/v3/search/trending"
        logger.info(f"[{trace_id}] Fetching CoinGecko trending")
        
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            trending_coins = data.get("coins", [])
            
            for coin_data in trending_coins[:5]:  # Top 5 trending
                coin = coin_data.get("item", {})
                try:
                    opportunity = {
                        "chain": "ethereum",  # Assume ethereum for CoinGecko trending
                        "dex": "aggregated",
                        "pair_address": f"trending_{coin.get('id', '')}",
                        "token0_symbol": coin.get('symbol', '').upper(),
                        "token1_symbol": "ETH",
                        "estimated_liquidity_usd": coin.get('market_cap_rank', 1000) * 1000,  # Estimate based on rank
                        "timestamp": datetime.now().isoformat(),
                        "block_number": 0,
                        "initial_reserve0": 0,
                        "initial_reserve1": 0,
                        "source": "coingecko_trending"
                    }
                    opportunities.append(opportunity)
                    
                except Exception as e:
                    logger.debug(f"[{trace_id}] Error processing CoinGecko coin: {e}")
                    continue
                    
            logger.info(f"[{trace_id}] CoinGecko trending added {len([o for o in opportunities if o.get('source') == 'coingecko_trending'])} opportunities")
    
    except Exception as e:
        logger.error(f"[{trace_id}] CoinGecko trending failed: {e}")
    
    # REMOVE MOCK DATA - Only use if no real data was fetched
    if len(opportunities) == 0:
        logger.warning(f"[{trace_id}] No real data fetched, adding minimal fallback")
        fallback_opportunity = {
            "chain": "ethereum",
            "dex": "uniswap_v3", 
            "pair_address": "0x0000000000000000000000000000000000000000",
            "token0_symbol": "NO_DATA",
            "token1_symbol": "WETH",
            "estimated_liquidity_usd": 0,
            "timestamp": datetime.now().isoformat(),
            "block_number": 0,
            "initial_reserve0": 0,
            "initial_reserve1": 0,
            "source": "fallback"
        }
        opportunities.append(fallback_opportunity)
    
    # Score and sort all opportunities
    for opp in opportunities:
        opp["opportunity_score"] = _calculate_opportunity_score(opp)
    
    opportunities.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)
    
    # Remove duplicates based on pair address
    seen_pairs = set()
    unique_opportunities = []
    for opp in opportunities:
        pair_key = f"{opp['chain']}_{opp['pair_address']}"
        if pair_key not in seen_pairs:
            seen_pairs.add(pair_key)
            unique_opportunities.append(opp)
    
    logger.info(f"[{trace_id}] Returning {len(unique_opportunities)} unique opportunities from real APIs")
    return unique_opportunities[:25]  # Return top 25 real opportunities


def _process_dexscreener_pair(pair: Dict[str, Any], trace_id: str) -> Dict[str, Any] | None:
    """Process a single DexScreener pair into our opportunity format."""
    try:
        # Handle both nested and direct liquidity formats
        liquidity_data = pair.get("liquidity", {})
        if isinstance(liquidity_data, dict):
            liquidity_usd = float(liquidity_data.get("usd", 0))
        else:
            liquidity_usd = float(liquidity_data) if liquidity_data else 0
            
        # Skip very low liquidity pairs
        if liquidity_usd < 5000:
            return None
            
        # Extract token information
        base_token = pair.get("baseToken", {})
        quote_token = pair.get("quoteToken", {})
        
        return {
            "chain": _normalize_chain(pair.get("chainId", "ethereum")),
            "dex": pair.get("dexId", "unknown"),
            "pair_address": pair.get("pairAddress", ""),
            "token0_symbol": base_token.get("symbol", ""),
            "token1_symbol": quote_token.get("symbol", ""),
            "estimated_liquidity_usd": liquidity_usd,
            "timestamp": pair.get("pairCreatedAt", datetime.now().isoformat()),
            "block_number": 0,
            "initial_reserve0": float(liquidity_data.get("base", 0)) if isinstance(liquidity_data, dict) else 0,
            "initial_reserve1": float(liquidity_data.get("quote", 0)) if isinstance(liquidity_data, dict) else 0,
            "source": "dexscreener",
            "price_usd": float(pair.get("priceUsd", 0)),
            "volume_24h": float(pair.get("volume", {}).get("h24", 0)) if pair.get("volume") else 0,
            "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0)) if pair.get("priceChange") else 0
        }
    except Exception as e:
        logger.error(f"[{trace_id}] Error processing DexScreener pair: {e}")
        return None

def _generate_realistic_mock_data() -> List[Dict[str, Any]]:
    """Generate realistic mock opps (dev)."""
    import random

    chains = ["ethereum", "bsc", "polygon", "base"]
    dexes = ["uniswap_v2", "uniswap_v3", "pancakeswap_v2", "quickswap"]
    base_tokens = ["WETH", "USDC", "USDT", "WBNB", "MATIC"]
    new_tokens = ["PEPE2", "CHAD", "DEGEN", "MOON", "ROCKET"]

    out: List[Dict[str, Any]] = []
    for _ in range(8):
        chain = random.choice(chains)
        dex = random.choice(dexes)
        base = random.choice(base_tokens)
        new = random.choice(new_tokens)
        out.append(
            {
                "chain": chain,
                "dex": dex,
                "pair_address": f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
                "token0_symbol": new,
                "token1_symbol": base,
                "estimated_liquidity_usd": random.randint(5_000, 200_000),
                "timestamp": datetime.now().isoformat(),
                "block_number": random.randint(18_000_000, 19_000_000),
                "initial_reserve0": random.randint(1_000, 100_000),
                "initial_reserve1": random.randint(5_000, 200_000),
                "source": "mock",
            }
        )
    return out


def _normalize_chain(chain_id: str) -> str:
    """Convert external chain IDs to our names."""
    mapping = {"ethereum": "ethereum", "bsc": "bsc", "polygon": "polygon", "base": "base"}
    result = mapping.get(chain_id, chain_id)
    logger.debug("Normalized chain %s -> %s", chain_id, result)
    return result


def _calculate_opportunity_score(opportunity: Dict[str, Any]) -> float:
    """Enhanced multi-factor scoring."""
    score = 0.0

    # Liquidity (0–15)
    liq = float(opportunity.get("estimated_liquidity_usd", 0))
    if liq >= 500_000:
        score += 15
    elif liq >= 200_000:
        score += 12
    elif liq >= 100_000:
        score += 10
    elif liq >= 50_000:
        score += 7
    elif liq >= 25_000:
        score += 5
    elif liq >= 10_000:
        score += 3
    elif liq >= 5_000:
        score += 2
    else:
        score += 1

    # Chain preference (0–5)
    chain = (opportunity.get("chain") or "").lower()
    chain_scores = {
        "ethereum": 5,
        "base": 4,
        "arbitrum": 4,
        "polygon": 3,
        "bsc": 3,
        "optimism": 3,
        "solana": 2,
    }
    score += chain_scores.get(chain, 1)

    # DEX quality (0–4)
    dex = (opportunity.get("dex") or "").lower()
    dex_scores = {
        "uniswap_v3": 4,
        "uniswap_v2": 3,
        "1inch_aggregator": 4,
        "0x_aggregator": 3,
        "pancakeswap_v3": 3,
        "pancakeswap_v2": 2,
        "quickswap": 2,
        "jupiter": 3,
        "sushiswap": 2,
        "curve": 3,
    }
    score += dex_scores.get(dex, 1)

    # Token pair quality (0–6)
    t0 = (opportunity.get("token0_symbol") or "").upper()
    t1 = (opportunity.get("token1_symbol") or "").upper()
    tier1 = {"WETH", "USDC", "USDT", "DAI", "WBTC"}
    tier2 = {"UNI", "LINK", "AAVE", "COMP", "MKR", "WBNB", "MATIC", "CAKE", "SOL"}
    tier3 = {"ARB", "OP", "AVAX", "FTM", "ATOM", "DOT", "ADA"}

    def tier_score(sym: str) -> int:
        if sym in tier1:
            return 3
        if sym in tier2:
            return 2
        if sym in tier3:
            return 1
        return 0

    score += tier_score(t0) + tier_score(t1)

    # Source reliability (0–3)
    source = (opportunity.get("source") or "").lower()
    source_scores = {
        "uniswap_v3": 3,
        "dexscreener": 2,
        "1inch": 2,
        "0x": 2,
        "pancakeswap": 2,
        "quickswap": 2,
        "jupiter": 2,
        "mock": 0,
    }
    score += source_scores.get(source, 1)

    # Freshness bonus (0–2)
    ts = opportunity.get("timestamp")
    if ts:
        try:
            opp_time = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            age_m = (datetime.now() - opp_time.replace(tzinfo=None)).total_seconds() / 60
            if age_m <= 5:
                score += 2
            elif age_m <= 30:
                score += 1
        except Exception:  # noqa: BLE001
            pass

    # Penalties
    bad_words = {
        "SCAM",
        "TEST",
        "FAKE",
        "MOON",
        "SAFE",
        "ELON",
        "SHIB",
        "PEPE",
        "DOGE",
        "FLOKI",
        "BABY",
        "MINI",
        "INU",
        "ROCKET",
        "DIAMOND",
    }
    pen = sum(1 for w in bad_words if w in t0 or w in t1)
    score -= pen * 1.5
    if liq < 5_000:
        score -= 2

    # Volume/liquidity ratio bonus
    vol24 = float(opportunity.get("volume_24h_usd", 0))
    if vol24 > 0 and liq > 0:
        r = vol24 / liq
        if r > 2.0:
            score += 2
        elif r > 1.0:
            score += 1
        elif r > 0.5:
            score += 0.5

    final_score = max(score, 0.1)
    logger.debug(
        "Score %s/%s liq=$%s chain=%s dex=%s src=%s -> %.2f",
        t0,
        t1,
        int(liq),
        chain,
        dex,
        source,
        final_score,
    )
    return final_score


def _calculate_advanced_metrics(opps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Advanced rollups (not yet exposed)."""
    if not opps:
        return {}
    total_liq = sum(float(o.get("estimated_liquidity_usd", 0)) for o in opps)
    scores = [float(o.get("opportunity_score", 0)) for o in opps]
    chains: Dict[str, int] = {}
    sources: Dict[str, int] = {}
    for o in opps:
        chains[o.get("chain", "unknown")] = chains.get(o.get("chain", "unknown"), 0) + 1
        sources[o.get("source", "unknown")] = sources.get(
            o.get("source", "unknown"), 0
        ) + 1
    return {
        "total_opportunities": len(opps),
        "total_liquidity_usd": total_liq,
        "avg_liquidity_usd": total_liq / len(opps),
        "avg_score": sum(scores) / len(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "min_score": min(scores) if scores else 0,
        "high_score_count": len([s for s in scores if s >= 15]),
        "medium_score_count": len([s for s in scores if 8 <= s < 15]),
        "low_score_count": len([s for s in scores if s < 8]),
        "chain_distribution": chains,
        "source_distribution": sources,
        "premium_opportunities": len(
            [o for o in opps if float(o.get("estimated_liquidity_usd", 0)) >= 100_000]
        ),
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def opportunity_stats(request) -> Response:
    """Get statistics about live opportunities."""
    trace_id = getattr(request, 'trace_id', 'unknown')
    
    try:
        opportunities = cache.get("live_opportunities", [])
        logger.info(f"[{trace_id}] Calculating stats for {len(opportunities)} real opportunities")
        
        total_opportunities = len(opportunities)
        high_liquidity_count = len([op for op in opportunities if op.get("estimated_liquidity_usd", 0) >= 50000])
        chains_active = len(set(op.get("chain") for op in opportunities if op.get("chain")))
        
        # Calculate real metrics
        avg_liquidity = 0
        total_volume_24h = 0
        trending_count = 0
        
        if opportunities:
            avg_liquidity = sum(op.get("estimated_liquidity_usd", 0) for op in opportunities) / len(opportunities)
            total_volume_24h = sum(op.get("volume_24h", 0) for op in opportunities)
            trending_count = len([op for op in opportunities if op.get("source") in ["dexscreener", "coingecko_trending"]])
        
        # Source breakdown
        source_breakdown = {}
        for opp in opportunities:
            source = opp.get("source", "unknown")
            source_breakdown[source] = source_breakdown.get(source, 0) + 1
        
        stats = {
            "total_opportunities": total_opportunities,
            "high_liquidity_opportunities": high_liquidity_count,
            "chains_active": chains_active,
            "average_liquidity_usd": round(avg_liquidity, 2),
            "total_volume_24h_usd": round(total_volume_24h, 2),
            "trending_opportunities": trending_count,
            "source_breakdown": source_breakdown,
            "last_updated": cache.get("live_opportunities_timestamp", "Never"),
            "data_freshness": "live" if opportunities else "no_data"
        }
        
        logger.info(f"[{trace_id}] Real data stats calculated: {stats}")
        return Response({"status": "ok", "stats": stats})
    
    except Exception as e:
        logger.error(f"[{trace_id}] Failed to get opportunity stats: {e}", exc_info=True)
        return Response({
            "error": f"Failed to get opportunity stats: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)







@api_view(["POST"])
@permission_classes([AllowAny])
def analyze_opportunity(request) -> Response:
    """Analyze a specific trading opportunity (mocked metrics for now)."""
    trace_id = getattr(request, "trace_id", "unknown")
    try:
        data = request.data
        pair_address = data.get("pair_address")
        chain = data.get("chain")
        dex = data.get("dex")
        if not all([pair_address, chain, dex]):
            return Response(
                {"error": "Missing required fields: pair_address, chain, dex"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            "[%s] Analyzing opportunity: %s/%s/%s",
            trace_id,
            chain,
            dex,
            pair_address,
        )

        analysis = _perform_opportunity_analysis(pair_address, chain, dex, trace_id)

        return Response(
            {
                "status": "ok",
                "analysis": analysis,
                "timestamp": timezone.now().isoformat(),
            }
        )

    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] Analysis failed: %s", trace_id, exc, exc_info=True)
        return Response(
            {"error": f"Analysis failed: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def _perform_opportunity_analysis(
    pair_address: str, chain: str, dex: str, trace_id: str = "unknown"
) -> Dict[str, Any]:
    """Compose a detailed (currently mocked) analysis payload."""
    return {
        "pair_info": {
            "address": pair_address,
            "chain": chain,
            "dex": dex,
            "analyzed_at": datetime.now().isoformat(),
        },
        "liquidity_analysis": _analyze_liquidity(pair_address, chain, dex, trace_id),
        "risk_assessment": _analyze_risks(pair_address, chain, dex, trace_id),
        "token_analysis": _analyze_tokens(pair_address, chain, dex, trace_id),
        "trading_signals": _generate_trading_signals(
            pair_address, chain, dex, trace_id
        ),
        "recommendation": _generate_recommendation(
            pair_address, chain, dex, trace_id
        ),
    }













def _analyze_liquidity(
    pair_address: str, chain: str, dex: str, trace_id: str
) -> Dict[str, Any]:
    """Liquidity depth & stability (mocked)."""
    return {
        "current_liquidity_usd": 125_000,
        "liquidity_depth_5pct": 8_500,
        "liquidity_depth_10pct": 15_200,
        "liquidity_stability_24h": "stable",
        "volume_24h_usd": 89_000,
        "volume_to_liquidity_ratio": 0.712,
        "large_holder_risk": "medium",
    }


def _analyze_risks(
    pair_address: str, chain: str, dex: str, trace_id: str
) -> Dict[str, Any]:
    """Risk assessment (mocked)."""
    return {
        "contract_verification": "verified",
        "honeypot_risk": "low",
        "buy_tax": 0.0,
        "sell_tax": 0.0,
        "ownership_risk": "renounced",
        "liquidity_locked": True,
        "lock_duration_days": 365,
        "suspicious_activity": False,
        "risk_score": 2.1,
        "risk_level": "low",
    }


def _analyze_tokens(
    pair_address: str, chain: str, dex: str, trace_id: str
) -> Dict[str, Any]:
    """Token fundamentals (mocked)."""
    return {
        "token0": {
            "symbol": "NEWTOKEN",
            "decimals": 18,
            "total_supply": 1_000_000_000,
            "circulating_supply": 800_000_000,
            "holder_count": 1_247,
            "top_10_holder_percentage": 23.4,
        },
        "token1": {
            "symbol": "WETH",
            "decimals": 18,
            "is_stablecoin": False,
            "is_wrapped_native": True,
        },
    }


def _generate_trading_signals(
    pair_address: str, chain: str, dex: str, trace_id: str
) -> Dict[str, Any]:
    """Signals & momentum (mocked)."""
    return {
        "momentum_score": 7.2,
        "trend_direction": "bullish",
        "volume_trend": "increasing",
        "price_action": "consolidating",
        "social_sentiment": "positive",
        "whale_activity": "accumulating",
        "technical_score": 6.8,
    }


def _generate_recommendation(
    pair_address: str, chain: str, dex: str, trace_id: str
) -> Dict[str, Any]:
    """Final trade recommendation (mocked)."""
    return {
        "action": "ENTER",
        "confidence": 0.73,
        "position_size": "small",
        "entry_strategy": "market",
        "stop_loss": 0.85,
        "take_profit_1": 1.25,
        "take_profit_2": 1.80,
        "rationale": (
            "Low risk profile with good liquidity and positive momentum. "
            "Contract verified with no major red flags."
        ),
        "max_slippage": 0.05,
        "gas_priority": "standard",
    }


def _fetch_jupiter_opportunities(trace_id: str) -> List[Dict[str, Any]]:
    """Jupiter (Solana) – heuristic/mocked liquidity."""
    out: List[Dict[str, Any]] = []
    try:
        with httpx.Client(timeout=15.0) as client:
            # Token list
            token_list = client.get("https://token.jup.ag/all")
            if token_list.status_code != 200:
                return out
            tokens = token_list.json()[:20]
            for t in tokens:
                sym = t.get("symbol")
                addr = t.get("address")
                if not (sym and addr):
                    continue
                price = client.get(f"https://price.jup.ag/v4/price?ids={addr}")
                if price.status_code != 200:
                    continue
                pjson = price.json().get("data", {}).get(addr, {})
                p = float(pjson.get("price", 0))
                if p <= 0:
                    continue
                out.append(
                    {
                        "chain": "solana",
                        "dex": "jupiter",
                        "pair_address": f"jupiter_{addr}",
                        "token0_symbol": sym,
                        "token1_symbol": "SOL",
                        "estimated_liquidity_usd": 10_000.0,  # heuristic
                        "timestamp": datetime.now().isoformat(),
                        "block_number": 0,
                        "initial_reserve0": 0,
                        "initial_reserve1": 0,
                        "source": "jupiter",
                        "price_usd": p,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] Jupiter API request failed: %s", trace_id, exc)
    return out[:10]


def _fetch_pancakeswap_opportunities(trace_id: str) -> List[Dict[str, Any]]:
    """PancakeSwap (BSC) – top pairs by reserve (API shape may vary)."""
    out: List[Dict[str, Any]] = []
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get("https://api.pancakeswap.info/api/v2/pairs")
            if resp.status_code != 200:
                return out
            pairs = resp.json().get("data", {})
            # Best-effort parse – fields may differ by API version
            for pair_id, info in list(pairs.items())[:15]:
                try:
                    liq = float(info.get("reserve_usd") or 0)
                except Exception:
                    liq = 0.0
                if liq < 10_000:
                    continue
                out.append(
                    {
                        "chain": "bsc",
                        "dex": "pancakeswap_v2",
                        "pair_address": pair_id,
                        "token0_symbol": info.get("token0", {}).get("symbol", "UNK0"),
                        "token1_symbol": info.get("token1", {}).get("symbol", "UNK1"),
                        "estimated_liquidity_usd": liq,
                        "timestamp": datetime.now().isoformat(),
                        "block_number": 0,
                        "initial_reserve0": float(info.get("reserve0") or 0),
                        "initial_reserve1": float(info.get("reserve1") or 0),
                        "source": "pancakeswap",
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] PancakeSwap API request failed: %s", trace_id, exc)
    return out[:10]


def _fetch_uniswap_subgraph_opportunities(trace_id: str) -> List[Dict[str, Any]]:
    """Uniswap V3 subgraph – top pools by TVL."""
    out: List[Dict[str, Any]] = []
    try:
        with httpx.Client(timeout=15.0) as client:
            url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
            query = """
            { pools(
                first: 20,
                orderBy: totalValueLockedUSD,
                orderDirection: desc,
                where: { totalValueLockedUSD_gt: "10000" }
              ) {
                id
                token0 { symbol name }
                token1 { symbol name }
                totalValueLockedUSD
                volumeUSD
                feeTier
                createdAtTimestamp
              }
            }
            """
            resp = client.post(url, json={"query": query})
            if resp.status_code != 200:
                return out
            pools = resp.json().get("data", {}).get("pools", [])
            for pool in pools:
                tvl = float(pool.get("totalValueLockedUSD") or 0)
                if tvl < 10_000:
                    continue
                ts = datetime.fromtimestamp(int(pool.get("createdAtTimestamp") or 0))
                out.append(
                    {
                        "chain": "ethereum",
                        "dex": "uniswap_v3",
                        "pair_address": pool.get("id", ""),
                        "token0_symbol": pool.get("token0", {}).get("symbol", "UNK0"),
                        "token1_symbol": pool.get("token1", {}).get("symbol", "UNK1"),
                        "estimated_liquidity_usd": tvl,
                        "timestamp": ts.isoformat(),
                        "block_number": 0,
                        "initial_reserve0": 0,
                        "initial_reserve1": 0,
                        "source": "uniswap_v3",
                        "fee_tier": pool.get("feeTier", 3000),
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] Uniswap subgraph failed: %s", trace_id, exc)
    return out[:10]


def _fetch_quickswap_opportunities(trace_id: str) -> List[Dict[str, Any]]:
    """QuickSwap subgraph – top pairs by reserveUSD."""
    out: List[Dict[str, Any]] = []
    try:
        with httpx.Client(timeout=15.0) as client:
            url = "https://api.thegraph.com/subgraphs/name/sameepsi/quickswap06"
            query = """
            { pairs(
                first: 15,
                orderBy: reserveUSD,
                orderDirection: desc,
                where: { reserveUSD_gt: "5000" }
              ) {
                id
                token0 { symbol name }
                token1 { symbol name }
                reserveUSD
                volumeUSD
                reserve0
                reserve1
                createdAtTimestamp
              }
            }
            """
            resp = client.post(url, json={"query": query})
            if resp.status_code != 200:
                return out
            pairs = resp.json().get("data", {}).get("pairs", [])
            for pair in pairs:
                liq = float(pair.get("reserveUSD") or 0)
                if liq < 5_000:
                    continue
                ts = datetime.fromtimestamp(int(pair.get("createdAtTimestamp") or 0))
                out.append(
                    {
                        "chain": "polygon",
                        "dex": "quickswap",
                        "pair_address": pair.get("id", ""),
                        "token0_symbol": pair.get("token0", {}).get("symbol", "UNK0"),
                        "token1_symbol": pair.get("token1", {}).get("symbol", "UNK1"),
                        "estimated_liquidity_usd": liq,
                        "timestamp": ts.isoformat(),
                        "block_number": 0,
                        "initial_reserve0": float(pair.get("reserve0") or 0),
                        "initial_reserve1": float(pair.get("reserve1") or 0),
                        "source": "quickswap",
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] QuickSwap subgraph failed: %s", trace_id, exc)
    return out[:8]


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_opportunities(request) -> Response:
    """Force refresh of live opportunities - always fetch fresh data."""
    trace_id = getattr(request, 'trace_id', 'unknown')
    logger.info(f"[{trace_id}] Force refreshing opportunities")
    
    try:
        # Always fetch fresh data, ignore cache
        opportunities = _fetch_live_opportunities_sync(trace_id)
        
        # Update cache with fresh data
        cache.set("live_opportunities", opportunities, timeout=10)
        cache.set("live_opportunities_timestamp", timezone.now().isoformat(), timeout=10)
        
        logger.info(f"[{trace_id}] Force refresh complete: {len(opportunities)} opportunities")
        
        return Response({
            "status": "ok",
            "message": "Live opportunities refreshed",
            "opportunities": opportunities,
            "count": len(opportunities),
            "forced_refresh": True,
            "timestamp": timezone.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"[{trace_id}] Failed to refresh opportunities: {e}", exc_info=True)
        return Response({
            "error": f"Failed to refresh opportunities: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _fetch_oneinch_opportunities(trace_id: str) -> List[Dict[str, Any]]:
    """1inch – heuristic over popular tokens (API keys required for many endpoints)."""
    out: List[Dict[str, Any]] = []
    chains = [
        {"chain_id": 1, "name": "ethereum"},
        {"chain_id": 56, "name": "bsc"},
        {"chain_id": 137, "name": "polygon"},
        {"chain_id": 8453, "name": "base"},
    ]
    try:
        for cfg in chains:
            tokens = _get_popular_tokens_for_chain(cfg["name"])[:3]
            for t in tokens:
                out.append(
                    {
                        "chain": cfg["name"],
                        "dex": "1inch_aggregator",
                        "pair_address": f"1inch_{t['address']}",
                        "token0_symbol": t["symbol"],
                        "token1_symbol": "WETH" if cfg["name"] == "ethereum" else "USDC",
                        "estimated_liquidity_usd": float(
                            t.get("estimated_liquidity", 50_000)
                        ),
                        "timestamp": datetime.now().isoformat(),
                        "block_number": 0,
                        "initial_reserve0": 0,
                        "initial_reserve1": 0,
                        "source": "1inch",
                        "aggregator_sources": ["uniswap", "sushiswap", "curve"],
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] 1inch heuristic failed: %s", trace_id, exc)
    return out[:10]


def _fetch_zeroex_opportunities(trace_id: str) -> List[Dict[str, Any]]:
    """0x – sources list + popular tokens (heuristic)."""
    out: List[Dict[str, Any]] = []
    chains = [
        {"name": "ethereum", "api": "https://api.0x.org"},
        {"name": "bsc", "api": "https://bsc.api.0x.org"},
        {"name": "polygon", "api": "https://polygon.api.0x.org"},
        {"name": "base", "api": "https://base.api.0x.org"},
    ]
    try:
        with httpx.Client(timeout=15.0) as client:
            for cfg in chains:
                try:
                    resp = client.get(f"{cfg['api']}/swap/v1/sources")
                    sources = list(resp.json().get("sources", {}).keys())[:5] if (
                        resp.status_code == 200
                    ) else []
                except Exception:
                    sources = []
                tokens = _get_popular_tokens_for_chain(cfg["name"])[:2]
                for t in tokens:
                    out.append(
                        {
                            "chain": cfg["name"],
                            "dex": "0x_aggregator",
                            "pair_address": f"0x_{t['address']}",
                            "token0_symbol": t["symbol"],
                            "token1_symbol": "USDC",
                            "estimated_liquidity_usd": float(
                                t.get("estimated_liquidity", 75_000)
                            ),
                            "timestamp": datetime.now().isoformat(),
                            "block_number": 0,
                            "initial_reserve0": 0,
                            "initial_reserve1": 0,
                            "source": "0x",
                            "liquidity_sources": sources,
                        }
                    )
    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] 0x API heuristic failed: %s", trace_id, exc)
    return out[:8]


def _get_popular_tokens_for_chain(chain: str) -> List[Dict[str, Any]]:
    """Static popular tokens (fallback without API keys)."""
    return {
        "ethereum": [
            {
                "symbol": "USDC",
                "address": "0xa0b86a33e6b84e7e1d29c2e3dd19e93bb9a1e6e4",
                "estimated_liquidity": 100_000,
            },
            {
                "symbol": "WETH",
                "address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                "estimated_liquidity": 150_000,
            },
            {
                "symbol": "UNI",
                "address": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
                "estimated_liquidity": 80_000,
            },
        ],
        "bsc": [
            {
                "symbol": "CAKE",
                "address": "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82",
                "estimated_liquidity": 60_000,
            },
            {
                "symbol": "WBNB",
                "address": "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c",
                "estimated_liquidity": 120_000,
            },
            {
                "symbol": "BUSD",
                "address": "0xe9e7cea3dedca5984780bafc599bd69add087d56",
                "estimated_liquidity": 90_000,
            },
        ],
        "polygon": [
            {
                "symbol": "MATIC",
                "address": "0x0000000000000000000000000000000000001010",
                "estimated_liquidity": 70_000,
            },
            {
                "symbol": "USDC",
                "address": "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",
                "estimated_liquidity": 95_000,
            },
            {
                "symbol": "WETH",
                "address": "0x7ceb23fd6f8a0e6e1bb73b1e9986c26dbb8f84e4",
                "estimated_liquidity": 85_000,
            },
        ],
        "base": [
            {
                "symbol": "USDC",
                "address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
                "estimated_liquidity": 65_000,
            },
            {
                "symbol": "WETH",
                "address": "0x4200000000000000000000000000000000000006",
                "estimated_liquidity": 110_000,
            },
        ],
        "solana": [
            {
                "symbol": "SOL",
                "address": "11111111111111111111111111111112",
                "estimated_liquidity": 80_000,
            },
            {
                "symbol": "USDC",
                "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "estimated_liquidity": 90_000,
            },
        ],
    }.get(chain, [])
