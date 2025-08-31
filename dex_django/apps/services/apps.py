from __future__ import annotations
from django.apps import AppConfig


class ServicesConfig(AppConfig):
    """Shared services (pricing, metadata, alerts) app config."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.services"
    verbose_name = "Services"
