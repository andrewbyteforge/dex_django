# from __future__ import annotations

# import asyncio
# import logging
# import os
# import sys
# from contextlib import asynccontextmanager
# from pathlib import Path

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from dotenv import load_dotenv

# # Fix the path setup for Django
# project_root = Path(__file__).parent.parent
# sys.path.insert(0, str(project_root))

# # Set Django settings module with correct path
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')

# # Initialize Django
# try:
#     import django
#     django.setup()
#     logger = logging.getLogger(__name__)
#     logger.info("Django initialized successfully")
# except Exception as e:
#     print(f"Django initialization failed: {e}")
#     # Continue without Django for now
#     logger = logging.getLogger(__name__)

# # Load environment variables
# load_dotenv()


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """FastAPI lifespan context manager."""
#     logger.info("Starting DEX Sniper Pro...")
    
#     try:
#         # Try to initialize components, but don't fail if they're not available
#         try:
#             from apps.core.runtime_state import runtime_state
#             logger.info("Runtime state initialized")
#         except ImportError as e:
#             logger.warning(f"Runtime state not available: {e}")
        
#         try:
#             from apps.chains.providers import web3_manager
#             await web3_manager.initialize()
#             logger.info("Web3 providers initialized")
#         except ImportError as e:
#             logger.warning(f"Web3 providers not available: {e}")
        
#         try:
#             from apps.dex.routers import dex_manager
#             await dex_manager.initialize()
#             logger.info("DEX routers initialized")
#         except ImportError as e:
#             logger.warning(f"DEX routers not available: {e}")
        
#         logger.info("DEX Sniper Pro started successfully")
        
#         yield
        
#     except Exception as e:
#         logger.error("Failed to start DEX Sniper Pro: %s", e)
#         yield
#     finally:
#         logger.info("Shutting down DEX Sniper Pro...")


# def create_app() -> FastAPI:
#     """Create and configure FastAPI application."""
    
#     app = FastAPI(
#         title="DEX Sniper Pro",
#         description="High-frequency DEX trading bot with AI-powered discovery",
#         version="1.0.0",
#         lifespan=lifespan,
#         docs_url="/docs",
#         redoc_url="/redoc",
#     )
    
#     # CORS middleware
#     app.add_middleware(
#         CORSMiddleware,
#         allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
#         allow_credentials=True,
#         allow_methods=["*"],
#         allow_headers=["*"],
#     )
    
#     # Import routers with error handling
#     routers_registered = []
    
#     # Health endpoints (always available)
#     try:
#         from apps.api import health
#         app.include_router(health.router, tags=["health"])
#         routers_registered.append("health")
#     except ImportError:
#         # Fallback health endpoint
#         from fastapi import APIRouter
#         health_router = APIRouter()
        
#         @health_router.get("/health")
#         async def fallback_health():
#             return {"status": "ok", "service": "DEX Sniper Pro", "mode": "fallback"}
        
#         app.include_router(health_router, tags=["health"])
#         routers_registered.append("health (fallback)")
    
#     # Try to register other routers
#     router_modules = [
#         ("apps.api.bot", "bot", "bot"),
#         ("apps.api.providers", "providers", "providers"),
#         ("apps.api.tokens", "tokens", "tokens"),
#         ("apps.api.trades", "trades", "trades"),
#         ("apps.api.trading", "trading", "trading"),
#         ("apps.api.paper", "paper", "paper"),
#         ("apps.ws.paper", "paper_ws", "websockets"),
#         ("apps.ws.metrics", "metrics_ws", "websockets"),
#     ]
    
#     for module_path, attr_name, tag in router_modules:
#         try:
#             module = __import__(module_path, fromlist=[attr_name])
#             router = getattr(module, 'router')
#             app.include_router(router, tags=[tag])
#             routers_registered.append(tag)
#         except (ImportError, AttributeError) as e:
#             logger.warning(f"Could not register {tag} router: {e}")
    
#     # Add debug endpoint to show registered routers
#     @app.get("/debug/info")
#     async def debug_info():
#         return {
#             "service": "DEX Sniper Pro",
#             "routers_registered": routers_registered,
#             "django_available": 'django' in sys.modules,
#             "total_routes": len(app.routes)
#         }
    
#     logger.info(f"Registered routers: {', '.join(routers_registered)}")
    
#     return app


# # Create app instance
# app = create_app()


# if __name__ == "__main__":
#     import uvicorn
    
#     uvicorn.run(
#         "dex_django.main:app",
#         host="127.0.0.1",
#         port=8000,
#         reload=True,
#         log_level="info",
#     )