# APP: backend
# FILE: dex_django/apps/discovery/test_active_pairs.py
"""
Test script to find traders using more active pairs and longer time windows.
"""

import asyncio
import logging
from transaction_analyzer import transaction_analyzer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_active_pairs")


async def test_active_ethereum_pairs():
    """Test with various active Ethereum pairs."""
    
    print("\n" + "=" * 60)
    print("🔍 TESTING ACTIVE ETHEREUM PAIRS")
    print("=" * 60)
    
    # More active pairs on Ethereum
    test_pairs = {
        # Uniswap V2 pairs (usually more transactions)
        "WETH/USDC V2": "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc",
        "WETH/USDT V2": "0x0d4a11d5EEaaC28EC3F61d100daF4d40471f1852",
        "WETH/DAI V2": "0xA478c2975Ab1Ea89e8196811F51A7B7Ade33eB11",
        
        # Popular meme/volatile pairs (lots of activity)
        "PEPE/WETH V2": "0xA43fe16908251ee70EF74718545e4FE6C5cCEc9f",
        "SHIB/WETH V2": "0x811beEd0119b4AfCE20D2583EB608C6F7AF1954f",
        
        # Uniswap V3 pairs (different fee tiers)
        "WETH/USDC V3 0.05%": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
        "WETH/USDC V3 0.3%": "0x8ad599c3A0ff1De082011EFDDc58f1908eb6e6D8",
    }
    
    results = {}
    
    for pair_name, pair_address in test_pairs.items():
        print(f"\n📊 Testing: {pair_name}")
        print(f"   Address: {pair_address}")
        
        # Try different time windows
        for hours in [24, 12, 6]:
            try:
                result = await transaction_analyzer.find_traders_from_pair(
                    pair_address=pair_address,
                    chain="ethereum",
                    hours_back=hours,
                    min_trades=1
                )
                
                if result.data and len(result.data) > 0:
                    print(f"   ✅ Found {len(result.data)} traders in {hours} hours!")
                    
                    # Show first trader details
                    trader = result.data[0]
                    print(f"   📈 Example trader: {trader['address'][:10]}...")
                    print(f"      - Trades: {trader['trades_count']}")
                    print(f"      - Win rate: {trader['win_rate']:.1f}%")
                    print(f"      - Confidence: {trader['confidence_score']:.1f}")
                    
                    results[pair_name] = {
                        "success": True,
                        "traders_found": len(result.data),
                        "hours_needed": hours,
                        "best_trader": trader['address']
                    }
                    break  # Found traders, no need to try longer windows
                    
                elif result.status.value == "no_transactions":
                    print(f"   ⏳ No transactions in {hours} hours, trying longer window...")
                    continue
                else:
                    print(f"   ❌ Error: {result.message}")
                    
            except Exception as e:
                print(f"   ❌ Exception: {e}")
                
        if pair_name not in results:
            results[pair_name] = {
                "success": False,
                "reason": "No traders found in any time window"
            }
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    
    successful_pairs = [p for p, r in results.items() if r.get("success")]
    if successful_pairs:
        print(f"\n✅ Pairs with traders found: {len(successful_pairs)}")
        for pair in successful_pairs:
            r = results[pair]
            print(f"   - {pair}: {r['traders_found']} traders in {r['hours_needed']} hours")
            print(f"     Best trader: {r['best_trader'][:10]}...")
    else:
        print("\n⚠️ No traders found in any pairs")
        print("This might indicate:")
        print("  1. The pairs are not active liquidity pools")
        print("  2. The API is not returning transaction data")
        print("  3. Need to check different contract addresses")
    
    return results


async def test_specific_active_pair():
    """Test with a known very active pair - WETH/USDT on Uniswap V2."""
    
    print("\n" + "=" * 60)
    print("🎯 TESTING KNOWN ACTIVE PAIR: WETH/USDT UNISWAP V2")
    print("=" * 60)
    
    # This is one of the most active pairs on Ethereum
    pair_address = "0x0d4a11d5EEaaC28EC3F61d100daF4d40471f1852"
    
    print(f"\nPair address: {pair_address}")
    print("This is the WETH/USDT pair on Uniswap V2 - should have lots of activity")
    
    # Try with 48 hours to ensure we find something
    result = await transaction_analyzer.find_traders_from_pair(
        pair_address=pair_address,
        chain="ethereum",
        hours_back=48,
        min_trades=2
    )
    
    if result.data and len(result.data) > 0:
        print(f"\n✅ SUCCESS! Found {len(result.data)} profitable traders")
        
        # Show top 3 traders
        print("\n📊 Top traders found:")
        for i, trader in enumerate(result.data[:3], 1):
            print(f"\n{i}. Trader: {trader['address']}")
            print(f"   - Total trades: {trader['trades_count']}")
            print(f"   - Win rate: {trader['win_rate']:.1f}%")
            print(f"   - Confidence score: {trader['confidence_score']:.1f}")
            print(f"   - Est. profit: ${trader['total_profit_usd']:.2f}")
    else:
        print(f"\n⚠️ No traders found: {result.message}")
        if result.error_details:
            print(f"Error details: {result.error_details}")


async def main():
    """Main test function."""
    
    print("\n🚀 Enhanced Transaction Analyzer Test")
    print("=" * 60)
    
    # Test 1: Try multiple active pairs
    await test_active_ethereum_pairs()
    
    # Test 2: Focus on one known active pair
    await test_specific_active_pair()
    
    # Show final statistics
    stats = transaction_analyzer.get_statistics()
    print("\n" + "=" * 60)
    print("📈 FINAL STATISTICS")
    print("=" * 60)
    print(f"API calls made: {stats['api_calls_made']}")
    print(f"API calls failed: {stats['api_calls_failed']}")
    print(f"Success rate: {stats['success_rate']:.1f}%")
    print(f"Total traders found: {stats['traders_found']}")
    print(f"Pairs analyzed: {stats['pairs_analyzed']}")


if __name__ == "__main__":
    asyncio.run(main())