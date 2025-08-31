from __future__ import annotations
from django.apps import AppConfig


class WsConfig(AppConfig):
    """WebSocket/real-time app config."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ws"
    verbose_name = "WebSockets"
