from __future__ import annotations

from django.contrib import admin
from .models import Provider, Token, Pair, Trade, LedgerEntry


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "mode", "enabled", "updated_at")
    list_filter = ("kind", "mode", "enabled")


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ("symbol", "chain", "address", "decimals", "fee_on_transfer")
    search_fields = ("symbol", "address", "name")
    list_filter = ("chain", "fee_on_transfer")


@admin.register(Pair)
class PairAdmin(admin.ModelAdmin):
    list_display = ("chain", "dex", "address", "base_token", "quote_token", "fee_bps")
    search_fields = ("address",)
    list_filter = ("chain", "dex")


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ("created_at", "chain", "dex", "pair", "side", "mode", "status")
    list_filter = ("chain", "dex", "side", "mode", "status")
    date_hierarchy = "created_at"


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "event_type", "status", "tx_hash", "trace_id")
    list_filter = ("event_type", "status")
    search_fields = ("tx_hash", "trace_id", "notes")
    date_hierarchy = "timestamp"
