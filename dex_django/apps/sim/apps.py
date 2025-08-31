from __future__ import annotations
from django.apps import AppConfig


class SimConfig(AppConfig):
    """Simulation and reports app config."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sim"
    verbose_name = "Simulation"
