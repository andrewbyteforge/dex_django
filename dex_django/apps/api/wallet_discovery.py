# APP: backend
# FILE: backend/app/api/wallet_discovery.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, validator

from backend.app.discovery.wallet_discovery_engine import (
    wallet_discovery_engine, WalletCandidate, DiscoverySource, ChainType
)
from backend.app.core.runtime_state import runtime_state

router = APIRouter(prefix="/api/v1/discovery", tags=["wallet-discovery"])
logger = logging.getLogger("api.wallet_discovery")


class DiscoveryRequest(BaseModel):
    """Request to discover top traders."""
    chains: List[str] = Field(default=["ethereum"], description="Chains to search")
    limit: int = Field(default=20, ge=5, le=100, description="Max number of traders to discover")
    min_volume_usd: float = Field(default=50000, ge=1000, description="Minimum trading volume")
    days_back: int = Field(default=30, ge=7, le=90, description="Analysis period in days")
    auto_add_threshold: float = Field(default=80.0, ge=70.0, le=95.0, description="Auto-add confidence threshold")
    
    @validator('chains')
    def validate_chains(cls, v):
        valid_chains = {"ethereum", "bsc", "base", "polygon", "arbitrum"}
        for chain in v:
            if chain not in valid_chains:
                raise ValueError(f"Invalid chain: {chain}. Must be one of: {valid_chains}")
        return v


class WalletAnalysisRequest(BaseModel):
    """Request to analyze a specific wallet."""
    address: str = Field(..., min_length=40, max_length=50, description="Wallet address to analyze")
    chain: str = Field(..., description="Blockchain to analyze on")
    days_back: int = Field(default=30, ge=7, le=90, description="Analysis period in days")
    
    @validator('address')
    def validate_address(cls, v):
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError("Invalid Ethereum address format")
        return v.lower()
    
    @validator('chain')
    def validate_chain(cls, v):
        valid_chains = {"ethereum", "bsc", "base", "polygon", "arbitrum"}
        if v not in valid_chains:
            raise ValueError(f"Invalid chain: {v}")
        return v


class ContinuousDiscoveryRequest(BaseModel):
    """Request to start/configure continuous discovery."""
    enabled: bool = Field(..., description="Enable or disable continuous discovery")
    chains: List[str] = Field(default=["ethereum", "bsc"], description="Chains to monitor")
    interval_hours: int = Field(default=24, ge=6, le=168, description="Discovery interval in hours")
    auto_add_enabled: bool = Field(default=False, description="Automatically add high-quality traders")
    auto_add_threshold: float = Field(default=85.0, ge=75.0, le=95.0, description="Auto-add threshold")


class WalletCandidateResponse(BaseModel):
    """Response model for wallet candidate."""
    address: str
    chain: str
    source: str
    
    # Performance metrics
    total_trades: int
    profitable_trades: int
    win_rate: float
    total_volume_usd: float
    total_pnl_usd: float
    avg_trade_size_usd: float
    
    # Time metrics
    first_trade: str
    last_trade: str
    active_days: int
    trades_per_day: float
    
    # Risk metrics
    max_drawdown_pct: float
    largest_loss_usd: float
    risk_score: float
    
    # Quality indicators
    consistent_profits: bool
    diverse_tokens: int
    suspicious_activity: bool
    
    # Metadata
    discovered_at: str
    confidence_score: float
    recommended_copy_percentage: float
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


