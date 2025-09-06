#!/usr/bin/env python
"""Fix the indentation error in wallet_discovery_engine.py"""

from pathlib import Path

def fix_indentation():
    """Fix the ChainType class indentation."""
    
    file_path = Path('dex_django/apps/discovery/wallet_discovery_engine.py')
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find line 33 (class ChainType:)
    if len(lines) > 33:
        print(f"Line 33: {lines[32].rstrip()}")
        print(f"Line 34: {lines[33].rstrip()}")
        
        # Check if line 34 needs indentation
        if lines[32].strip().startswith('class ChainType') and not lines[33].startswith('    '):
            print("\nFixing indentation...")
            
            # Fix lines 34 onwards until we hit another class or def
            fixed_lines = lines[:33]
            i = 33
            
            while i < len(lines):
                line = lines[i]
                
                # If it's a class attribute without proper indentation
                if ('=' in line and not line.startswith('    ') and 
                    not line.strip().startswith('#') and
                    not line.strip().startswith('class') and
                    not line.strip().startswith('def')):
                    # Add indentation
                    fixed_lines.append('    ' + line)
                    print(f"Fixed line {i+1}: {'    ' + line.rstrip()}")
                elif line.strip() and not line.startswith('    ') and (
                    line.strip().startswith('class') or 
                    line.strip().startswith('def') or
                    line.strip().startswith('logger')):
                    # End of ChainType class
                    fixed_lines.extend(lines[i:])
                    break
                else:
                    fixed_lines.append(line)
                
                i += 1
            
            # Write the fixed file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(fixed_lines)
            
            print("\n✓ Fixed indentation in wallet_discovery_engine.py")
        else:
            print("\nIndentation looks correct or different issue.")
    else:
        print("File has less than 34 lines")

if __name__ == "__main__":
    fix_indentation()