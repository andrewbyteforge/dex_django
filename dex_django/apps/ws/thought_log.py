from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


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
                "channel": "thought_log",
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
            elif message_type == "get_history":
                # Could implement frame history replay here
                await self._send_to_client(websocket, {
                    "type": "history_unavailable",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": "Frame history not implemented yet"
                })
                
        except json.JSONDecodeError:
            logger.warning("Invalid JSON received from thought log WebSocket")
    
    async def emit_discovery(
        self,
        opportunity: OpportunitySignal,
        notes: Optional[str] = None
    ) -> str:
        """Emit discovery thought log frame."""
        frame = ThoughtLogFrame(
            frame_id=self._next_frame_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            log_type=ThoughtLogType.DISCOVERY,
            opportunity=opportunity,
            notes=notes
        )
        await self._broadcast_frame(frame)
        return frame.frame_id
    
    async def emit_risk_assessment(
        self,
        frame_id: str,
        risk_assessment: RiskAssessment,
        notes: Optional[str] = None
    ) -> None:
        """Emit risk assessment thought log frame."""
        frame = ThoughtLogFrame(
            frame_id=frame_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            log_type=ThoughtLogType.RISK_ASSESSMENT,
            risk_assessment=risk_assessment,
            notes=notes
        )
        await self._broadcast_frame(frame)
    
    async def emit_pricing_analysis(
        self,
        frame_id: str,
        pricing: PricingAnalysis,
        notes: Optional[str] = None
    ) -> None:
        """Emit pricing analysis thought log frame."""
        frame = ThoughtLogFrame(
            frame_id=frame_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            log_type=ThoughtLogType.PRICING_ANALYSIS,
            pricing=pricing,
            notes=notes
        )
        await self._broadcast_frame(frame)
    
    async def emit_decision(
        self,
        frame_id: str,
        decision: TradingDecision,
        notes: Optional[str] = None
    ) -> None:
        """Emit trading decision thought log frame."""
        frame = ThoughtLogFrame(
            frame_id=frame_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            log_type=ThoughtLogType.DECISION,
            decision=decision,
            notes=notes
        )
        await self._broadcast_frame(frame)
    
    async def emit_execution(
        self,
        frame_id: str,
        execution: ExecutionResult,
        notes: Optional[str] = None
    ) -> None:
        """Emit execution result thought log frame."""
        frame = ThoughtLogFrame(
            frame_id=frame_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            log_type=ThoughtLogType.EXECUTION,
            execution=execution,
            notes=notes
        )
        await self._broadcast_frame(frame)
    
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
        # Convert dataclasses to dicts, handling None values
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