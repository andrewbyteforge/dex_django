from __future__ import annotations

import os
import sys
from fastapi import FastAPI, APIRouter, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"Project root: {project_root}")

# Create health router
health_router = APIRouter()

@health_router.get("/health")
async def health_check():
    return {
        "status": "ok", 
        "service": "DEX Sniper Pro Debug",
        "message": "Routes working!"
    }

@health_router.get("/health/ready") 
async def readiness_check():
    return {
        "status": "ok",
        "service": "DEX Sniper Pro Debug", 
        "dependencies": {"test": "working"}
    }

# Create API v1 router
api_router = APIRouter(prefix="/api/v1")

# Bot endpoints (missing from original)
@api_router.get("/bot/status")
async def get_bot_status():
    return {
        "status": "ok",
        "data": {
            "status": "running",
            "uptime_seconds": 3600,
            "total_trades": 0,
            "active_positions": 0,
            "paper_mode": True,
            "last_trade_time": None
        }
    }

@api_router.get("/bot/settings")
async def get_bot_settings():
    return {
        "status": "ok",
        "data": {
            "autotrade_enabled": False,
            "paper_mode": True,
            "max_trade_size_eth": 1.0,
            "slippage_tolerance_bps": 300,
            "daily_trade_limit": 50,
            "risk_level": "conservative"
        }
    }

# Providers endpoint (missing)
@api_router.get("/providers/")
async def get_providers():
    return {
        "status": "ok",
        "data": [
            {
                "id": 1,
                "name": "Ankr Ethereum",
                "url": "https://rpc.ankr.com/eth",
                "chain": "ethereum",
                "kind": "rpc",
                "enabled": True,
                "status": "active"
            },
            {
                "id": 2,
                "name": "Ankr BSC", 
                "url": "https://rpc.ankr.com/bsc",
                "chain": "bsc",
                "kind": "rpc",
                "enabled": True,
                "status": "active"
            }
        ],
        "count": 2
    }

# Tokens endpoint (missing)
@api_router.get("/tokens/")
async def get_tokens(page: int = 1):
    return {
        "status": "ok",
        "data": [
            {
                "id": 1,
                "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "symbol": "WETH",
                "name": "Wrapped Ether",
                "decimals": 18,
                "chain": "ethereum",
                "is_verified": True,
                "price_usd": 2000.0
            },
            {
                "id": 2,
                "address": "0xA0b86a33E6441C4C66f36aC6F7b8Aa6Da38Df51F",
                "symbol": "USDC",
                "name": "USD Coin",
                "decimals": 6,
                "chain": "ethereum",
                "is_verified": True,
                "price_usd": 1.0
            }
        ],
        "pagination": {
            "page": page,
            "limit": 50,
            "total": 2,
            "pages": 1
        }
    }

# Trades endpoint (missing)
@api_router.get("/trades/")
async def get_trades(page: int = 1):
    return {
        "status": "ok",
        "data": [],
        "pagination": {
            "page": page,
            "limit": 50,
            "total": 0,
            "pages": 0
        }
    }

# Health endpoint at API level (your frontend expects this)
@api_router.get("/health")
async def api_health_check():
    return {
        "status": "ok",
        "service": "DEX Sniper Pro API",
        "message": "API working!"
    }

# Paper trading endpoints (existing)
@api_router.post("/paper/toggle")
async def toggle_paper(request: dict):
    return {"status": "ok", "paper_enabled": True, "debug": True}

@api_router.get("/metrics/paper")
async def metrics_paper():
    return {"status": "ok", "metrics": {"debug": True}}

@api_router.post("/paper/thought-log/test")
async def paper_thought_log_test():
    return {"status": "ok", "debug": True}

# Trading endpoints (existing)
@api_router.get("/chains")
async def get_supported_chains():
    return {
        "status": "ok", 
        "chains": [
            {"name": "ethereum", "chain_id": 1},
            {"name": "bsc", "chain_id": 56},
            {"name": "base", "chain_id": 8453}
        ]
    }

@api_router.post("/balance")
async def get_balance(request: dict):
    return {"status": "ok", "balance": {"debug": True}}

@api_router.post("/quotes")
async def get_quote(request: dict):
    return {"status": "ok", "quote": {"debug": True}}

# WebSocket router
ws_router = APIRouter()

@ws_router.websocket("/ws/paper")
async def ws_paper(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({
        "type": "hello",
        "payload": {"channel": "paper", "debug": True}
    })
    try:
        while True:
            await websocket.receive_text()
    except:
        pass

@ws_router.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({
        "type": "hello", 
        "payload": {"channel": "metrics", "debug": True}
    })
    try:
        while True:
            await websocket.receive_text()
    except:
        pass

# Create the FastAPI app
app = FastAPI(
    title="DEX Sniper Pro Debug",
    description="Debug version with all expected endpoints",
    version="1.0.0-debug"
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(health_router, tags=["health"])
app.include_router(api_router, tags=["api"])
app.include_router(ws_router, tags=["websockets"])

print("✅ All routers registered successfully!")
print("Available routes:")
for route in app.routes:
    if hasattr(route, 'methods'):
        print(f"  {route.methods} {route.path}")

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting debug server with all expected endpoints...")
    uvicorn.run(
        "debug_main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )