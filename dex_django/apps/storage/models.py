from __future__ import annotations

from decimal import Decimal
from django.db import models


class Provider(models.Model):
    """Upstream providers (RPC, aggregators, security feeds)."""

    class Kind(models.TextChoices):
        RPC = "rpc", "RPC"
        AGGREGATOR = "aggregator", "Aggregator"
        SECURITY = "security", "Security"
        WEBSOCKET = "ws", "WebSocket"
        OTHER = "other", "Other"

    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.RPC)
    url = models.URLField(max_length=300, blank=True)
    mode = models.CharField(max_length=8, default="free")  # "free" | "pro"
    enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["kind", "enabled"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.kind})"


class Token(models.Model):
    """On-chain token metadata."""

    chain = models.CharField(max_length=20)  # ethereum | bsc | polygon | solana | etc.
    address = models.CharField(max_length=100)  # address or mint
    symbol = models.CharField(max_length=24)
    name = models.CharField(max_length=120, blank=True)
    decimals = models.PositiveSmallIntegerField(default=18)
    fee_on_transfer = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("chain", "address")
        indexes = [
            models.Index(fields=["chain", "symbol"]),
        ]

    def __str__(self) -> str:
        return f"{self.symbol} [{self.chain}]"


class Pair(models.Model):
    """DEX trading pair."""

    chain = models.CharField(max_length=20)
    dex = models.CharField(max_length=40)  # uniswap_v2 | uniswap_v3 | pancake | quickswap | jupiter
    address = models.CharField(max_length=100)

    base_token = models.ForeignKey(
        Token, on_delete=models.PROTECT, related_name="base_pairs"
    )
    quote_token = models.ForeignKey(
        Token, on_delete=models.PROTECT, related_name="quote_pairs"
    )
    fee_bps = models.PositiveIntegerField(default=0)

    discovered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("chain", "dex", "address")
        indexes = [
            models.Index(fields=["chain", "dex"]),
        ]

    def __str__(self) -> str:
        return f"{self.dex}:{self.address[:6]}… on {self.chain}"


class Trade(models.Model):
    """Executed trade records (minimal v1; extend later)."""

    class Side(models.TextChoices):
        BUY = "buy", "Buy"
        SELL = "sell", "Sell"

    class Mode(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTOTRADE = "autotrade", "Autotrade"

    chain = models.CharField(max_length=20)
    dex = models.CharField(max_length=40)
    pair = models.ForeignKey(Pair, on_delete=models.PROTECT)

    side = models.CharField(max_length=4, choices=Side.choices)
    mode = models.CharField(max_length=9, choices=Mode.choices, default=Mode.MANUAL)

    amount_in = models.DecimalField(max_digits=38, decimal_places=18, default=Decimal(0))
    amount_out = models.DecimalField(max_digits=38, decimal_places=18, default=Decimal(0))
    exec_price = models.DecimalField(
        max_digits=38, decimal_places=18, default=Decimal(0)
    )
    slippage_bps = models.PositiveIntegerField(default=0)
    gas_native = models.DecimalField(
        max_digits=38, decimal_places=18, default=Decimal(0)
    )
    tx_hash = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=16, default="filled")  # filled | failed | partial
    reason = models.CharField(max_length=140, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["chain", "dex"]),
            models.Index(fields=["tx_hash"]),
        ]

    def __str__(self) -> str:
        return f"{self.side} {self.pair} ({self.amount_in} in)"


class LedgerEntry(models.Model):
    """Audit-friendly event log (minimal fields for v1)."""

    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=24)  # approve | buy | sell | deposit | withdraw | fee | error
    network = models.CharField(max_length=20, blank=True)
    dex = models.CharField(max_length=40, blank=True)
    pair_address = models.CharField(max_length=100, blank=True)
    tx_hash = models.CharField(max_length=100, blank=True)

    amount_in = models.DecimalField(max_digits=38, decimal_places=18, default=Decimal(0))
    amount_out = models.DecimalField(max_digits=38, decimal_places=18, default=Decimal(0))
    fee_native = models.DecimalField(max_digits=38, decimal_places=18, default=Decimal(0))
    pnl_native = models.DecimalField(max_digits=38, decimal_places=18, default=Decimal(0))

    status = models.CharField(max_length=16, default="ok")  # ok | fail
    reason = models.CharField(max_length=140, blank=True)

    trace_id = models.CharField(max_length=64, blank=True)
    notes = models.CharField(max_length=240, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["event_type"]),
            models.Index(fields=["tx_hash"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} [{self.status}] {self.tx_hash[:8]}"
