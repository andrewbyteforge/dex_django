from __future__ import annotations

import asyncio
import os
import sys
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state for the trading bot
class BotState:
    def __init__(self):
        self.paper_mode = True
        self.autotrade_enabled = False
        self.total_trades = 0
        self.uptime_start = datetime.now(timezone.utc)
        self.settings = {
            "max_trade_size_eth": 1.0,
            "slippage_tolerance_bps": 300,
            "daily_trade_limit": 50,
            "risk_level": "conservative"
        }

bot_state = BotState()

# Create FastAPI app
app = FastAPI(
    title="DEX Sniper Pro",
    description="High-frequency DEX trading bot with AI-powered discovery",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class BotSettingsUpdate(BaseModel):
    autotrade_enabled: Optional[bool] = None
    paper_mode: Optional[bool] = None
    max_trade_size_eth: Optional[float] = Field(None, gt=0, le=10)
    slippage_tolerance_bps: Optional[int] = Field(None, ge=10, le=5000)

class QuoteRequest(BaseModel):
    chain: str
    token_in: str
    token_out: str
    amount_in: str
    slippage_bps: int = 300

class BalanceRequest(BaseModel):
    chain: str
    address: str

# Create main API router
api_router = APIRouter(prefix="/api/v1")

# Health endpoint
@app.get("/health")
async def health():
    return {"status": "ok", "service": "DEX Sniper Pro"}

# Bot endpoints with real state
@api_router.get("/bot/status")
async def bot_status():
    uptime_seconds = int((datetime.now(timezone.utc) - bot_state.uptime_start).total_seconds())
    
    return {
        "status": "ok",
        "data": {
            "status": "running" if bot_state.autotrade_enabled else "idle",
            "uptime_seconds": uptime_seconds,
            "total_trades": bot_state.total_trades,
            "paper_mode": bot_state.paper_mode,
            "autotrade_enabled": bot_state.autotrade_enabled,
            "last_trade_time": None,
            "chains_connected": ["ethereum", "bsc", "base"]
        }
    }

@api_router.get("/bot/settings")
async def bot_settings():
    return {
        "status": "ok",
        "data": {
            "autotrade_enabled": bot_state.autotrade_enabled,
            "paper_mode": bot_state.paper_mode,
            **bot_state.settings
        }
    }

@api_router.put("/bot/settings")
async def update_bot_settings(settings: BotSettingsUpdate):
    updated_fields = []
    
    if settings.autotrade_enabled is not None:
        bot_state.autotrade_enabled = settings.autotrade_enabled
        updated_fields.append("autotrade_enabled")
    
    if settings.paper_mode is not None:
        bot_state.paper_mode = settings.paper_mode
        updated_fields.append("paper_mode")
    
    if settings.max_trade_size_eth is not None:
        bot_state.settings["max_trade_size_eth"] = settings.max_trade_size_eth
        updated_fields.append("max_trade_size_eth")
    
    if settings.slippage_tolerance_bps is not None:
        bot_state.settings["slippage_tolerance_bps"] = settings.slippage_tolerance_bps
        updated_fields.append("slippage_tolerance_bps")
    
    logger.info(f"Updated bot settings: {updated_fields}")
    
    return {
        "status": "ok",
        "message": f"Updated settings: {', '.join(updated_fields)}",
        "data": {
            "autotrade_enabled": bot_state.autotrade_enabled,
            "paper_mode": bot_state.paper_mode,
            **bot_state.settings
        }
    }

# Provider endpoints
@api_router.get("/providers/")
async def providers(enabled_only: bool = False):
    providers_data = [
        {
            "id": 1,
            "name": "Ankr Ethereum",
            "url": "https://rpc.ankr.com/eth",
            "chain": "ethereum",
            "kind": "rpc",
            "enabled": True,
            "status": "active",
            "latency_ms": 45
        },
        {
            "id": 2,
            "name": "Ankr BSC",
            "url": "https://rpc.ankr.com/bsc",
            "chain": "bsc",
            "kind": "rpc",
            "enabled": True,
            "status": "active",
            "latency_ms": 32
        },
        {
            "id": 3,
            "name": "Ankr Base",
            "url": "https://rpc.ankr.com/base",
            "chain": "base",
            "kind": "rpc",
            "enabled": True,
            "status": "active",
            "latency_ms": 28
        }
    ]
    
    if enabled_only:
        providers_data = [p for p in providers_data if p["enabled"]]
    
    return {
        "status": "ok",
        "data": providers_data,
        "count": len(providers_data)
    }

# Token endpoints
@api_router.get("/tokens/")
async def tokens(page: int = 1, limit: int = 50, chain: Optional[str] = None, verified_only: bool = False):
    tokens_data = [
        {
            "id": 1,
            "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "symbol": "WETH",
            "name": "Wrapped Ether",
            "decimals": 18,
            "chain": "ethereum",
            "is_verified": True,
            "price_usd": 2000.0,
            "market_cap": 240000000000.0
        },
        {
            "id": 2,
            "address": "0xA0b86a33E6441C4C66f36aC6F7b8Aa6Da38Df51F",
            "symbol": "USDC",
            "name": "USD Coin",
            "decimals": 6,
            "chain": "ethereum",
            "is_verified": True,
            "price_usd": 1.0,
            "market_cap": 32000000000.0
        },
        {
            "id": 3,
            "address": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
            "symbol": "WBNB",
            "name": "Wrapped BNB",
            "decimals": 18,
            "chain": "bsc",
            "is_verified": True,
            "price_usd": 220.0,
            "market_cap": 34000000000.0
        }
    ]
    
    # Apply filters
    if chain:
        tokens_data = [t for t in tokens_data if t["chain"] == chain.lower()]
    
    if verified_only:
        tokens_data = [t for t in tokens_data if t["is_verified"]]
    
    # Pagination
    start = (page - 1) * limit
    end = start + limit
    paginated_tokens = tokens_data[start:end]
    
    return {
        "status": "ok",
        "data": paginated_tokens,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": len(tokens_data),
            "pages": (len(tokens_data) + limit - 1) // limit
        }
    }

