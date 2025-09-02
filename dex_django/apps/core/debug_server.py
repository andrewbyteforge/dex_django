# APP: dex_django
# FILE: dex_django/apps/core/debug_server.py
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dex_django.apps.api.debug_routers import health_router, api_router, cleanup_disconnected_clients
from dex_django.apps.core.debug_state import debug_state
from dex_django.apps.core.django_setup import setup_django, get_django_status
from dex_django.apps.ws.debug_websockets import router as ws_router, periodic_metrics_broadcast

logger = logging.getLogger("core.debug_server")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.
    
    Handles application startup and shutdown tasks including:
    - Django ORM initialization
    - Module availability detection
    - Background task scheduling
    - Resource cleanup
    """
    logger.info("Starting DEX Sniper Pro debug server...")
    
    # Startup tasks
    try:
        # Initialize Django ORM
        django_ready = setup_django()
        debug_state.set_module_availability(django=django_ready)
        
        if django_ready:
            logger.info("Django ORM initialized successfully")
        else:
            logger.warning("Django ORM initialization failed - some features may be unavailable")
        
        # Try to import and register optional modules
        await _detect_and_register_modules()
        
        # Start background tasks
        background_tasks = await _start_background_tasks()
        
        logger.info("Debug server startup completed successfully")
        
        # Server is now ready to serve requests
        yield
        
    except Exception as e:
        logger.error(f"Error during server startup: {e}")
        raise
    
    # Shutdown tasks
    finally:
        logger.info("Shutting down DEX Sniper Pro debug server...")
        
        # Cancel background tasks
        if 'background_tasks' in locals():
            for task in background_tasks:
                if not task.cancelled():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
        
        # Cleanup debug state
        debug_state.shutdown()
        
        logger.info("Debug server shutdown completed")


async def _detect_and_register_modules() -> None:
    """
    Detect and register optional modules.
    
    Attempts to import copy_mock and complete copy trading modules,
    updating debug state with their availability.
    """
    copy_mock_available = False
    copy_trading_ready = False
    
    # Try to import copy_mock module
    try:
        from apps.api import copy_mock
        copy_mock_available = True
        logger.info("copy_mock module detected and available")
    except ImportError as e:
        logger.info(f"copy_mock module not available: {e}")
    except Exception as e:
        logger.warning(f"Error importing copy_mock module: {e}")
    
    # Try to import complete copy trading system
    try:
        from dex_django.apps.strategy import copy_trading_complete
        copy_trading_ready = True
        logger.info("Complete copy trading system detected and available")
    except ImportError as e:
        logger.info(f"Complete copy trading system not available: {e}")
    except Exception as e:
        logger.warning(f"Error importing copy trading system: {e}")
    
    # Update debug state with module availability
    debug_state.set_module_availability(
        copy_mock=copy_mock_available,
        copy_trading_system=copy_trading_ready,
        django=debug_state.django_initialized
    )


async def _start_background_tasks() -> list:
    """
    Start background tasks for the debug server.
    
    Returns:
        List of asyncio tasks that were started.
    """
    tasks = []
    
    # Periodic WebSocket client cleanup (every 5 minutes)
    cleanup_task = asyncio.create_task(_periodic_cleanup_task())
    tasks.append(cleanup_task)
    
    # Periodic metrics broadcasting (every 30 seconds)
    metrics_task = asyncio.create_task(_periodic_metrics_task())
    tasks.append(metrics_task)
    
    logger.info(f"Started {len(tasks)} background tasks")
    return tasks


async def _periodic_cleanup_task() -> None:
    """Background task to periodically clean up disconnected WebSocket clients."""
    while True:
        try:
            await asyncio.sleep(300)  # 5 minutes
            await cleanup_disconnected_clients()
        except asyncio.CancelledError:
            logger.info("Cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying


async def _periodic_metrics_task() -> None:
    """Background task to periodically broadcast metrics to WebSocket clients."""
    while True:
        try:
            await asyncio.sleep(30)  # 30 seconds
            if debug_state.has_metrics_clients():
                await periodic_metrics_broadcast()
        except asyncio.CancelledError:
            logger.info("Metrics broadcast task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in metrics broadcast task: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying


def create_debug_app() -> FastAPI:
    """
    Create and configure the FastAPI debug application.
    
    Sets up the complete FastAPI application with:
    - CORS middleware for frontend communication
    - All API and WebSocket routers
    - Optional module routers (copy_mock, copy_trading)
    - Proper error handling and logging
    
    Returns:
        Configured FastAPI application instance.
    """
    # Create FastAPI application with lifespan management
    app = FastAPI(
        title="DEX Sniper Pro Debug Server",
        description="Development debug server with integrated copy trading system, live execution, and performance tracking",
        version="1.4.0-debug",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # Configure CORS middleware for frontend communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://127.0.0.1:5173",  # Alternative localhost
            "http://localhost:3000",  # Alternative React dev server
            "http://127.0.0.1:3000",
            "*"  # Allow all origins in development
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Register core routers
    app.include_router(health_router, tags=["health"])
    app.include_router(api_router, tags=["debug-api"])
    app.include_router(ws_router, tags=["websockets"])
    
    # Register optional routers after app creation
    _register_optional_routers(app)
    
    logger.info("FastAPI debug application created and configured")
    return app


def _register_optional_routers(app: FastAPI) -> None:
    """
    Register optional routers if their modules are available.
    
    Args:
        app: FastAPI application instance to register routers with.
    """
    routers_registered = 0
    
    # Register copy_mock router if available
    if debug_state.copy_mock_available:
        try:
            from apps.api import copy_mock
            app.include_router(copy_mock.router, tags=["copy-mock"])
            
            # Register discovery router if it exists
            if hasattr(copy_mock, 'discovery_router'):
                app.include_router(copy_mock.discovery_router, tags=["copy-mock-discovery"])
                routers_registered += 1
            
            routers_registered += 1
            logger.info("copy_mock routers registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to register copy_mock routers: {e}")
            debug_state.set_module_availability(copy_mock=False)
    
    # Register complete copy trading router if available
    if debug_state.copy_trading_system_ready:
        try:
            from dex_django.apps.strategy.copy_trading_complete import router as complete_copy_router
            app.include_router(complete_copy_router, tags=["copy-trading-complete"])
            routers_registered += 1
            logger.info("Complete copy trading router registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to register complete copy trading router: {e}")
            debug_state.set_module_availability(copy_trading_system=False)
    
    if routers_registered > 0:
        logger.info(f"Registered {routers_registered} optional routers")
    else:
        logger.info("No optional routers registered")


def get_app_info() -> dict:
    """
    Get comprehensive application information.
    
    Returns:
        Dictionary containing application status and configuration.
    """
    django_ready, django_status = get_django_status()
    
    return {
        "application": {
            "name": "DEX Sniper Pro Debug Server",
            "version": "1.4.0-debug",
            "mode": "development"
        },
        "system": debug_state.get_system_status(),
        "django": {
            "initialized": django_ready,
            "status": django_status
        },
        "routers": {
            "health": True,
            "debug_api": True,
            "websockets": True,
            "copy_mock": debug_state.copy_mock_available,
            "copy_trading_complete": debug_state.copy_trading_system_ready
        },
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
            "health": "/health",
            "websockets": ["/ws/paper", "/ws/metrics"]
        }
    }


# Root endpoint to provide application information
async def root_endpoint():
    """Root endpoint providing application information and available routes."""
    return {
        "message": "DEX Sniper Pro Debug Server",
        "status": "running",
        "info": get_app_info(),
        "quick_links": {
            "health_check": "/health",
            "api_docs": "/docs",
            "paper_trading_status": "/api/v1/paper/status",
            "live_opportunities": "/api/v1/opportunities/live",
            "copy_trading_status": "/api/v1/copy/status",
            "websocket_paper": "/ws/paper",
            "websocket_metrics": "/ws/metrics"
        }
    }


def configure_app_routes(app: FastAPI) -> None:
    """
    Configure additional application routes.
    
    Args:
        app: FastAPI application instance.
    """
    # Add root endpoint
    app.get("/")(root_endpoint)
    
    # Add application info endpoint
    @app.get("/info")
    async def app_info():
        return get_app_info()
    
    logger.info("Additional application routes configured")


# Factory function to create a fully configured debug application
def create_configured_debug_app() -> FastAPI:
    """
    Create a fully configured debug application.
    
    This is the main factory function that creates the complete
    debug server application with all features enabled.
    
    Returns:
        Fully configured FastAPI application ready to run.
    """
    app = create_debug_app()
    configure_app_routes(app)
    
    logger.info("Debug application fully configured and ready")
    return app