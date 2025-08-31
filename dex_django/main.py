from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our modules
from backend.app.core.config import settings
from backend.app.core.database import init_db
from backend.app.api import health, trading, discovery
from backend.app.ws import paper_ws, metrics_ws

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager."""
    logger.info("Starting DEX Sniper Pro...")
    
    # Initialize database
    await init_db()
    
    # Initialize blockchain providers
    from backend.app.chains.providers import web3_manager
    await web3_manager.initialize()
    
    # Initialize DEX routers
    from backend.app.dex.routers import dex_manager
    await dex_manager.initialize()
    
    # Initialize discovery engine
    from backend.app.discovery.engine import discovery_engine
    await discovery_engine.start()
    
    logger.info("DEX Sniper Pro started successfully")
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down DEX Sniper Pro...")
    await discovery_engine.stop()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title="DEX Sniper Pro",
        description="High-frequency DEX trading bot with AI-powered discovery",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Health endpoint
    app.include_router(health.router, tags=["health"])
    
    # API v1 routes
    app.include_router(trading.router, prefix="/api/v1", tags=["trading"])
    app.include_router(discovery.router, prefix="/api/v1", tags=["discovery"])
    
    # WebSocket routes
    app.include_router(paper_ws.router, tags=["websockets"])
    app.include_router(metrics_ws.router, tags=["websockets"])
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "dex_django.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )