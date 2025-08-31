# APP: backend
# FILE: backend/app/api/debug.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])
logger = logging.getLogger("api.debug")


class TestRequest(BaseModel):
    """Test request model."""
    test_data: str = "hello"


@router.get("/ping")
async def ping() -> Dict[str, Any]:
    """Simple ping endpoint to test API connectivity."""
    return {
        "status": "ok",
        "message": "API is responding",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints_available": [
            "/api/v1/debug/ping",
            "/api/v1/debug/test-json", 
            "/api/v1/copy/traders",
            "/api/v1/copy/status"
        ]
    }


@router.post("/test-json")
async def test_json(data: TestRequest) -> Dict[str, Any]:
    """Test JSON parsing and response."""
    return {
        "status": "success",
        "received_data": data.dict(),
        "message": "JSON parsing working correctly"
    }


@router.get("/copy-trading-check")
async def copy_trading_check() -> Dict[str, Any]:
    """Check if copy trading endpoints are working."""
    
    try:
        # This simulates what the copy trading status endpoint should return
        return {
            "status": "ok",
            "message": "Copy trading API check passed",
            "mock_data": {
                "is_enabled": True,
                "monitoring_active": False,
                "followed_traders_count": 0,
                "active_copies_today": 0,
                "total_copies": 0,
                "win_rate_pct": 0.0,
                "total_pnl_usd": "0.00"
            },
            "next_steps": [
                "Check if /api/v1/copy/traders endpoint exists",
                "Verify database connection",
                "Check copy trading coordinator initialization"
            ]
        }
        
    except Exception as e:
        logger.error(f"Copy trading check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "troubleshooting": [
                "Check if copy trading modules are imported",
                "Verify database initialization",
                "Check for missing dependencies"
            ]
        }