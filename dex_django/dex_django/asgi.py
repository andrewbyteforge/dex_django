# APP: backend
# FILE: dex_django/dex_django/asgi.py
"""
ASGI config for dex_django project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""
from __future__ import annotations

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path

# Import Django settings before importing channels consumers
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dex_django.settings')
django_asgi_app = get_asgi_application()

from apps.ws.consumers import PaperTradingConsumer

# WebSocket URL patterns
websocket_urlpatterns = [
    path('ws/paper', PaperTradingConsumer.as_asgi()),
]

# ASGI application with both HTTP and WebSocket support
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})