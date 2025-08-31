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
    bot_settings,
    bot_status,
    bot_start,
    bot_stop,
)
from .views_paper import (
    paper_toggle,
    paper_metrics,
    paper_thought_log_test,
)

from .views_discovery import (
    discovery_status,
    discovery_start,
    discovery_stop,
    discovery_config,
    recent_discoveries,
    force_discovery_scan,
)

from .views_live_opportunities import (
    live_opportunities,
    refresh_opportunities, 
    opportunity_stats,
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
    # Paper Trading endpoints
    path("api/v1/paper/toggle", paper_toggle, name="paper-toggle"),
    path("api/v1/metrics/paper", paper_metrics, name="paper-metrics"),
    path("api/v1/paper/thought-log/test", paper_thought_log_test, name="paper-thought-log-test"),
    path("api/v1/discovery/scan", force_discovery_scan, name="force-discovery-scan"),
    path("api/v1/discovery/status", discovery_status, name="discovery-status"),
    path("api/v1/discovery/start", discovery_start, name="discovery-start"),
    path("api/v1/discovery/stop", discovery_stop, name="discovery-stop"),
    path("api/v1/discovery/config", discovery_config, name="discovery-config"),
    path("api/v1/discovery/recent", recent_discoveries, name="recent-discoveries"),

    path("api/v1/opportunities/live", live_opportunities, name="live-opportunities"),
    path("api/v1/opportunities/refresh", refresh_opportunities, name="refresh-opportunities"),
    path("api/v1/opportunities/stats", opportunity_stats, name="opportunity-stats"),
    path(
        "api/v1/",
        include(([path("ping", ping, name="ping")] + router_v1.urls, "api_v1"), namespace="api_v1"),
    ),
]