#!/usr/bin/env python
"""Fix the ChainType initialization error in wallet_discovery_engine.py"""

from pathlib import Path
import re

def fix_chaintype_error():
    """Fix ChainType enum usage in the discovery engine."""
    
    file_path = Path('dex_django/apps/discovery/wallet_discovery_engine.py')
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for the ChainType class definition
    if 'class ChainType:' in content:
        # It's using a stub class, not an enum
        print("Found stub ChainType class (not enum)")
        
        # Replace ChainType() calls with proper attribute access
        content = re.sub(r'ChainType\(\)', 'ChainType', content)
        
        # Make sure ChainType attributes are strings
        content = re.sub(
            r'class ChainType:\s*\n\s+ETHEREUM = "ethereum"\s*\n\s+BSC = "bsc"\s*\n\s+BASE = "base"\s*\n\s+POLYGON = "polygon"',
            '''class ChainType:
    ETHEREUM = "ethereum"
    BSC = "bsc" 
    BASE = "base"
    POLYGON = "polygon"
    SOLANA = "solana"
    
    @classmethod
    def values(cls):
        return ["ethereum", "bsc", "base", "polygon", "solana"]''',
            content
        )
    
    # Fix any ChainType() initialization errors
    content = re.sub(r'ChainType\(\)', 'ChainType', content)
    
    # Also fix the chain_mapping dictionary to use string values
    content = re.sub(
        r'chain_mapping = \{\s*ChainType\.ETHEREUM:',
        'chain_mapping = {\n            "ethereum":',
        content
    )
    content = re.sub(
        r'ChainType\.(ETHEREUM|BSC|BASE|POLYGON|SOLANA)(?=:)',
        r'"\1".lower()',
        content
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ Fixed ChainType issues in {file_path}")
    print("Now checking the discovery router...")
    
    # Also check the router file
    router_path = Path('dex_django/apps/api/wallet_discovery_router.py')
    if router_path.exists():
        with open(router_path, 'r', encoding='utf-8') as f:
            router_content = f.read()
        
        # Fix ChainType usage in router
        router_content = re.sub(r'ChainType\((.*?)\)', r'str(\1)', router_content)
        
        with open(router_path, 'w', encoding='utf-8') as f:
            f.write(router_content)
        
        print(f"✓ Fixed ChainType usage in router")

if __name__ == "__main__":
    fix_chaintype_error()