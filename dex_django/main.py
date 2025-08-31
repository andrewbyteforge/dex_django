# APP: dex_django
# FILE: dex_django/main.py
from __future__ import annotations

# Ensure project root (which contains "backend/") is on sys.path
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI

# Now these imports work because backend is on sys.path
from backend.app.api import paper as paper_api
from backend.app.ws import paper as paper_ws


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="DEX Sniper Pro")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Mount routers
    app.include_router(paper_api.router)
    app.add_api_websocket_route("/ws/paper", paper_ws.ws_paper)

    return app


app = create_app()
