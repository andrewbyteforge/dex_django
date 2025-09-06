#!/usr/bin/env python
"""
Clear mock trader data from the database.
Run from project root: python clear_database.py
"""

import os
import sys
import django
from pathlib import Path

# Determine the project root and add to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Add the dex_django subdirectory to path as well
dex_django_dir = project_root / 'dex_django'
sys.path.insert(0, str(dex_django_dir))

# Configure Django settings - try both possible locations
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')

try:
    django.setup()
    print("✓ Django configured successfully")
except Exception as e:
    # Try alternative settings path
    os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
    try:
        django.setup()
        print("✓ Django configured successfully (using alternative path)")
    except Exception as e2:
        print(f"✗ Failed to configure Django: {e}")
        print(f"✗ Alternative path also failed: {e2}")
        print("Make sure you're running this from the project root (D:\\dex_django)")
        sys.exit(1)

# Now import models
try:
    from apps.storage.models import FollowedTrader, CopyTrade
    print("✓ Models imported successfully")
except ImportError as e:
    # Try alternative import path
    try:
        from dex_django.apps.storage.models import FollowedTrader, CopyTrade
        print("✓ Models imported successfully (alternative path)")
    except ImportError as e2:
        print(f"✗ Failed to import models: {e}")
        print(f"✗ Alternative import also failed: {e2}")
        sys.exit(1)

def clear_database():
    """Clear all trader and copy trade data."""
    
    # Show current data
    trader_count = FollowedTrader.objects.count()
    copy_count = CopyTrade.objects.count()
    
    print("\n" + "="*50)
    print("DATABASE CLEAR UTILITY")
    print("="*50)
    print(f"Current database contents:")
    print(f"  • Traders: {trader_count}")
    print(f"  • Copy Trades: {copy_count}")
    
    if trader_count == 0 and copy_count == 0:
        print("\n✓ Database is already empty!")
        return
    
    # Show sample of data to be deleted
    if trader_count > 0:
        print("\nSample traders to be deleted:")
        for trader in FollowedTrader.objects.all()[:3]:
            print(f"  - {trader.trader_name}: {trader.wallet_address[:10]}...")
        if trader_count > 3:
            print(f"  ... and {trader_count - 3} more")
    
    # Confirmation
    print("\n" + "!"*50)
    print("WARNING: This will permanently delete ALL data!")
    print("!"*50)
    print("\nType 'DELETE ALL' to confirm (or anything else to cancel):")
    
    confirm = input("> ").strip()
    
    if confirm != "DELETE ALL":
        print("\n✗ Operation cancelled")
        return
    
    print("\nDeleting data...")
    
    try:
        # Delete copy trades first (foreign key constraints)
        if copy_count > 0:
            deleted_copies = CopyTrade.objects.all().delete()
            print(f"  ✓ Deleted {deleted_copies[0]} copy trades")
        
        # Delete traders
        if trader_count > 0:
            deleted_traders = FollowedTrader.objects.all().delete()
            print(f"  ✓ Deleted {deleted_traders[0]} traders")
        
        # Verify
        remaining_traders = FollowedTrader.objects.count()
        remaining_copies = CopyTrade.objects.count()
        
        print("\n" + "="*50)
        print("OPERATION COMPLETE")
        print("="*50)
        print(f"Remaining traders: {remaining_traders}")
        print(f"Remaining copy trades: {remaining_copies}")
        
        if remaining_traders == 0 and remaining_copies == 0:
            print("\n✓ Database successfully cleared!")
        else:
            print("\n⚠ Warning: Some data may still remain")
            
    except Exception as e:
        print(f"\n✗ Error during deletion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        clear_database()
    except KeyboardInterrupt:
        print("\n\n✗ Operation cancelled by user")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)