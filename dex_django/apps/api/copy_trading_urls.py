from __future__ import annotations

from django.urls import path
from . import views_copy_trading

urlpatterns = [
    path('discover/', views_copy_trading.discover_traders, name='discover_traders'),
    path('signals/', views_copy_trading.copy_signals, name='copy_signals'),
    path('stats/', views_copy_trading.copy_trading_stats, name='copy_trading_stats'),
    path('toggle/', views_copy_trading.toggle_copy_trading, name='toggle_copy_trading'),
]