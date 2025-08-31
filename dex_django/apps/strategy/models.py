from __future__ import annotations

from decimal import Decimal
from django.db import models


class BotSettings(models.Model):
    """
    Single row of global settings that the bot/runner will read.
    """

    # safety gates
    mainnet_enabled = models.BooleanField(default=False)
    autotrade_enabled = models.BooleanField(default=False)

    # currency & budget caps (base is e.g. GBP; UI will allow change)
    base_currency = models.CharField(max_length=8, default="GBP")
    per_trade_cap_base = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("75"))
    daily_cap_base = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("500"))
    hot_wallet_hard_cap_base = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("200"))

    # slippage & risk presets (v1 defaults from overview)
    slippage_bps_new_pair = models.PositiveIntegerField(default=700)  # 7%
    slippage_bps_normal = models.PositiveIntegerField(default=300)    # 3%
    tp_percent = models.PositiveIntegerField(default=40)
    sl_percent = models.PositiveIntegerField(default=20)
    trailing_percent = models.PositiveIntegerField(default=15)

    # cooldowns (seconds)
    token_cooldown_sec = models.PositiveIntegerField(default=60)
    chain_cooldown_sec = models.PositiveIntegerField(default=300)

    # circuit breaker
    fail_streak_pause = models.PositiveIntegerField(default=3)

    # timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bot Settings"
        verbose_name_plural = "Bot Settings"

    def __str__(self) -> str:  # flake8: noqa: D401
        return "BotSettings(1)"
