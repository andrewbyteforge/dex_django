from __future__ import annotations
from django.apps import AppConfig


class DiscoveryConfig(AppConfig):
    """Discovery pipeline app config."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.discovery"
    verbose_name = "Discovery"
