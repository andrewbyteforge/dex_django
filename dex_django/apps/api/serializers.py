from __future__ import annotations

from rest_framework import serializers
from apps.storage.models import Provider, Token, Pair, Trade


class ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = [
            "id",
            "name",
            "kind",
            "url",
            "mode",
            "enabled",
            "created_at",
            "updated_at",
        ]


class TokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Token
        fields = [
            "id",
            "chain",
            "address",
            "symbol",
            "name",
            "decimals",
            "fee_on_transfer",
            "created_at",
            "updated_at",
        ]


class PairSerializer(serializers.ModelSerializer):
    # Accept token IDs on write; show nested symbols on read for convenience
    base_token = serializers.PrimaryKeyRelatedField(
        queryset=Token.objects.all()
    )
    quote_token = serializers.PrimaryKeyRelatedField(
        queryset=Token.objects.all()
    )
    base_token_symbol = serializers.CharField(
        source="base_token.symbol", read_only=True
    )
    quote_token_symbol = serializers.CharField(
        source="quote_token.symbol", read_only=True
    )

    class Meta:
        model = Pair
        fields = [
            "id",
            "chain",
            "dex",
            "address",
            "fee_bps",
            "base_token",
            "quote_token",
            "base_token_symbol",
            "quote_token_symbol",
            "discovered_at",
            "updated_at",
        ]


class TradeSerializer(serializers.ModelSerializer):
    pair = serializers.PrimaryKeyRelatedField(queryset=Pair.objects.all())

    class Meta:
        model = Trade
        fields = [
            "id",
            "chain",
            "dex",
            "pair",
            "side",
            "mode",
            "amount_in",
            "amount_out",
            "exec_price",
            "slippage_bps",
            "gas_native",
            "tx_hash",
            "status",
            "reason",
            "created_at",
        ]

from apps.storage.models import Provider, Token, Pair, Trade, LedgerEntry  # add LedgerEntry import
# ...
class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = [
            "id",
            "timestamp",
            "event_type",
            "network",
            "dex",
            "pair_address",
            "tx_hash",
            "amount_in",
            "amount_out",
            "fee_native",
            "pnl_native",
            "status",
            "reason",
            "trace_id",
            "notes",
        ]


from rest_framework import serializers
from apps.strategy.models import BotSettings

class BotSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotSettings
        fields = [
            "id",
            "mainnet_enabled",
            "autotrade_enabled",
            "base_currency",
            "per_trade_cap_base",
            "daily_cap_base",
            "hot_wallet_hard_cap_base",
            "slippage_bps_new_pair",
            "slippage_bps_normal",
            "tp_percent",
            "sl_percent",
            "trailing_percent",
            "token_cooldown_sec",
            "chain_cooldown_sec",
            "fail_streak_pause",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("created_at", "updated_at")