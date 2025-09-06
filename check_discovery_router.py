#!/usr/bin/env python
"""Check the discovery router implementation."""

from pathlib import Path

def check_discovery_router():
    """Display key parts of the discovery router."""
    
    router_path = Path('dex_django/apps/api/wallet_discovery_router.py')
    
    if not router_path.exists():
        print(f"Router file not found: {router_path}")
        return
    
    with open(router_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print("=== Discovery Router Analysis ===\n")
    
    # Find the discover_traders endpoint
    in_discover_traders = False
    indent_level = 0
    
    for i, line in enumerate(lines):
        if 'def discover_traders' in line or 'async def discover_traders' in line:
            in_discover_traders = True
            indent_level = len(line) - len(line.lstrip())
            print(f"Found discover_traders at line {i+1}:")
            print("-" * 40)
        
        if in_discover_traders:
            current_indent = len(line) - len(line.lstrip())
            
            # Stop when we reach the next function
            if line.strip() and current_indent <= indent_level and i > 0 and 'def ' in line:
                break
            
            # Show important lines
            if 'ChainType' in line or 'discover_top_traders' in line or 'return' in line:
                print(f"Line {i+1}: {line.rstrip()}")

if __name__ == "__main__":
    check_discovery_router()