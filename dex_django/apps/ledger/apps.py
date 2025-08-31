from __future__ import annotations
from django.apps import AppConfig


class LedgerConfig(AppConfig):
    """Ledger/export app config."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ledger"
    verbose_name = "Ledger"
