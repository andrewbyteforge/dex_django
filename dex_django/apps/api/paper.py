# APP: backend
# FILE: backend/app/api/paper.py
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.runtime_state import runtime_state

router = APIRouter(prefix="/api/v1", tags=["paper"])


class PaperToggleRequest(BaseModel):
    """Toggle Paper Trading mode."""
    enabled: bool = Field(..., description="Enable or disable Paper Trading.")


@router.post("/paper/toggle", summary="Enable/disable Paper Trading")
async def toggle_paper(req: PaperToggleRequest) -> Dict[str, Any]:
    """Toggle Paper Trading and broadcast a status frame on /ws/paper."""
    try:
        await runtime_state.set_paper_enabled(req.enabled)
        return {"status": "ok", "paper_enabled": await runtime_state.get_paper_enabled()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, str(exc)) from exc


@router.get("/metrics/paper", summary="Get Paper Trading metrics")
async def metrics_paper() -> Dict[str, Any]:
    """Return current Paper Trading session metrics snapshot."""
    try:
        metrics = await runtime_state.get_paper_metrics()
        return {"status": "ok", "metrics": metrics}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, str(exc)) from exc


@router.post("/paper/thought-log/test", summary="Emit a sample AI Thought Log")
async def paper_thought_log_test() -> Dict[str, Any]:
    """Emit a tiny test 'thought_log' frame over /ws/paper (for UI wiring)."""
    try:
        await runtime_state.emit_thought_log({
            "opportunity": {"pair": "0xDEADBEEF", "chain": "bsc", "dex": "pancake_v2", "symbol": "TEST"},
            "discovery_signals": {"liquidity_usd": 42000, "trend_score": 0.68},
            "risk_gates": {"owner_controls": "pass", "buy_tax": 0.03, "sell_tax": 0.03, "blacklist_check": "pass"},
            "pricing": {"quote_in": "0.25 BNB", "expected_out": "12345 TKN", "expected_slippage_bps": 75},
            "decision": {"action": "paper_buy", "rationale": "trend>0.6, taxes<=3%"},
        })
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, str(exc)) from exc
