import asyncio
from apps.trading.engine import trading_engine, ExecutionMode

async def test_paper_mode():
    print("Testing paper trading mode...")
    
    # Start in paper mode (no real money)
    success = await trading_engine.start_trading(mode=ExecutionMode.PAPER)
    
    if success:
        print("✅ Trading engine started in paper mode")
        status = trading_engine.get_status()
        print(f"Status: {status}")
        
        # Let it run for 30 seconds
        await asyncio.sleep(30)
        
        # Stop the engine
        await trading_engine.stop_trading()
        print("✅ Trading engine stopped")
    else:
        print("❌ Failed to start trading engine")

# Run the test
if __name__ == "__main__":
    asyncio.run(test_paper_mode())