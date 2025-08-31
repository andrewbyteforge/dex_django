import asyncio
from apps.trading.router_executor import router_executor

async def test_router_connections():
    print("Testing router connections...")
    
    # Try to initialize (will fail without RPC keys, but shows what's missing)
    success = await router_executor.initialize()
    
    if success:
        print("✅ Router executor initialized")
        print(f"Connected chains: {list(router_executor.web3_connections.keys())}")
        print(f"Available routers: {list(router_executor.router_configs.keys())}")
    else:
        print("❌ Router initialization failed (expected without RPC keys)")
        print("Available router configs:", list(router_executor.router_configs.keys()))

if __name__ == "__main__":
    asyncio.run(test_router_connections())