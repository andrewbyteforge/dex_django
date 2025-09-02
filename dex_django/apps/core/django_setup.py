# APP: backend
# FILE: backend/app/core/django_setup.py
from __future__ import annotations

import logging
import os
import sys
import traceback
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
        # Add the dex_django directory to Python path
        project_root = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            '..', '..', '..', 'dex_django'
        )
        project_root = os.path.abspath(project_root)
        
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            logger.debug(f"Added project root to Python path: {project_root}")
        
        # Configure Django settings BEFORE importing django
        if not os.environ.get('DJANGO_SETTINGS_MODULE'):
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')
            logger.debug("Set DJANGO_SETTINGS_MODULE environment variable")
        
        # NOW import django after environment is set
        import django
        from django.conf import settings
        
        # Only setup if not already configured
        if not settings.configured:
            django.setup()
            logger.info("Django ORM initialized successfully")
        else:
            logger.debug("Django already configured, skipping setup")
        
        return True
        
    except ImportError as e:
        logger.error(f"Failed to import Django modules: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False
        
    except Exception as e:
        logger.error(f"Failed to initialize Django: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
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
            return True, "Django ORM is initialized and configured"
        else:
            return False, "Django settings not configured"
            
    except ImportError:
        return False, "Django not available (ImportError)"
        
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
        
        if settings.configured:
            logger.info(f"Database engine: {settings.DATABASES.get('default', {}).get('ENGINE', 'Unknown')}")
            logger.info(f"Database name: {settings.DATABASES.get('default', {}).get('NAME', 'Unknown')}")
            logger.info(f"Installed apps count: {len(settings.INSTALLED_APPS)}")
        else:
            logger.warning("Django settings not configured")
            
    except Exception as e:
        logger.error(f"Failed to log Django info: {e}")