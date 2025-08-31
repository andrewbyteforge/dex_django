from __future__ import annotations

from django.urls import path
from .consumers import HealthConsumer

websocket_urlpatterns = [
    path("ws/health", HealthConsumer.as_asgi(), name="ws-health"),
]
