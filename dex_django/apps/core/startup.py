# APP: backend
# FILE: backend/app/core/startup.py
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any

from backend.app.core.database import init_db
from backend.app.core.data_seeder import copy_trading_seeder
from backend.app.copy_trading.copy_trading_coordinator import copy_trading_coordinator

logger = logging.getLogger("core.startup")


async def initialize_application() -> Dict[str, Any]:
    """
    Initialize the DEX Sniper Pro application with copy trading capabilities.
    This runs on application startup to ensure all systems are ready.
    """
    
    logger.info("Initializing DEX Sniper Pro application...")
    
    results = {
        "database_init": None,
        "seeding_check": None,
        "copy_trading_ready": False
    }
    
    try:
        # 1. Initialize database
        logger.info("Initializing database...")
        await init_db()
        results["database_init"] = "success"
        logger.info("Database initialized successfully")
        
        # 2. Check seeding status
        logger.info("Checking copy trading seeding status...")
        seeding_status = await copy_trading_seeder.get_seeding_status()
        results["seeding_check"] = seeding_status
        
        # 3. Auto-seed if no data exists
        if seeding_status.get("seeding_needed", False):
            logger.info("No copy trading data found, auto-seeding with sample traders...")
            seed_result = await copy_trading_seeder.seed_copy_trading_data(force_reseed=False)
            results["auto_seeding"] = seed_result
            
            if seed_result["status"] == "success":
                logger.info(f"Auto-seeded {seed_result['seeded_count']} sample traders")
            else:
                logger.warning(f"Auto-seeding failed: {seed_result.get('error', 'Unknown error')}")
        
        # 4. Prepare copy trading system (don't start automatically)
        logger.info("Copy trading system ready for manual start")
        results["copy_trading_ready"] = True
        
        logger.info("DEX Sniper Pro initialization completed successfully")
        
        return {
            "status": "success",
            "message": "Application initialized successfully",
            "details": results,
            "next_steps": [
                "Visit the Copy Trading tab to review seeded traders",
                "Replace example wallet addresses with real successful traders",
                "Start copy trading monitoring when ready",
                "Configure copy settings based on your risk tolerance"
            ]
        }
        
    except Exception as e:
        logger.error(f"Application initialization failed: {e}")
        results["error"] = str(e)
        
        return {
            "status": "error",
            "message": f"Initialization failed: {str(e)}",
            "details": results
        }


async def startup_copy_trading_system() -> Dict[str, Any]:
    """
    Start the copy trading system if configured properly.
    This is separate from initialization to allow manual control.
    """
    
    logger.info("Starting copy trading system...")
    
    try:
        # Check if we have any active traders
        status = await copy_trading_coordinator.get_system_status()
        active_traders = status.get("wallets", {}).get("status_counts", {}).get("active", 0)
        
        if active_traders == 0:
            return {
                "status": "warning",
                "message": "No active traders to monitor",
                "recommendation": "Add traders in the Copy Trading tab first"
            }
        
        # Start the coordinator
        result = await copy_trading_coordinator.start()
        
        logger.info(f"Copy trading system started with {active_traders} active traders")
        
        return {
            "status": "success",
            "message": f"Copy trading started monitoring {active_traders} traders",
            "details": result
        }
        
    except Exception as e:
        logger.error(f"Failed to start copy trading system: {e}")
        return {
            "status": "error",
            "message": f"Copy trading start failed: {str(e)}"
        }


# FastAPI startup event handler
async def on_startup():
    """FastAPI startup event handler."""
    result = await initialize_application()
    
    if result["status"] == "success":
        logger.info("DEX Sniper Pro ready for copy trading!")
        print("\n" + "="*60)
        print("🚀 DEX Sniper Pro - Copy Trading System Ready!")
        print("="*60)
        print("✅ Database initialized")
        print("✅ Copy trading models ready")
        print("✅ Sample traders seeded (replace with real addresses)")
        print("📝 Next: Visit Copy Trading tab to configure traders")
        print("🎯 Replace example addresses with real successful traders")
        print("="*60 + "\n")
    else:
        logger.error("Startup failed!")
        print(f"\n❌ Startup Error: {result['message']}\n")


# Manual database reset (use with caution)
async def reset_and_reseed():
    """Reset and reseed copy trading data. Use for development only."""
    
    logger.warning("Resetting and reseeding copy trading data...")
    
    try:
        # Stop copy trading first
        await copy_trading_coordinator.stop()
        
        # Re-initialize database (this would recreate tables)
        await init_db()
        
        # Force reseed
        result = await copy_trading_seeder.seed_copy_trading_data(force_reseed=True)
        
        logger.info(f"Reset and reseed completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Reset and reseed failed: {e}")
        raise


if __name__ == "__main__":
    # For manual testing
    asyncio.run(initialize_application())