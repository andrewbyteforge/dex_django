#!/usr/bin/env python
"""Create a simple discovery endpoint that returns empty results."""

from pathlib import Path

def create_simple_discovery():
    """Create a simple discovery function that returns empty results."""
    
    file_path = Path('dex_django/apps/api/copy_trading_discovery.py')
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
    
    # Read the file to find the discover_traders function
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the function
    for i, line in enumerate(lines):
        if 'async def discover_traders' in line:
            print(f"Found discover_traders at line {i+1}")
            
            # Show next 10 lines to see what it's doing
            print("\nCurrent implementation:")
            for j in range(i, min(i+10, len(lines))):
                print(f"  {lines[j].rstrip()}")
            
            print("\n" + "="*50)
            print("To fix the hanging issue, temporarily replace the function with:")
            print("="*50)
            print("""
@router.post("/discovery/discover-traders")
async def discover_traders(req: DiscoverTradersRequest) -> Dict[str, Any]:
    \"\"\"Temporarily return empty results to fix hanging issue.\"\"\"
    
    logger.info(f"Discovery request received for chains: {req.chains}")
    
    # Return empty results for now
    return {
        "status": "ok",
        "wallets": [],
        "message": "Discovery engine temporarily disabled - add traders manually",
        "total_discovered": 0,
        "chains_searched": req.chains
    }
""")
            break

if __name__ == "__main__":
    create_simple_discovery()