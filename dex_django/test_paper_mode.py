import asyncio
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')
django.setup()

from apps.trading.engine import trading_engine, ExecutionMode

async def test_paper_mode():
    print("Testing paper trading mode...")
    
    # Start in paper mode (no real money)
    success = await trading_engine.start_trading(mode=ExecutionMode.PAPER)
    
    if success:
        print("✅ Trading engine started in paper mode")
        status = trading_engine.get_status()
        print(f"Status: {status}")
        
        # Let it run for 10 seconds to see activity
        print("Running for 10 seconds...")
        await asyncio.sleep(10)
        
        # Check status again
        status = trading_engine.get_status()
        print(f"Final status: {status}")
        
        # Stop the engine
        await trading_engine.stop_trading()
        print("✅ Trading engine stopped")
    else:
        print("❌ Failed to start trading engine")

if __name__ == "__main__":
    asyncio.run(test_paper_mode())