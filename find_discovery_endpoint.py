#!/usr/bin/env python
"""Find where the discovery endpoint is defined."""

from pathlib import Path
import re

def find_discovery_endpoint():
    """Search for the discover-traders endpoint."""
    
    root = Path('dex_django')
    
    print("Searching for discover-traders endpoint...\n")
    
    # Search patterns
    patterns = [
        r'discover.?traders',
        r'/discovery/',
        r'wallet_discovery_engine',
        r'ChainType\('
    ]
    
    files_found = []
    
    for py_file in root.rglob('*.py'):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    files_found.append(py_file)
                    break
        except Exception:
            pass
    
    # Show unique files
    unique_files = list(set(files_found))
    
    print("Files containing discovery-related code:")
    for file in unique_files:
        rel_path = file.relative_to(Path.cwd())
        print(f"  - {rel_path}")
        
        # Check for ChainType() error
        with open(file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            if 'ChainType()' in line or 'ChainType(' in line and 'class ChainType' not in line:
                print(f"    ⚠️ Line {i+1}: {line.strip()}")

if __name__ == "__main__":
    find_discovery_endpoint()