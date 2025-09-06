# APP: backend
# FILE: dex_django/apps/discovery/test_rate_limited.py
"""
Simple rate-limited test for transaction analyzer.
Respects Etherscan's 2 requests per second limit.
"""

import asyncio
import logging
from transaction_analyzer import transaction_analyzer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_rate_limited")


async def test_single_pair():
    """Test a single pair with proper rate limiting."""
    
    print("\n" + "=" * 60)
    print("RATE-LIMITED TEST - SINGLE PAIR")
    print("=" * 60)
    
    # Use WETH/USDC V2 - one of the most active pairs
    pair_address = "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc"
    pair_name = "WETH/USDC Uniswap V2"
    
    print(f"\nTesting: {pair_name}")
    print(f"Address: {pair_address}")
    print(f"Rate limit delay: {transaction_analyzer.rate_limit_delay} seconds")
    
    # Try with 72 hours to find more transactions
    hours = 72
    print(f"\nSearching for transactions in the last {hours} hours...")
    
    result = await transaction_analyzer.find_traders_from_pair(
        pair_address=pair_address,
        chain="ethereum",
        hours_back=hours,
        min_trades=1
    )
    
    print("\n" + "-" * 60)
    print("RESULTS:")
    print("-" * 60)
    
    if result.status.value == "success":
        if result.data and len(result.data) > 0:
            print(f"✅ SUCCESS! Found {len(result.data)} traders")
            
            # Show first 3 traders
            for i, trader in enumerate(result.data[:3], 1):
                print(f"\nTrader {i}:")
                print(f"  Address: {trader['address']}")
                print(f"  Trades: {trader['trades_count']}")
                print(f"  Win rate: {trader['win_rate']:.1f}%")
                print(f"  Confidence: {trader['confidence_score']:.1f}")
        else:
            print("⚠️ No profitable traders found (transactions exist but none meet criteria)")
    elif result.status.value == "no_transactions":
        print("⚠️ No transactions found in time range")
        print("This pair might not have direct transactions (could be a V3 pool)")
    elif result.status.value == "rate_limited":
        print("❌ Rate limited by Etherscan")
        print("Wait a minute and try again")
    else:
        print(f"❌ Error: {result.message}")
        if result.error_details:
            print(f"Details: {result.error_details[:200]}")
    
    # Show statistics
    stats = transaction_analyzer.get_statistics()
    print("\n" + "-" * 60)
    print("API STATISTICS:")
    print("-" * 60)
    print(f"Calls made: {stats['api_calls_made']}")
    print(f"Calls failed: {stats['api_calls_failed']}")
    print(f"Success rate: {stats['success_rate']:.1f}%")
    

async def test_router_instead():
    """Test Uniswap V2 Router instead of pair contracts."""
    
    print("\n" + "=" * 60)
    print("TESTING UNISWAP V2 ROUTER")
    print("=" * 60)
    
    # Uniswap V2 Router - where actual swaps happen
    router_address = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
    
    print(f"\nTesting: Uniswap V2 Router")
    print(f"Address: {router_address}")
    print("Note: This is where traders actually send transactions")
    
    # Only check last 1 hour to avoid too many transactions
    result = await transaction_analyzer.find_traders_from_pair(
        pair_address=router_address,  # Using router as "pair" to test
        chain="ethereum",
        hours_back=1,
        min_trades=1
    )
    
    if result.status.value == "success" and result.data:
        print(f"\n✅ Found {len(result.data)} traders using the router!")
        print("This confirms the system works - we just need to target router contracts")
    else:
        print(f"\nStatus: {result.status.value}")
        print(f"Message: {result.message}")


async def main():
    """Main test function."""
    
    print("\n🔍 Transaction Analyzer - Rate Limited Test")
    print("=" * 60)
    print("This test respects Etherscan's 2/sec rate limit")
    print("Delay between requests: 0.6 seconds")
    print("=" * 60)
    
    # Test 1: Single pair with longer history
    await test_single_pair()
    
    # Wait before next test
    print("\n⏳ Waiting 2 seconds before next test...")
    await asyncio.sleep(2)
    
    # Test 2: Try router contract instead
    await test_router_instead()
    
    print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(main())