# APP: backend
# FILE: backend/app/core/startup.py
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any

from dex_django.core.database import init_db
from dex_django.copy_trading.copy_trading_coordinator import copy_trading_coordinator

logger = logging.getLogger("core.startup")


async def initialize_application() -> Dict[str, Any]:
    """
    Initialize the DEX Sniper Pro application with copy trading capabilities.
    This runs on application startup to ensure all systems are ready.
    """
    
    logger.info("Initializing DEX Sniper Pro application...")
    
    results = {
        "database_init": None,
        "copy_trading_ready": False
    }
    
    try:
        # 1. Initialize database
        logger.info("Initializing database...")
        await init_db()
        results["database_init"] = "success"
        logger.info("Database initialized successfully")
        
        # 2. Initialize copy trading coordinator (without starting)
        logger.info("Initializing copy trading coordinator...")
        await copy_trading_coordinator.initialize()
        results["copy_trading_ready"] = True
        logger.info("Copy trading coordinator initialized")
        
        # 3. Set final status
        results["status"] = "success"
        results["message"] = "Application initialized successfully"
        
        logger.info("DEX Sniper Pro initialization complete")
        return results
        
    except Exception as e:
        logger.error(f"Application initialization failed: {e}")
        results["status"] = "error"
        results["message"] = str(e)
        return results


async def startup_handler() -> None:
    """FastAPI startup event handler."""
    result = await initialize_application()
    
    if result["status"] == "success":
        logger.info("DEX Sniper Pro ready for copy trading!")
        print("\n" + "="*60)
        print("🚀 DEX Sniper Pro - Copy Trading System Ready!")
        print("="*60)
        print("✅ Database initialized")
        print("✅ Copy trading models ready")
        print("📝 Next: Add traders via the Copy Trading tab")
        print("🎯 Monitor real trader wallets for opportunities")
        print("="*60 + "\n")
    else:
        logger.error("Startup failed!")
        print(f"\n❌ Startup Error: {result['message']}\n")


if __name__ == "__main__":
    # For manual testing
    asyncio.run(initialize_application())