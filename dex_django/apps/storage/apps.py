from __future__ import annotations

import logging
from django.apps import AppConfig
from django.db.backends.signals import connection_created

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    """Core app config."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "dex_django.apps.core"  # FIXED: Added dex_django prefix to match INSTALLED_APPS
    verbose_name = "Core"

    def ready(self) -> None:
        # Import here to avoid import-time side effects
        from .signals import apply_sqlite_pragmas

        # Connect once; Django handles per-process import
        connection_created.connect(apply_sqlite_pragmas, dispatch_uid="sqlite_pragmas_once")
        logger.info("Core signals connected (connection_created → apply_sqlite_pragmas).")