@router.post("/discover-traders", summary="Discover top performing traders")
async def discover_traders(req: DiscoveryRequest) -> Dict[str, Any]:
    """
    Automatically discover top performing traders across specified chains.
    Uses multiple data sources to find and analyze successful wallets.
    """
    
    try:
        logger.info(f"Starting trader discovery: {req.chains}, {req.days_back} days")
        
        all_candidates = []
        
        # Discover on each requested chain
        for chain_str in req.chains:
            chain = ChainType(chain_str)
            
            candidates = await wallet_discovery_engine.discover_top_traders(
                chain=chain,
                limit=req.limit,
                min_volume_usd=req.min_volume_usd,
                days_back=req.days_back
            )
            
            all_candidates.extend(candidates)
        
        # Convert to response format
        candidate_responses = []
        auto_added_count = 0
        
        for candidate in all_candidates:
            # Auto-add high-confidence candidates if requested
            if candidate.confidence_score >= req.auto_add_threshold:
                result = await wallet_discovery_engine.add_discovered_wallet_to_tracking(
                    candidate,
                    copy_percentage=2.0,  # Conservative default
                    max_position_usd=500.0
                )
                
                if result["success"]:
                    auto_added_count += 1
                    logger.info(f"Auto-added trader: {candidate.address}")
            
            # Add to response
            candidate_responses.append(WalletCandidateResponse(
                address=candidate.address,
                chain=candidate.chain.value,
                source=candidate.source.value,
                total_trades=candidate.total_trades,
                profitable_trades=candidate.profitable_trades,
                win_rate=candidate.win_rate,
                total_volume_usd=float(candidate.total_volume_usd),
                total_pnl_usd=float(candidate.total_pnl_usd),
                avg_trade_size_usd=float(candidate.avg_trade_size_usd),
                first_trade=candidate.first_trade.isoformat(),
                last_trade=candidate.last_trade.isoformat(),
                active_days=candidate.active_days,
                trades_per_day=candidate.trades_per_day,
                max_drawdown_pct=candidate.max_drawdown_pct,
                largest_loss_usd=float(candidate.largest_loss_usd),
                risk_score=candidate.risk_score,
                consistent_profits=candidate.consistent_profits,
                diverse_tokens=candidate.diverse_tokens,
                suspicious_activity=candidate.suspicious_activity,
                discovered_at=candidate.discovered_at.isoformat(),
                confidence_score=candidate.confidence_score,
                recommended_copy_percentage=min(3.0, max(1.0, (100 - candidate.risk_score) / 30))
            ).dict())
        
        # Emit thought log
        await runtime_state.emit_thought_log({
            "event": "trader_discovery_completed",
            "discovery_params": {
                "chains": req.chains,
                "days_analyzed": req.days_back,
                "min_volume_usd": req.min_volume_usd
            },
            "results": {
                "total_candidates": len(all_candidates),
                "high_quality_candidates": len([c for c in all_candidates if c.confidence_score >= 80]),
                "auto_added": auto_added_count
            },
            "top_candidate": {
                "address": all_candidates[0].address if all_candidates else None,
                "win_rate": all_candidates[0].win_rate if all_candidates else 0,
                "confidence": all_candidates[0].confidence_score if all_candidates else 0
            } if all_candidates else None,
            "action": "analysis_complete",
            "rationale": f"Discovered {len(all_candidates)} potential traders, auto-added {auto_added_count} high-quality candidates"
        })
        
        return {
            "status": "success",
            "discovered_count": len(all_candidates),
            "auto_added_count": auto_added_count,
            "candidates": candidate_responses,
            "discovery_summary": {
                "chains_analyzed": req.chains,
                "analysis_period_days": req.days_back,
                "avg_confidence_score": sum(c.confidence_score for c in all_candidates) / len(all_candidates) if all_candidates else 0,
                "top_performers": len([c for c in all_candidates if c.confidence_score >= 80])
            }
        }
        
    except Exception as e:
        logger.error(f"Trader discovery failed: {e}")
        raise HTTPException(500, f"Discovery failed: {str(e)}") from e


