from __future__ import annotations

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import index, health
from .views_api_v1 import (
    ping,
    ProviderViewSet,
    TokenViewSet,
    PairViewSet,
    TradeViewSet,
    LedgerEntryViewSet,
    # ↓ add these four
    bot_settings,
    bot_status,
    bot_start,
    bot_stop,
)

router_v1 = DefaultRouter()
router_v1.register(r"providers", ProviderViewSet, basename="providers")
router_v1.register(r"tokens", TokenViewSet, basename="tokens")
router_v1.register(r"pairs", PairViewSet, basename="pairs")
router_v1.register(r"trades", TradeViewSet, basename="trades")
router_v1.register(r"ledger", LedgerEntryViewSet, basename="ledger")

urlpatterns = [
    path("", index, name="index"),
    path("health", health, name="health"),
    path("api/v1/health", health, name="api-health"),
    path("api/v1/bot/settings", bot_settings, name="bot-settings"),
    path("api/v1/bot/status", bot_status, name="bot-status"),
    path("api/v1/bot/start", bot_start, name="bot-start"),
    path("api/v1/bot/stop", bot_stop, name="bot-stop"),
    path(
        "api/v1/",
        include(([path("ping", ping, name="ping")] + router_v1.urls, "api_v1"), namespace="api_v1"),
    ),
]
