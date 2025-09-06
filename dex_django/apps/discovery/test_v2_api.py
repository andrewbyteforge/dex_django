# APP: backend
# FILE: dex_django/apps/discovery/test_v2_api.py
"""
Test Etherscan V2 API across all chains with single API key.
"""

import asyncio
import logging
from transaction_analyzer import transaction_analyzer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_v2_api")


async def test_all_chains():
    """Test V2 API with all supported chains."""
    
    print("\n" + "=" * 60)
    print("🧪 TESTING ETHERSCAN V2 API - ALL CHAINS")
    print("Using single Etherscan API key for all chains")
    print("=" * 60)
    
    # Test routers for each chain
    test_addresses = {
        "ethereum": {
            "address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "name": "Uniswap V2 Router"
        },
        "bsc": {
            "address": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
            "name": "PancakeSwap V2 Router"
        },
        "base": {
            "address": "0x4752ba5DBc23f44D87826276BF6Fd6b1C372aD24",
            "name": "BaseSwap Router"
        },
        "polygon": {
            "address": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
            "name": "QuickSwap Router"
        }
    }
    
    results = {}
    
    for chain, router_info in test_addresses.items():
        print(f"\n🔍 Testing {chain.upper()}")
        print(f"   Router: {router_info['name']}")
        print(f"   Address: {router_info['address']}")
        
        try:
            # Test with 1 hour window
            result = await transaction_analyzer.find_traders_from_pair(
                pair_address=router_info['address'],
                chain=chain,
                hours_back=1,
                min_trades=1
            )
            
            if result.status.value == "success":
                if result.data and len(result.data) > 0:
                    print(f"   ✅ SUCCESS! Found {len(result.data)} traders")
                    results[chain] = {
                        "status": "working",
                        "traders_found": len(result.data)
                    }
                else:
                    print(f"   ✅ API working but no traders in last hour")
                    results[chain] = {
                        "status": "working",
                        "traders_found": 0
                    }
            else:
                print(f"   ❌ Failed: {result.message}")
                results[chain] = {
                    "status": "failed",
                    "error": result.message
                }
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            results[chain] = {
                "status": "error",
                "error": str(e)
            }
        
        # Small delay between chains
        await asyncio.sleep(1)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 V2 API TEST SUMMARY")
    print("=" * 60)
    
    working_chains = [c for c, r in results.items() if r.get("status") == "working"]
    failed_chains = [c for c, r in results.items() if r.get("status") in ["failed", "error"]]
    
    print(f"\n✅ Working chains: {working_chains}")
    print(f"❌ Failed chains: {failed_chains}")
    
    if working_chains == ["ethereum", "bsc", "base", "polygon"]:
        print("\n🎉 SUCCESS! V2 API is working for ALL chains with single key!")
    elif working_chains:
        print(f"\n⚠️ V2 API partially working. Only {len(working_chains)}/4 chains successful.")
    else:
        print("\n❌ V2 API not working. May need to check API key or endpoints.")
    
    # Show statistics
    stats = transaction_analyzer.get_statistics()
    print(f"\n📈 API Statistics:")
    print(f"   Total calls: {stats['api_calls_made']}")
    print(f"   Failed calls: {stats['api_calls_failed']}")
    print(f"   Success rate: {stats['success_rate']:.1f}%")
    
    return results


if __name__ == "__main__":
    asyncio.run(test_all_chains())