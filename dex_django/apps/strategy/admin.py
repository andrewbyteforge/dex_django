from __future__ import annotations

from django.contrib import admin
from .models import BotSettings


@admin.register(BotSettings)
class BotSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "mainnet_enabled",
        "autotrade_enabled",
        "base_currency",
        "per_trade_cap_base",
        "daily_cap_base",
        "hot_wallet_hard_cap_base",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")
