from __future__ import annotations

import os
import sys
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"Project root: {project_root}")
print(f"Python path: {sys.path[:3]}")

# Create a simple health router for testing
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

# Create paper router for testing
paper_router = APIRouter(prefix="/api/v1")

@paper_router.post("/paper/toggle")
async def toggle_paper(request: dict):
    return {"status": "ok", "paper_enabled": True, "debug": True}

@paper_router.get("/metrics/paper")
async def metrics_paper():
    return {"status": "ok", "metrics": {"debug": True}}

@paper_router.post("/paper/thought-log/test")
async def paper_thought_log_test():
    return {"status": "ok", "debug": True}

# Create trading router for testing
trading_router = APIRouter(prefix="/api/v1")

@trading_router.get("/chains")
async def get_supported_chains():
    return {
        "status": "ok", 
        "chains": [
            {"name": "ethereum", "chain_id": 1},
            {"name": "bsc", "chain_id": 56},
            {"name": "base", "chain_id": 8453}
        ]
    }

@trading_router.post("/balance")
async def get_balance(request: dict):
    return {"status": "ok", "balance": {"debug": True}}

@trading_router.post("/quotes")
async def get_quote(request: dict):
    return {"status": "ok", "quote": {"debug": True}}

# Create WebSocket router for testing
from fastapi import WebSocket
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
    description="Debug version to test routing",
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
app.include_router(paper_router, tags=["paper"])
app.include_router(trading_router, tags=["trading"])
app.include_router(ws_router, tags=["websockets"])

print("✅ All routers registered successfully!")
print("Available routes:")
for route in app.routes:
    if hasattr(route, 'methods'):
        print(f"  {route.methods} {route.path}")

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting debug server...")
    uvicorn.run(
        "debug_main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )