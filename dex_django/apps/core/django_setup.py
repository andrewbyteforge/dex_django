# APP: dex_django
# FILE: dex_django/apps/core/django_setup.py
from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Tuple

logger = logging.getLogger("core.django_setup")


def setup_django() -> bool:
    """
    Initialize Django ORM for database access.
    
    Configures Django settings and initializes the ORM system.
    Must be called before importing any Django models or using ORM features.
    
    Returns:
        bool: True if Django was successfully initialized, False otherwise.
        
    Raises:
        None: All exceptions are caught and logged, returns False on failure.
    """
    try:
        # Find the actual project root (dex_django directory)
        current_file = Path(__file__).resolve()
        # Go up from apps/core/django_setup.py to find dex_django root
        # Current path: dex_django/apps/core/django_setup.py
        # Target: dex_django/ (2 levels up)
        project_root = current_file.parent.parent.parent
        
        # Verify we found the right directory by checking for manage.py
        manage_py = project_root / "manage.py"
        settings_file = project_root / "dex_django" / "settings.py"
        
        if not manage_py.exists():
            # Try alternative path structure
            logger.warning(f"manage.py not found at {manage_py}, trying alternative paths")
            # Maybe we're in a different structure, try to find dex_django
            for parent in current_file.parents:
                if (parent / "manage.py").exists():
                    project_root = parent
                    logger.info(f"Found project root at: {project_root}")
                    break
            else:
                logger.error("Could not locate manage.py in any parent directory")
                return False
        
        # Convert to string for sys.path
        project_root_str = str(project_root)
        
        # Add to Python path if not already there
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)
            logger.info(f"Added project root to Python path: {project_root_str}")
        
        # Log the actual settings file path for debugging
        expected_settings = project_root / "dex_django" / "settings.py"
        if expected_settings.exists():
            logger.debug(f"Found settings.py at: {expected_settings}")
        else:
            logger.warning(f"settings.py not found at expected location: {expected_settings}")
        
        # Configure Django settings BEFORE importing django
        # Use the correct module path: 'dex_django.dex_django.settings' not 'dex_django.dex_django.settings'
        if not os.environ.get('DJANGO_SETTINGS_MODULE'):
            os.environ['DJANGO_SETTINGS_MODULE'] = 'dex_django.dex_django.settings'
            logger.info(f"Set DJANGO_SETTINGS_MODULE to: dex_django.settings")
        else:
            current_setting = os.environ.get('DJANGO_SETTINGS_MODULE')
            if current_setting != 'dex_django.dex_django.settings':
                logger.warning(f"Overriding DJANGO_SETTINGS_MODULE from '{current_setting}' to 'dex_django.dex_django.settings'")
                os.environ['DJANGO_SETTINGS_MODULE'] = 'dex_django.dex_django.settings'
            else:
                logger.info(f"DJANGO_SETTINGS_MODULE already correctly set to: {current_setting}")
        
        # Test if we can import the settings module before trying Django setup
        try:
            import importlib
            settings_module = importlib.import_module('dex_django.dex_django.settings')
            logger.debug(f"Successfully imported settings module from: {settings_module.__file__}")
        except ImportError as e:
            logger.error(f"Cannot import dex_django.settings: {e}")
            logger.error(f"Current working directory: {os.getcwd()}")
            logger.error(f"Python path: {sys.path}")
            return False
        
        # NOW import django after environment is set
        import django
        from django.conf import settings
        
        # Only setup if not already configured
        if not settings.configured:
            django.setup()
            logger.info("Django ORM initialized successfully")
            
            # Log successful initialization details
            try:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    logger.info("Database connection verified successfully")
            except Exception as db_error:
                logger.warning(f"Database connection test failed (may be normal on startup): {db_error}")
        else:
            logger.debug("Django already configured, skipping setup")
        
        return True
        
    except ImportError as e:
        logger.error(f"Failed to import Django modules: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        logger.error(f"Python path: {sys.path}")
        logger.error(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE', 'Not set')}")
        return False
        
    except Exception as e:
        logger.error(f"Failed to initialize Django: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        logger.error(f"Python path: {sys.path}")
        logger.error(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE', 'Not set')}")
        return False


def get_django_status() -> Tuple[bool, str]:
    """
    Check Django initialization status.
    
    Returns:
        Tuple[bool, str]: (is_initialized, status_message)
    """
    try:
        import django
        from django.conf import settings
        
        if settings.configured:
            # Try to get more detailed status
            try:
                from django.db import connection
                # Test the connection
                connection.ensure_connection()
                return True, "Django ORM is initialized and database is connected"
            except Exception as db_error:
                return True, f"Django ORM is initialized but database may not be ready: {db_error}"
        else:
            return False, "Django settings not configured"
            
    except ImportError as e:
        return False, f"Django not available (ImportError: {e})"
        
    except Exception as e:
        return False, f"Django status check failed: {e}"


def ensure_django_ready() -> bool:
    """
    Ensure Django is ready for use, attempting initialization if needed.
    
    Returns:
        bool: True if Django is ready, False if initialization failed.
    """
    is_ready, status = get_django_status()
    
    if is_ready:
        logger.debug(f"Django status: {status}")
        return True
    
    logger.info(f"Django not ready: {status}. Attempting initialization...")
    return setup_django()


def log_django_info() -> None:
    """Log Django configuration information for debugging."""
    try:
        import django
        from django.conf import settings
        
        logger.info(f"Django version: {django.get_version()}")
        logger.info(f"Settings module: {os.environ.get('DJANGO_SETTINGS_MODULE', 'Not set')}")
        logger.info(f"Python path: {sys.path[:3]}...")  # Log first 3 paths
        
        if settings.configured:
            logger.info(f"Project BASE_DIR: {getattr(settings, 'BASE_DIR', 'Not set')}")
            logger.info(f"Database engine: {settings.DATABASES.get('default', {}).get('ENGINE', 'Unknown')}")
            logger.info(f"Database name: {settings.DATABASES.get('default', {}).get('NAME', 'Unknown')}")
            logger.info(f"Installed apps count: {len(settings.INSTALLED_APPS)}")
            
            # Log first few installed apps for verification
            if settings.INSTALLED_APPS:
                logger.info(f"First installed apps: {settings.INSTALLED_APPS[:3]}")
        else:
            logger.warning("Django settings not configured")
            
    except Exception as e:
        logger.error(f"Failed to log Django info: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")


# Optional: Test function for debugging
def test_django_setup() -> None:
    """Test Django setup and print diagnostic information."""
    print("=" * 60)
    print("Django Setup Diagnostic Test")
    print("=" * 60)
    
    print(f"Current working directory: {os.getcwd()}")
    print(f"Script location: {__file__}")
    print(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE', 'Not set')}")
    
    # Try to find project structure
    current = Path(__file__).resolve()
    print(f"\nDirectory structure:")
    for parent in current.parents[:4]:
        print(f"  {parent}")
        if (parent / "manage.py").exists():
            print(f"    ✓ Found manage.py")
        if (parent / "dex_django" / "settings.py").exists():
            print(f"    ✓ Found dex_django/settings.py")
    
    print("\n" + "=" * 60)
    result = ensure_django_ready()
    print(f"Django setup result: {result}")
    
    if result:
        log_django_info()
        print("Django setup successful! Check logs for details.")
    else:
        print("Django setup failed. Check logs for error details.")
    
    print("=" * 60)


if __name__ == "__main__":
    # If run directly, execute the test
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    test_django_setup()