@router.post("/analyze-wallet", summary="Analyze specific wallet performance")
async def analyze_wallet(req: WalletAnalysisRequest) -> Dict[str, Any]:
    """
    Analyze the performance of a specific wallet address.
    Provides detailed metrics and recommendation for copy trading.
    """
    
    try:
        logger.info(f"Analyzing wallet {req.address} on {req.chain}")
        
        chain = ChainType(req.chain)
        
        candidate = await wallet_discovery_engine.analyze_wallet_performance(
            address=req.address,
            chain=chain,
            days_back=req.days_back
        )
        
        if not candidate:
            return {
                "status": "not_qualified",
                "message": "Wallet does not meet minimum criteria for copy trading",
                "address": req.address,
                "chain": req.chain,
                "reasons": [
                    "Insufficient trading history",
                    "Low win rate or volume",
                    "High risk score",
                    "Suspicious activity detected"
                ]
            }
        
        # Generate recommendation
        recommendation = "strongly_recommended" if candidate.confidence_score >= 80 else \
                        "recommended" if candidate.confidence_score >= 65 else \
                        "moderate" if candidate.confidence_score >= 50 else "not_recommended"
        
        return {
            "status": "success",
            "recommendation": recommendation,
            "candidate": WalletCandidateResponse(
                address=candidate.address,
                chain=candidate.chain.value,
                source=candidate.source.value,
                total_trades=candidate.total_trades,
                profitable_trades=candidate.profitable_trades,
                win_rate=candidate.win_rate,
                total_volume_usd=float(candidate.total_volume_usd),
                total_pnl_usd=float(candidate.total_pnl_usd),
                avg_trade_size_usd=float(candidate.avg_trade_size_usd),
                first_trade=candidate.first_trade.isoformat(),
                last_trade=candidate.last_trade.isoformat(),
                active_days=candidate.active_days,
                trades_per_day=candidate.trades_per_day,
                max_drawdown_pct=candidate.max_drawdown_pct,
                largest_loss_usd=float(candidate.largest_loss_usd),
                risk_score=candidate.risk_score,
                consistent_profits=candidate.consistent_profits,
                diverse_tokens=candidate.diverse_tokens,
                suspicious_activity=candidate.suspicious_activity,
                discovered_at=candidate.discovered_at.isoformat(),
                confidence_score=candidate.confidence_score,
                recommended_copy_percentage=min(3.0, max(1.0, (100 - candidate.risk_score) / 30))
            ).dict(),
            "analysis_summary": {
                "risk_level": "low" if candidate.risk_score < 30 else "moderate" if candidate.risk_score < 60 else "high",
                "trading_style": self._infer_trading_style(candidate),
                "key_strengths": self._identify_strengths(candidate),
                "key_risks": self._identify_risks(candidate)
            }
        }
        
    except Exception as e:
        logger.error(f"Wallet analysis failed: {e}")
        raise HTTPException(500, f"Analysis failed: {str(e)}") from e


@router.post("/continuous-discovery", summary="Configure continuous discovery")
async def configure_continuous_discovery(req: ContinuousDiscoveryRequest) -> Dict[str, Any]:
    """
    Enable or configure continuous trader discovery.
    When enabled, the system automatically discovers new traders periodically.
    """
    
    try:
        if req.enabled:
            chains = [ChainType(chain) for chain in req.chains]
            
            await wallet_discovery_engine.start_continuous_discovery(
                chains=chains,
                discovery_interval_hours=req.interval_hours
            )
            
            message = f"Continuous discovery started for {req.chains}"
            logger.info(message)
            
        else:
            await wallet_discovery_engine.stop_continuous_discovery()
            message = "Continuous discovery stopped"
            logger.info(message)
        
        return {
            "status": "success",
            "message": message,
            "configuration": {
                "enabled": req.enabled,
                "chains": req.chains if req.enabled else [],
                "interval_hours": req.interval_hours if req.enabled else 0,
                "auto_add_enabled": req.auto_add_enabled,
                "auto_add_threshold": req.auto_add_threshold
            }
        }
        
    except Exception as e:
        logger.error(f"Continuous discovery configuration failed: {e}")
        raise HTTPException(500, f"Configuration failed: {str(e)}") from e


