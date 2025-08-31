from __future__ import annotations
from django.apps import AppConfig


class DexConfig(AppConfig):
    """DEX adapters app config."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dex"
    verbose_name = "DEX"
