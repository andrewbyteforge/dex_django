# APP: backend
# FILE: dex_django/dex_django/routing.py
from __future__ import annotations

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path

from apps.ws.consumers import PaperTradingConsumer

# Django Channels routing
websocket_urlpatterns = [
    path('ws/paper', PaperTradingConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})