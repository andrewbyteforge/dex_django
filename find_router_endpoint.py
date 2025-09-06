#!/usr/bin/env python
"""Completely disable the discovery engine to return empty results."""

from pathlib import Path

def disable_discovery_engine():
    """Make discover_top_traders return empty list immediately."""
    
    file_path = Path('dex_django/apps/discovery/wallet_discovery_engine.py')
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find discover_top_traders method
    new_lines = []
    in_method = False
    method_found = False
    
    for i, line in enumerate(lines):
        if 'async def discover_top_traders' in line:
            in_method = True
            method_found = True
            new_lines.append(line)
            # Get the indentation
            next_line_indent = '        '  # Assuming 8 spaces
            # Add immediate return
            new_lines.append(f'{next_line_indent}"""Return empty list - discovery disabled."""\n')
            new_lines.append(f'{next_line_indent}logger.info("Discovery disabled - returning empty list")\n')
            new_lines.append(f'{next_line_indent}return []  # No mock data\n')
            new_lines.append('\n')
            print(f"Found discover_top_traders at line {i+1}")
            print("Adding immediate return []")
            continue
            
        if in_method:
            # Check if we're out of the method
            current_indent = len(line) - len(line.lstrip())
            if line.strip() and current_indent == 4:  # Back to class level
                in_method = False
                new_lines.append(line)
            # Skip the original method body
        else:
            new_lines.append(line)
    
    if method_found:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"\n✓ Disabled discover_top_traders in {file_path}")
        print("The discovery engine will now return empty results immediately.")
    else:
        print("Method not found!")

if __name__ == "__main__":
    disable_discovery_engine()