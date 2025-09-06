#!/usr/bin/env python
"""
Script to fix Django settings path issues in dex_django project.
Run this from the project root: python fix_django_settings.py
"""

import os
import sys
from pathlib import Path

def fix_django_settings():
    """Fix all Django settings references in the project."""
    
    print("=" * 80)
    print("FIXING DJANGO SETTINGS PATHS")
    print("=" * 80)
    
    # Set correct environment variable immediately
    os.environ['DJANGO_SETTINGS_MODULE'] = 'dex_django.dex_django.settings'
    
    current_dir = Path.cwd()
    print(f"\nCurrent directory: {current_dir}")
    
    # Check project structure
    settings_file = current_dir / "dex_django" / "dex_django" / "settings.py"
    if settings_file.exists():
        print(f"✓ Found settings.py at correct location: {settings_file}")
    else:
        print(f"✗ Settings file not found at: {settings_file}")
        return False
    
    # Files to check and fix
    files_to_fix = {
        "manage.py": {
            "old": "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')",
            "new": "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.dex_django.settings')"
        },
        "dex_django/wsgi.py": {
            "old": "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')",
            "new": "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.dex_django.settings')"
        },
        "dex_django/asgi.py": {
            "old": "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')",
            "new": "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.dex_django.settings')"
        },
        "dex_django/dex_django/wsgi.py": {
            "old": "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')",
            "new": "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.dex_django.settings')"
        },
        "dex_django/dex_django/asgi.py": {
            "old": "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')",
            "new": "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.dex_django.settings')"
        }
    }
    
    print("\n" + "-" * 40)
    print("Checking and fixing files:")
    print("-" * 40)
    
    for file_path, replacements in files_to_fix.items():
        full_path = current_dir / file_path
        if full_path.exists():
            print(f"\nProcessing: {file_path}")
            print("\n" + "-" * 40)
    print("Testing Django setup:")
    print("-" * 40)
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if replacements["old"] in content:
            content = content.replace(replacements["old"], replacements["new"])
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ Fixed Django settings path")
        elif replacements["new"] in content:
            print(f"  ✓ Already has correct path")
        else:
            print(f"  ⚠ Neither old nor new pattern found")
            
    except Exception as e:
        print(f"  ✗ Error processing file: {e}")
    else:
        print(f"\n⚠ File not found: {file_path}")
    
    # Create __init__.py files if missing
    print("\n" + "-" * 40)
    print("Checking __init__.py files:")
    print("-" * 40)
    
    init_files = [
        "dex_django/__init__.py",
        "dex_django/dex_django/__init__.py"
    ]
    
    for init_path in init_files:
        full_path = current_dir / init_path
        if not full_path.exists():
            full_path.touch()
            print(f"  ✓ Created: {init_path}")
        else:
            print(f"  ✓ Exists: {init_path}")
    
    # Check apps directory
    print("\n" + "-" * 40)
    print("Checking apps directory:")
    print("-" * 40)
    
    apps_dir = current_dir / "dex_django" / "apps"
    if apps_dir.exists():
        print(f"  ✓ Found apps directory at: {apps_dir}")
        
        # Check for __init__.py in apps
        apps_init = apps_dir / "__init__.py"
        if not apps_init.exists():
            apps_init.touch()
            print(f"  ✓ Created apps/__init__.py")
        else:
            print(f"  ✓ apps/__init__.py exists")
        
        # List subdirectories in apps
        subdirs = [d for d in apps_dir.iterdir() if d.is_dir()]
        if subdirs:
            print(f"  Found {len(subdirs)} app modules:")
            for subdir in subdirs[:5]:  # Show first 5
                print(f"    - {subdir.name}")
    else:
        print(f"  ✗ Apps directory not found at: {apps_dir}")
        print(f"  Please ensure your Django apps are in the correct location")
    
    # Test Django import
    print("\n" + "-" * 40)
    print("Testing Django setup:")
    print("-" * 40)
    
    # Add project root to path
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    
    try:
        # Try to import the settings module
        import importlib
        settings_module = importlib.import_module('dex_django.dex_django.settings')
        print(f"  ✓ Successfully imported settings module")
        
        # Try Django setup
        import django
        django.setup()
        print(f"  ✓ Django setup successful!")
        
        from django.conf import settings
        print(f"  ✓ Database: {settings.DATABASES['default']['NAME']}")
        print(f"  ✓ Installed apps: {len(settings.INSTALLED_APPS)} apps")
        
        return True
        
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Setup error: {e}")
        return False
    
    print("\n" + "=" * 80)
    print("DONE")
    print("=" * 80)


if __name__ == "__main__":
    success = fix_django_settings()
    
    if success:
        print("\n✅ Django settings have been fixed successfully!")
        print("You can now run: python debug_main.py")
    else:
        print("\n❌ There were issues fixing Django settings.")
        print("Please check the errors above and fix them manually.")