from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Add the project root to Python path for Django integration
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Initialize Django for ORM access
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')
import django
django.setup()

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager."""
    logger.info("Starting DEX Sniper Pro...")
    
    try:
        # Initialize blockchain providers
        from apps.chains.providers import web3_manager
        await web3_manager.initialize()
        
        # Initialize DEX routers
        from apps.dex.routers import dex_manager
        await dex_manager.initialize()
        
        logger.info("DEX Sniper Pro started successfully")
        
        yield
        
    except Exception as e:
        logger.error("Failed to start DEX Sniper Pro: %s", e)
        # Don't raise - let the app start anyway for testing
        yield
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down DEX Sniper Pro...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title="DEX Sniper Pro",
        description="High-frequency DEX trading bot with AI-powered discovery",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Import and register all routes
    from apps.api import health, trading
    from apps.api import paper  # Your existing paper trading endpoints
    from apps.ws import paper as paper_ws  # Your existing WebSocket handlers
    from apps.ws import metrics as metrics_ws
    
    # Health endpoints (no prefix)
    app.include_router(health.router, tags=["health"])
    
    # API v1 routes
    app.include_router(trading.router, prefix="/api/v1", tags=["trading"])
    app.include_router(paper.router, tags=["paper"])  # Remove prefix - it's in the router
    
    # WebSocket routes (no prefix)
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