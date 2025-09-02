# APP: backend
# FILE: debug_main.py
"""
DEX Sniper Pro Debug Server - Entry Point

Streamlined entry point for the debug development server.
All complex logic has been moved to dedicated modules for better maintainability.
"""
from __future__ import annotations

import logging
import os
import sys
import uvicorn

# System path setup - Add to path BEFORE importing app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("debug_main")


def install_missing_dependencies() -> None:
    """Install missing dependencies if needed."""
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        logger.info("Installing missing aiohttp dependency...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
        logger.info("aiohttp installed successfully")


def get_app():
    """
    Factory function for uvicorn import string.
    
    This function is called by uvicorn when using reload mode
    with the import string "debug_main:get_app".
    
    Returns:
        FastAPI application instance.
    """
    install_missing_dependencies()
    
    from dex_django.apps.core.debug_server import create_configured_debug_app
    return create_configured_debug_app()


def main() -> None:
    """
    Main entry point for the debug server.
    
    Creates and runs the FastAPI debug application with uvicorn.
    """
    logger.info("Starting DEX Sniper Pro Debug Server...")
    
    try:
        # Install missing dependencies
        install_missing_dependencies()
        
        # Server configuration
        host = os.getenv("DEBUG_HOST", "127.0.0.1")
        port = int(os.getenv("DEBUG_PORT", "8000"))
        reload = os.getenv("DEBUG_RELOAD", "true").lower() == "true"
        
        logger.info(f"Debug server configured:")
        logger.info(f"  Host: {host}")
        logger.info(f"  Port: {port}")
        logger.info(f"  Reload: {reload}")
        logger.info(f"  Docs URL: http://{host}:{port}/docs")
        logger.info(f"  Health Check: http://{host}:{port}/health")
        
        # Start the server with proper import string for reload mode
        if reload:
            # Use import string for reload mode
            uvicorn.run(
                "debug_main:get_app",
                host=host,
                port=port,
                reload=True,
                log_level="info",
                access_log=True
            )
        else:
            # Use app object for production mode
            from dex_django.apps.core.debug_server import create_configured_debug_app
            app = create_configured_debug_app()
            
            uvicorn.run(
                app,
                host=host,
                port=port,
                reload=False,
                log_level="info",
                access_log=True
            )
        
    except KeyboardInterrupt:
        logger.info("Debug server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start debug server: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()