@router.get("/discovery-status", summary="Get discovery system status")
async def get_discovery_status() -> Dict[str, Any]:
    """Get current status of the wallet discovery system."""
    
    try:
        discovered_wallets = wallet_discovery_engine.discovered_wallets
        
        return {
            "status": "success",
            "discovery_running": wallet_discovery_engine.discovery_running,
            "total_discovered": len(discovered_wallets),
            "discovered_by_chain": {
                chain: len([w for w in discovered_wallets.values() if chain in w.address])
                for chain in ["ethereum", "bsc", "base", "polygon"]
            },
            "high_confidence_candidates": len([
                w for w in discovered_wallets.values() 
                if w.confidence_score >= 80
            ]),
            "recent_discoveries": [
                {
                    "address": wallet.address,
                    "chain": wallet.chain.value,
                    "confidence_score": wallet.confidence_score,
                    "discovered_at": wallet.discovered_at.isoformat()
                }
                for wallet in sorted(
                    discovered_wallets.values(),
                    key=lambda w: w.discovered_at,
                    reverse=True
                )[:5]
            ]
        }
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(500, f"Status check failed: {str(e)}") from e


@router.post("/add-discovered-wallet/{address}/{chain}", summary="Add discovered wallet to tracking")
async def add_discovered_wallet(
    address: str,
    chain: str,
    copy_percentage: float = Query(2.0, ge=0.5, le=10.0),
    max_position_usd: float = Query(500.0, ge=50.0, le=5000.0)
) -> Dict[str, Any]:
    """Add a discovered wallet to active copy trading."""
    
    try:
        wallet_key = f"{chain}:{address.lower()}"
        candidate = wallet_discovery_engine.discovered_wallets.get(wallet_key)
        
        if not candidate:
            raise HTTPException(404, f"Wallet {address} not found in discovered candidates")
        
        result = await wallet_discovery_engine.add_discovered_wallet_to_tracking(
            candidate=candidate,
            copy_percentage=copy_percentage,
            max_position_usd=max_position_usd
        )
        
        if not result["success"]:
            raise HTTPException(400, result["error"])
        
        return {
            "status": "success",
            "message": f"Added {candidate.address} to copy trading",
            "trader_details": {
                "address": candidate.address,
                "chain": candidate.chain.value,
                "confidence_score": candidate.confidence_score,
                "win_rate": candidate.win_rate,
                "copy_settings": {
                    "copy_percentage": copy_percentage,
                    "max_position_usd": max_position_usd
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add discovered wallet: {e}")
        raise HTTPException(500, f"Add failed: {str(e)}") from e


# Helper functions
def _infer_trading_style(candidate: WalletCandidate) -> str:
    """Infer trading style from candidate metrics."""
    
    if candidate.trades_per_day > 5:
        return "day_trader"
    elif candidate.trades_per_day > 1:
        return "active_trader"
    elif candidate.avg_trade_size_usd > 2000:
        return "position_trader"
    else:
        return "swing_trader"


def _identify_strengths(candidate: WalletCandidate) -> List[str]:
    """Identify key strengths of the candidate."""
    
    strengths = []
    
    if candidate.win_rate > 70:
        strengths.append("High win rate")
    if candidate.risk_score < 30:
        strengths.append("Low risk profile")
    if candidate.consistent_profits:
        strengths.append("Consistent profitability")
    if candidate.diverse_tokens > 10:
        strengths.append("Diverse token selection")
    if candidate.total_volume_usd > Decimal("100000"):
        strengths.append("High trading volume")
    
    return strengths


def _identify_risks(candidate: WalletCandidate) -> List[str]:
    """Identify key risks of the candidate."""
    
    risks = []
    
    if candidate.max_drawdown_pct > 20:
        risks.append("High maximum drawdown")
    if candidate.risk_score > 60:
        risks.append("High risk score")
    if candidate.trades_per_day > 10:
        risks.append("Very high frequency trading")
    if candidate.largest_loss_usd > Decimal("1000"):
        risks.append("Large single losses")
    if not candidate.consistent_profits:
        risks.append("Inconsistent profitability")
    
    return risks