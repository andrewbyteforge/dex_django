#!/usr/bin/env python
"""Fix all ChainType() initialization errors in the project."""

from pathlib import Path
import re

def fix_file(file_path, line_numbers_with_errors):
    """Fix ChainType errors in a specific file."""
    
    path = Path(file_path)
    if not path.exists():
        print(f"  ✗ File not found: {file_path}")
        return False
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Fix patterns
    replacements = [
        # ChainType(something) -> something (for string values)
        (r'ChainType\(([\w\.]+)\)', r'\1'),
        # ChainType(something.lower()) -> something.lower()
        (r'ChainType\(([\w\.]+\.lower\(\))\)', r'\1'),
        # [ChainType(chain) for chain in ...] -> just use chains directly
        (r'\[ChainType\((\w+)\) for \1 in ([\w\.]+)\]', r'\2'),
        # chain_enum = ChainType(req.chain) -> chain_enum = req.chain
        (r'(\w+) = ChainType\(([\w\.]+)\)', r'\1 = \2'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    """Fix all ChainType errors found."""
    
    files_to_fix = [
        ('dex_django/apps/api/copy_trading.py', [323]),
        ('dex_django/apps/storage/copy_trading_models.py', [338]),
        ('dex_django/apps/api/copy_trading_discovery.py', [177]),
        ('dex_django/apps/api/wallet_discovery.py', [124, 228, 304]),
    ]
    
    print("Fixing ChainType() initialization errors...\n")
    
    for file_path, line_nums in files_to_fix:
        print(f"Processing: {file_path}")
        print(f"  Lines with errors: {line_nums}")
        
        if fix_file(file_path, line_nums):
            print(f"  ✓ Fixed ChainType errors")
        else:
            print(f"  - No changes made")
        print()
    
    print("✅ All ChainType errors should be fixed!")
    print("\nRestart your server and test again:")
    print("  python test_discovery_api.py")

if __name__ == "__main__":
    main()