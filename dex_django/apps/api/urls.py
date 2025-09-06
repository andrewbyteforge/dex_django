from __future__ import annotations

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import only the views that actually exist in your directory
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
from .views_live_opportunities import (
    live_opportunities,
    refresh_opportunities,
    opportunity_stats,
    analyze_opportunity,
)
from .views_wallet import (
    wallet_balances,
    prepare_transaction,
    supported_chains,
)

# Try to import intelligence views with error handling
try:
    from .views_bot_intelligence import (
        analyze_opportunities,
        detailed_analysis,
        risk_settings,
        intelligence_status
    )
    INTELLIGENCE_AVAILABLE = True
except ImportError as e:
    print(f"Intelligence views not available: {e}")
    INTELLIGENCE_AVAILABLE = False

# Set up DRF router
router_v1 = DefaultRouter()
router_v1.register(r"providers", ProviderViewSet, basename="providers")
router_v1.register(r"tokens", TokenViewSet, basename="tokens")
router_v1.register(r"pairs", PairViewSet, basename="pairs")
router_v1.register(r"trades", TradeViewSet, basename="trades")
router_v1.register(r"ledger", LedgerEntryViewSet, basename="ledger")

urlpatterns = [
    # Basic endpoints
    path("", index, name="index"),
    path("health", health, name="health"),
    path("api/v1/health", health, name="api-health"),
    
    # Bot control endpoints
    path("api/v1/bot/settings", bot_settings, name="bot-settings"),
    path("api/v1/bot/status", bot_status, name="bot-status"),
    path("api/v1/bot/start", bot_start, name="bot-start"),
    path("api/v1/bot/stop", bot_stop, name="bot-stop"),
    
    # Paper Trading endpoints
    path("api/v1/paper/toggle", paper_toggle, name="paper-toggle"),
    path("api/v1/metrics/paper", paper_metrics, name="paper-metrics"),
    path("api/v1/paper/thought-log/test", paper_thought_log_test, name="paper-thought-log-test"),
    
    # NOTE: Discovery endpoints removed since views_discovery.py doesn't exist
    # You can add them back when you create the views_discovery.py file
    
    # Live Opportunities endpoints
    path("api/v1/opportunities/live", live_opportunities, name="live-opportunities"),
    path("api/v1/opportunities/refresh", refresh_opportunities, name="refresh-opportunities"),
    path("api/v1/opportunities/stats", opportunity_stats, name="opportunity-stats"),
    path("api/v1/opportunities/analyze", analyze_opportunity, name="analyze-opportunity"),
    
    # Wallet endpoints
    path("api/v1/wallet/balances", wallet_balances, name="wallet-balances"),
    path("api/v1/wallet/prepare", prepare_transaction, name="prepare-transaction"),
    path("api/v1/chains", supported_chains, name="supported-chains"),
    
    # DRF router endpoints (includes ping and CRUD)
    path("api/v1/", include(router_v1.urls)),
    path("api/v1/ping", ping, name="ping"),
]

# Add intelligence endpoints if available
if INTELLIGENCE_AVAILABLE:
    urlpatterns.extend([
        path("api/v1/intelligence/analyze", analyze_opportunities, name="analyze-opportunities"),
        path("api/v1/intelligence/detailed", detailed_analysis, name="detailed-analysis"),
        path("api/v1/intelligence/risk", risk_settings, name="risk-settings"),
        path("api/v1/intelligence/status", intelligence_status, name="intelligence-status"),
    ])