from __future__ import annotations
from django.apps import AppConfig


class StrategyConfig(AppConfig):
    """Strategies and risk controls app config."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.strategy"
    verbose_name = "Strategy"
