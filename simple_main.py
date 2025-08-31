from __future__ import annotations

import os
import sys
from pathlib import Path
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print(f"Project root: {project_root}")
print(f"Working directory: {os.getcwd()}")

# Create FastAPI app
app = FastAPI(
    title="DEX Sniper Pro",
    description="DEX trading bot API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create main API router
api_router = APIRouter(prefix="/api/v1")

# Health endpoint
@app.get("/health")
async def health():
    return {"status": "ok", "service": "DEX Sniper Pro"}

# Bot endpoints
@api_router.get("/bot/status")
async def bot_status():
    return {
        "status": "ok",
        "data": {
            "status": "running",
            "uptime_seconds": 3600,
            "total_trades": 0,
            "paper_mode": True
        }
    }

@api_router.get("/bot/settings")
async def bot_settings():
    return {
        "status": "ok",
        "data": {
            "autotrade_enabled": False,
            "paper_mode": True,
            "max_trade_size_eth": 1.0,
            "slippage_tolerance_bps": 300
        }
    }

# Provider endpoints
@api_router.get("/providers/")
async def providers():
    return {
        "status": "ok",
        "data": [
            {"id": 1, "name": "Ankr ETH", "url": "https://rpc.ankr.com/eth", "enabled": True},
            {"id": 2, "name": "Ankr BSC", "url": "https://rpc.ankr.com/bsc", "enabled": True}
        ]
    }

# Token endpoints
@api_router.get("/tokens/")
async def tokens():
    return {
        "status": "ok",
        "data": [
            {"id": 1, "symbol": "WETH", "name": "Wrapped Ether", "address": "0xC02a..."},
            {"id": 2, "symbol": "USDC", "name": "USD Coin", "address": "0xA0b8..."}
        ],
        "pagination": {"page": 1, "total": 2}
    }

# Trade endpoints
@api_router.get("/trades/")
async def trades():
    return {
        "status": "ok",
        "data": [],
        "pagination": {"page": 1, "total": 0}
    }

# Trading endpoints
@api_router.get("/chains")
async def chains():
    return {
        "status": "ok",
        "chains": [
            {"name": "ethereum", "chain_id": 1},
            {"name": "bsc", "chain_id": 56},
            {"name": "base", "chain_id": 8453}
        ]
    }

@api_router.post("/balance")
async def balance(request: dict):
    return {"status": "ok", "balance": {"balance": "0", "symbol": "ETH"}}

@api_router.post("/quotes")
async def quotes(request: dict):
    return {"status": "ok", "quote": {"amount_out": "100", "dex": "uniswap"}}

# Paper trading
@api_router.post("/paper/toggle")
async def paper_toggle(request: dict):
    return {"status": "ok", "paper_enabled": True}

@api_router.get("/metrics/paper")
async def paper_metrics():
    return {"status": "ok", "metrics": {"total_trades": 0}}

# Health at API level
@api_router.get("/health")
async def api_health():
    return {"status": "ok", "service": "DEX Sniper Pro API"}

# Register router
app.include_router(api_router)

# Debug endpoint
@app.get("/debug/info")
async def debug_info():
    return {
        "service": "DEX Sniper Pro Simple",
        "total_routes": len(app.routes),
        "working_dir": os.getcwd(),
        "python_path": sys.path[:3]
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting simple DEX Sniper Pro server...")
    uvicorn.run(
        "simple_main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )