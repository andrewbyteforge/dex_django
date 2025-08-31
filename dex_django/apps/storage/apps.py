from __future__ import annotations

from django.apps import AppConfig


class StorageConfig(AppConfig):
    """Storage/models app config."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.storage"
    verbose_name = "Storage"

    def ready(self) -> None:
        # Import registers signal handlers
        from . import signals  # noqa: F401
