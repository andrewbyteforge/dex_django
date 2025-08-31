import asyncio
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')
django.setup()

from apps.trading.router_executor import router_executor

async def test_router_health():
    print("=== Router Connection Health Test ===")
    
    # Test 1: Router Configuration Check
    print("\n1. Checking router configurations...")
    if not router_executor.router_configs:
        await router_executor._load_router_configs()
    
    for router_key, config in router_executor.router_configs.items():
        print(f"   ✓ {router_key}: {config.name} ({config.chain})")
        print(f"     Router: {config.router_address}")
        print(f"     Factory: {config.factory_address}")
        print(f"     Supports ETH: {config.supports_eth}")
    
    # Test 2: RPC Endpoint Availability  
    print("\n2. Testing RPC endpoint connectivity...")
    
    rpc_endpoints = {
        "ethereum": os.getenv("ETH_RPC_URL", "https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY"),
        "bsc": os.getenv("BSC_RPC_URL", "https://bsc-dataseed1.binance.org/"),
        "base": os.getenv("BASE_RPC_URL", "https://mainnet.base.org/"),
        "polygon": os.getenv("POLYGON_RPC_URL", "https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY"),
    }
    
    for chain, rpc_url in rpc_endpoints.items():
        try:
            from web3 import Web3
            web3 = Web3(Web3.HTTPProvider(rpc_url))
            
            # Test connection
            if web3.is_connected():
                # Get latest block to verify RPC is working
                latest_block = web3.eth.block_number
                print(f"   ✓ {chain}: Connected (Block: {latest_block})")
                
                # Test gas price
                try:
                    gas_price = web3.eth.gas_price
                    gas_gwei = gas_price / 10**9
                    print(f"     Gas Price: {gas_gwei:.2f} Gwei")
                except Exception as e:
                    print(f"     Gas Price: Error ({e})")
                    
            else:
                print(f"   ❌ {chain}: Connection failed")
                
        except Exception as e:
            print(f"   ❌ {chain}: Error - {e}")
    
    # Test 3: Router Contract Validation
    print("\n3. Validating router contracts...")
    
    try:
        success = await router_executor.initialize()
        if success:
            print("   ✓ Router executor initialized successfully")
            
            # Test each connected chain's router
            for chain, web3 in router_executor.web3_connections.items():
                print(f"\n   Testing {chain} routers:")
                
                for router_key, config in router_executor.router_configs.items():
                    if config.chain == chain:
                        try:
                            # Create router contract instance
                            router = web3.eth.contract(
                                address=config.router_address,
                                abi=config.router_abi
                            )
                            
                            # Test a simple view function (factory address)
                            if hasattr(router.functions, 'factory'):
                                factory = router.functions.factory().call()
                                matches_config = factory.lower() == config.factory_address.lower()
                                status = "✓" if matches_config else "⚠"
                                print(f"     {status} {config.name}: Contract accessible")
                                if not matches_config:
                                    print(f"       Factory mismatch: {factory} vs {config.factory_address}")
                            else:
                                print(f"     ? {config.name}: No factory() function (might be V3)")
                                
                        except Exception as e:
                            print(f"     ❌ {config.name}: Contract error - {e}")
        else:
            print("   ❌ Router executor initialization failed")
            
    except Exception as e:
        print(f"   ❌ Router validation failed: {e}")
    
    # Test 4: Quote Simulation (No Real Trades)
    print("\n4. Testing quote simulation...")
    
    if router_executor.initialized and router_executor.web3_connections:
        # Test with a well-known pair (ETH/USDC) on each chain
        test_pairs = {
            "ethereum": {
                "token_in": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
                "token_out": "0xA0b86a33E6441E4c436a9b85C8db0d6e7c5a9Dbb",  # USDC
                "amount_in": 1000000000000000000  # 1 ETH in wei
            },
            "bsc": {
                "token_in": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB  
                "token_out": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",  # USDC
                "amount_in": 1000000000000000000  # 1 BNB in wei
            }
        }
        
        for chain, pair_data in test_pairs.items():
            if chain in router_executor.web3_connections:
                print(f"\n   Testing quote on {chain}:")
                web3 = router_executor.web3_connections[chain]
                
                # Find a compatible router for this chain
                router_config = None
                for config in router_executor.router_configs.values():
                    if config.chain == chain and "v2" in config.name.lower():
                        router_config = config
                        break
                
                if router_config:
                    try:
                        router = web3.eth.contract(
                            address=router_config.router_address,
                            abi=router_config.router_abi
                        )
                        
                        # Try to get amounts out
                        path = [pair_data["token_in"], pair_data["token_out"]]
                        amounts_out = router.functions.getAmountsOut(
                            pair_data["amount_in"], path
                        ).call()
                        
                        output_amount = amounts_out[-1] / 10**6  # Assuming USDC (6 decimals)
                        print(f"     ✓ Quote: 1 native token = ${output_amount:,.2f}")
                        
                    except Exception as e:
                        print(f"     ❌ Quote failed: {e}")
                else:
                    print(f"     ⚠ No compatible router found for {chain}")
    
    # Test Summary
    print("\n=== Test Summary ===")
    print(f"Router Configs: {len(router_executor.router_configs)} loaded")
    print(f"Web3 Connections: {len(router_executor.web3_connections)} active")
    print(f"Router Initialized: {router_executor.initialized}")
    
    if router_executor.web3_connections:
        print(f"Connected Chains: {list(router_executor.web3_connections.keys())}")
    else:
        print("⚠ No Web3 connections established")
        print("  To enable more connections:")
        print("  - Set ETH_RPC_URL with Alchemy/Infura API key")
        print("  - Set POLYGON_RPC_URL with Alchemy/Infura API key")

if __name__ == "__main__":
    asyncio.run(test_router_health())