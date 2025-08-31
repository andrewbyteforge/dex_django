from __future__ import annotations
from django.apps import AppConfig


class TradingConfig(AppConfig):
    """Order execution and approvals app config."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.trading"
    verbose_name = "Trading"