# Trade endpoints
@api_router.get("/trades/")
async def trades(page: int = 1, limit: int = 50):
    # Return empty for now - trades will be added as bot executes
    return {
        "status": "ok",
        "data": [],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": 0,
            "pages": 0
        }
    }

# Enhanced trading endpoints
@api_router.get("/chains")
async def chains():
    return {
        "status": "ok",
        "chains": [
            {
                "name": "ethereum",
                "chain_id": 1,
                "native_symbol": "ETH",
                "block_time_ms": 12000,
                "gas_price_gwei": 20
            },
            {
                "name": "bsc",
                "chain_id": 56,
                "native_symbol": "BNB",
                "block_time_ms": 3000,
                "gas_price_gwei": 3
            },
            {
                "name": "base",
                "chain_id": 8453,
                "native_symbol": "ETH",
                "block_time_ms": 2000,
                "gas_price_gwei": 1
            }
        ]
    }

@api_router.post("/balance")
async def balance(request: BalanceRequest):
    # Mock balance check - in production this would query the blockchain
    mock_balances = {
        "ethereum": {"balance": "1.5", "symbol": "ETH"},
        "bsc": {"balance": "10.2", "symbol": "BNB"},
        "base": {"balance": "0.8", "symbol": "ETH"}
    }
    
    chain_balance = mock_balances.get(request.chain.lower(), {"balance": "0", "symbol": "TOKEN"})
    
    return {
        "status": "ok",
        "balance": {
            "address": request.address,
            "chain": request.chain,
            **chain_balance
        }
    }

@api_router.post("/quotes")
async def quotes(request: QuoteRequest):
    # Mock quote - in production this would query DEX routers
    try:
        amount_in = float(request.amount_in)
        # Simple mock conversion rate
        amount_out = amount_in * 1800  # ETH to USDC rate
        slippage_amount = amount_out * (request.slippage_bps / 10000)
        amount_out_min = amount_out - slippage_amount
        
        return {
            "status": "ok",
            "quote": {
                "amount_in": request.amount_in,
                "amount_out": str(amount_out),
                "amount_out_min": str(amount_out_min),
                "path": [request.token_in, request.token_out],
                "gas_estimate": 180000,
                "gas_price": 20000000000,
                "slippage_bps": request.slippage_bps,
                "price_impact_bps": 15,
                "router_address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "dex": "uniswap"
            }
        }
    except ValueError:
        raise HTTPException(400, "Invalid amount_in format")

# Paper trading
@api_router.post("/paper/toggle")
async def paper_toggle(request: dict):
    enabled = request.get("enabled", True)
    bot_state.paper_mode = enabled
    
    logger.info(f"Paper trading {'enabled' if enabled else 'disabled'}")
    
    return {
        "status": "ok",
        "paper_enabled": bot_state.paper_mode,
        "message": f"Paper trading {'enabled' if enabled else 'disabled'}"
    }

@api_router.get("/metrics/paper")
async def paper_metrics():
    return {
        "status": "ok",
        "metrics": {
            "total_trades": bot_state.total_trades,
            "winning_trades": 0,
            "total_pnl_usd": 0.0,
            "win_rate_pct": 0.0,
            "session_start": bot_state.uptime_start.isoformat()
        }
    }

# Health at API level (for frontend that expects it)
@api_router.get("/health")
async def api_health():
    return {"status": "ok", "service": "DEX Sniper Pro API"}

# Register router
app.include_router(api_router)

# Debug endpoint
@app.get("/debug/info")
async def debug_info():
    return {
        "service": "DEX Sniper Pro Enhanced",
        "total_routes": len(app.routes),
        "bot_state": {
            "paper_mode": bot_state.paper_mode,
            "autotrade_enabled": bot_state.autotrade_enabled,
            "total_trades": bot_state.total_trades,
            "uptime": str(datetime.now(timezone.utc) - bot_state.uptime_start)
        }
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting enhanced DEX Sniper Pro server...")
    uvicorn.run(
        "enhanced_main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )