from __future__ import annotations
from django.apps import AppConfig


class ChainsConfig(AppConfig):
    """Chains/RPC clients app config."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.chains"
    verbose_name = "Chains"
