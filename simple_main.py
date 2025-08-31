from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print(f"Project root: {project_root}")
print(f"Working directory: {os.getcwd()}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AI Thought Log Data Models
class ThoughtLogType(Enum):
    """Types of AI thought log messages."""
    DISCOVERY = "discovery"
    RISK_ASSESSMENT = "risk_assessment"
    PRICING_ANALYSIS = "pricing_analysis"
    DECISION = "decision"
    EXECUTION = "execution"
    POST_TRADE = "post_trade"


@dataclass
class OpportunitySignal:
    """Discovery opportunity signal."""
    pair_address: str
    chain: str
    dex: str
    symbol: str
    token_in: str
    token_out: str
    liquidity_usd: float
    volume_24h: Optional[float] = None
    trend_score: Optional[float] = None
    mempool_activity: Optional[int] = None


@dataclass
class RiskAssessment:
    """Risk gate results."""
    liquidity_check: str  # "pass", "fail", "warning"
    owner_controls: str
    buy_tax_pct: Optional[float] = None
    sell_tax_pct: Optional[float] = None
    blacklist_check: str = "pass"
    contract_verified: Optional[bool] = None
    honeypot_risk: str = "low"
    rug_risk_score: Optional[float] = None


@dataclass
class PricingAnalysis:
    """Pricing and slippage analysis."""
    quote_in: str
    expected_out: str
    expected_slippage_bps: int
    gas_estimate_gwei: Optional[float] = None
    price_impact_bps: Optional[int] = None
    router_path: Optional[List[str]] = None
    best_dex: Optional[str] = None


@dataclass
class TradingDecision:
    """Final AI decision."""
    action: str  # "paper_buy", "paper_sell", "skip", "wait"
    confidence: float  # 0.0 to 1.0
    rationale: str
    position_size_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None


@dataclass
class ExecutionResult:
    """Trade execution result."""
    tx_hash: Optional[str] = None
    status: str = "pending"  # "pending", "confirmed", "failed", "simulated"
    realized_slippage_bps: Optional[int] = None
    gas_used: Optional[int] = None
    gas_price_gwei: Optional[float] = None
    execution_time_ms: Optional[int] = None


@dataclass
class ThoughtLogFrame:
    """Complete AI thought log frame."""
    frame_id: str
    timestamp: str
    log_type: ThoughtLogType
    opportunity: Optional[OpportunitySignal] = None
    risk_assessment: Optional[RiskAssessment] = None
    pricing: Optional[PricingAnalysis] = None
    decision: Optional[TradingDecision] = None
    execution: Optional[ExecutionResult] = None
    notes: Optional[str] = None


# AI Thought Log Streamer
class ThoughtLogStreamer:
    """AI Thought Log WebSocket streaming manager."""
    
    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._frame_counter = 0
        self._session_start = datetime.now(timezone.utc)
        
    async def connect(self, websocket: WebSocket) -> None:
        """Accept new WebSocket connection."""
        await websocket.accept()
        self._connections.add(websocket)
        logger.info("New thought log WebSocket connection. Total: %d", len(self._connections))
        
        # Send welcome message
        await self._send_to_client(websocket, {
            "type": "hello",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "channel": "paper",
                "session_start": self._session_start.isoformat(),
                "frame_counter": self._frame_counter
            }
        })
    
    async def disconnect(self, websocket: WebSocket) -> None:
        """Handle WebSocket disconnection."""
        self._connections.discard(websocket)
        logger.info("Thought log WebSocket disconnected. Total: %d", len(self._connections))
    
    async def handle_message(self, websocket: WebSocket, data: str) -> None:
        """Handle incoming WebSocket messages."""
        try:
            message = json.loads(data)
            message_type = message.get("type", "")
            
            if message_type == "ping":
                await self._send_to_client(websocket, {
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
        except json.JSONDecodeError:
            logger.warning("Invalid JSON received from thought log WebSocket")
    
    async def emit_complete_thought(
        self,
        opportunity: OpportunitySignal,
        risk_assessment: RiskAssessment,
        pricing: PricingAnalysis,
        decision: TradingDecision,
        execution: Optional[ExecutionResult] = None,
        notes: Optional[str] = None
    ) -> str:
        """Emit complete thought process in one frame."""
        frame = ThoughtLogFrame(
            frame_id=self._next_frame_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            log_type=ThoughtLogType.DECISION,
            opportunity=opportunity,
            risk_assessment=risk_assessment,
            pricing=pricing,
            decision=decision,
            execution=execution,
            notes=notes
        )
        await self._broadcast_frame(frame)
        return frame.frame_id
    
    def _next_frame_id(self) -> str:
        """Generate next frame ID."""
        self._frame_counter += 1
        return f"frame_{self._frame_counter:06d}"
    
    async def _broadcast_frame(self, frame: ThoughtLogFrame) -> None:
        """Broadcast thought log frame to all connected clients."""
        if not self._connections:
            return
        
        message = {
            "type": "thought_log",
            "timestamp": frame.timestamp,
            "payload": self._serialize_frame(frame)
        }
        
        await self._broadcast_message(message)
    
    def _serialize_frame(self, frame: ThoughtLogFrame) -> Dict[str, Any]:
        """Serialize thought log frame to JSON-compatible dict."""
        result = {
            "frame_id": frame.frame_id,
            "timestamp": frame.timestamp,
            "log_type": frame.log_type.value,
        }
        
        if frame.opportunity:
            result["opportunity"] = asdict(frame.opportunity)
        if frame.risk_assessment:
            result["risk_assessment"] = asdict(frame.risk_assessment)
        if frame.pricing:
            result["pricing"] = asdict(frame.pricing)
        if frame.decision:
            result["decision"] = asdict(frame.decision)
        if frame.execution:
            result["execution"] = asdict(frame.execution)
        if frame.notes:
            result["notes"] = frame.notes
            
        return result
    
    async def _broadcast_message(self, message: Dict[str, Any]) -> None:
        """Broadcast message to all connected clients."""
        if not self._connections:
            return
        
        # Copy set to avoid modification during iteration
        connections = self._connections.copy()
        disconnected = set()
        
        for websocket in connections:
            try:
                await self._send_to_client(websocket, message)
            except Exception as e:
                logger.warning("Failed to send thought log to client: %s", e)
                disconnected.add(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected:
            self._connections.discard(websocket)
    
    async def _send_to_client(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """Send message to specific client."""
        await websocket.send_text(json.dumps(message))


# Global thought log streamer instance
thought_log_streamer = ThoughtLogStreamer()

# Create FastAPI app
app = FastAPI(
    title="DEX Sniper Pro",
    description="DEX trading bot API with AI Thought Log streaming",
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

# WebSocket endpoint for AI Thought Log + Paper Trading
@app.websocket("/ws/paper")
async def websocket_paper(websocket: WebSocket):
    """WebSocket endpoint for paper trading real-time updates and AI thought log."""
    print(f"🔌 New WebSocket connection attempt")  # Debug print
    
    try:
        await thought_log_streamer.connect(websocket)
        print(f"🔌 WebSocket connected successfully. Total connections: {len(thought_log_streamer._connections)}")  # Debug print
        
        while True:
            data = await websocket.receive_text()
            print(f"📨 WebSocket received: {data}")  # Debug print
            await thought_log_streamer.handle_message(websocket, data)
            
    except WebSocketDisconnect:
        print(f"🔌 WebSocket disconnected")  # Debug print
        await thought_log_streamer.disconnect(websocket)
    except Exception as e:
        print(f"❌ WebSocket error: {e}")  # Debug print
        logger.error("WebSocket error in /ws/paper: %s", e)
        await thought_log_streamer.disconnect(websocket)

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

# NEW: AI Thought Log test endpoint
@api_router.post("/paper/thought-log/test")
async def emit_test_thought_log():
    """Emit a test AI thought log frame for UI development."""
    try:
        print("🧠 Test thought log endpoint called")  # Debug print
        
        # Create sample thought log frame
        opportunity = OpportunitySignal(
            pair_address="0xDEADBEEF12345678",
            chain="bsc",
            dex="pancake_v2",
            symbol="TEST/BNB",
            token_in="0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
            token_out="0xDEADBEEF12345678",
            liquidity_usd=42000.0,
            volume_24h=156000.0,
            trend_score=0.68,
            mempool_activity=8
        )
        
        risk_assessment = RiskAssessment(
            liquidity_check="pass",
            owner_controls="pass",
            buy_tax_pct=0.03,
            sell_tax_pct=0.03,
            blacklist_check="pass",
            contract_verified=True,
            honeypot_risk="low",
            rug_risk_score=0.12
        )
        
        pricing = PricingAnalysis(
            quote_in="0.25 BNB",
            expected_out="12345 TEST",
            expected_slippage_bps=75,
            gas_estimate_gwei=5.2,
            price_impact_bps=45,
            router_path=["WBNB", "TEST"],
            best_dex="pancake_v2"
        )
        
        decision = TradingDecision(
            action="paper_buy",
            confidence=0.82,
            rationale="Strong trend score (0.68), low taxes (3%), verified contract, good liquidity ($42K)",
            position_size_pct=2.5,
            stop_loss_pct=15.0,
            take_profit_pct=25.0
        )
        
        print(f"🧠 Emitting thought log to {len(thought_log_streamer._connections)} connections")  # Debug print
        
        # Emit complete thought log
        frame_id = await thought_log_streamer.emit_complete_thought(
            opportunity=opportunity,
            risk_assessment=risk_assessment,
            pricing=pricing,
            decision=decision,
            notes="Test thought log generated for UI development and WebSocket testing"
        )
        
        print(f"🧠 Thought log emitted successfully with frame_id: {frame_id}")  # Debug print
        
        return {
            "status": "ok",
            "frame_id": frame_id,
            "message": "Test thought log emitted successfully",
            "connections": len(thought_log_streamer._connections)
        }
        
    except Exception as e:
        print(f"❌ Failed to emit test thought log: {e}")  # Debug print
        logger.error("Failed to emit test thought log: %s", e)
        return {"status": "error", "message": str(e)}

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
        "service": "DEX Sniper Pro Simple with AI Thought Log",
        "total_routes": len(app.routes),
        "working_dir": os.getcwd(),
        "python_path": sys.path[:3],
        "thought_log_connections": len(thought_log_streamer._connections),
        "thought_log_frame_counter": thought_log_streamer._frame_counter,
        "endpoints": [
            "POST /api/v1/paper/thought-log/test - Test AI thought log",
            "WS /ws/paper - WebSocket for thought log streaming",
            "GET /debug/info - This debug endpoint"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting simple DEX Sniper Pro server with AI Thought Log streaming...")
    uvicorn.run(
        "simple_main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )