from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


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
        app_label = "storage"  # FIXED: Added explicit app_label
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
        app_label = "storage"  # FIXED: Added explicit app_label
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
        app_label = "storage"  # FIXED: Added explicit app_label
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
        app_label = "storage"  # FIXED: Added explicit app_label
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
        app_label = "storage"  # FIXED: Added explicit app_label
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["event_type"]),
            models.Index(fields=["tx_hash"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} [{self.status}] {self.tx_hash[:8]}"


# COPY TRADING MODELS - ADD AFTER EXISTING MODELS

class TraderStatus(models.TextChoices):
    """Status of a followed trader."""
    ACTIVE = "active", "Active"
    PAUSED = "paused", "Paused"
    BLACKLISTED = "blacklisted", "Blacklisted"


class CopyMode(models.TextChoices):
    """Copy trading modes."""
    PERCENTAGE = "percentage", "Percentage of Portfolio"
    FIXED_AMOUNT = "fixed_amount", "Fixed Amount"
    PROPORTIONAL = "proportional", "Proportional to Trader"


class CopyStatus(models.TextChoices):
    """Status of copy trade execution."""
    PENDING = "pending", "Pending"
    EXECUTED = "executed", "Executed"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class FollowedTrader(models.Model):
    """
    Track wallets we're copying trades from.
    Integrates with existing DEX Sniper Pro architecture.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Trader identification
    wallet_address = models.CharField(
        max_length=64, 
        unique=True, 
        db_index=True,
        help_text="Ethereum/EVM wallet address to follow"
    )
    trader_name = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    
    # Status and configuration
    status = models.CharField(
        max_length=20,
        choices=TraderStatus.choices,
        default=TraderStatus.ACTIVE,
        db_index=True
    )
    
    # Copy settings
    copy_mode = models.CharField(
        max_length=20,
        choices=CopyMode.choices,
        default=CopyMode.PERCENTAGE
    )
    copy_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("5.0"),
        validators=[MinValueValidator(Decimal("0.1")), MaxValueValidator(Decimal("50.0"))],
        help_text="Percentage of portfolio to allocate (for percentage mode)"
    )
    fixed_amount_usd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("10.0"))],
        help_text="Fixed USD amount per trade (for fixed amount mode)"
    )
    
    # Risk controls
    max_position_usd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("1000.0"),
        validators=[MinValueValidator(Decimal("50.0")), MaxValueValidator(Decimal("50000.0"))],
        help_text="Maximum position size in USD"
    )
    min_trade_usd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("50.0"),
        validators=[MinValueValidator(Decimal("10.0"))],
        help_text="Minimum original trade size to copy"
    )
    max_slippage_bps = models.PositiveIntegerField(
        default=300,
        validators=[MinValueValidator(50), MaxValueValidator(1000)]
    )
    max_risk_score = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=Decimal("7.0"),
        validators=[MinValueValidator(Decimal("1.0")), MaxValueValidator(Decimal("10.0"))],
        help_text="Maximum risk score threshold (1.0-10.0)"
    )
    
    # Chain and token filters
    allowed_chains = models.JSONField(
        default=list,
        help_text="List of allowed chains: ['ethereum', 'bsc', 'base', 'polygon', 'solana']"
    )
    blacklisted_tokens = models.JSONField(
        default=list,
        help_text="List of token addresses to never copy"
    )
    whitelisted_tokens = models.JSONField(
        default=list,
        help_text="List of token addresses to exclusively copy (empty = all allowed)"
    )
    
    # Trade type filters
    copy_buy_only = models.BooleanField(default=False)
    copy_sell_only = models.BooleanField(default=False)
    
    # Trade size filters
    min_trade_usd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("100.0"),
        help_text="Minimum original trade size to copy"
    )
    max_trade_usd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("50000.0"),
        help_text="Maximum original trade size to copy"
    )
    
    # Performance tracking
    total_copies = models.PositiveIntegerField(default=0)
    successful_copies = models.PositiveIntegerField(default=0)
    total_pnl_usd = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.0")
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "storage"  # FIXED: Added explicit app_label
        verbose_name = "Followed Trader"
        verbose_name_plural = "Followed Traders" 
        db_table = "copy_followed_traders"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet_address']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['-last_activity_at']),
        ]

    def __str__(self) -> str:
        return f"{self.trader_name or self.wallet_address[:8]}"

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_copies == 0:
            return 0.0
        return (self.successful_copies / self.total_copies) * 100

    def update_stats(self, success: bool, pnl_usd: Decimal) -> None:
        """Update performance statistics."""
        self.total_copies += 1
        if success:
            self.successful_copies += 1
        self.total_pnl_usd += pnl_usd
        self.last_activity_at = timezone.now()
        self.save()


class CopyTrade(models.Model):
    """
    Individual copy trade execution record.
    Links to existing Trade model when executed.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    followed_trader = models.ForeignKey(
        FollowedTrader,
        on_delete=models.CASCADE,
        related_name="copy_trades"
    )
    trade = models.ForeignKey(
        Trade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="copy_trades",
        help_text="Link to executed trade (if any)"
    )
    ledger_entry = models.ForeignKey(
        LedgerEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="copy_trades",
        help_text="Link to ledger entry"
    )
    
    # Original trade details
    original_tx_hash = models.CharField(max_length=100, db_index=True)
    original_trader_address = models.CharField(max_length=64)
    original_block = models.PositiveIntegerField(null=True, blank=True)
    
    # Copy trade details
    chain = models.CharField(max_length=20, db_index=True)
    dex = models.CharField(max_length=40)
    token_address = models.CharField(max_length=64, db_index=True)
    token_symbol = models.CharField(max_length=24, blank=True)
    action = models.CharField(max_length=10)  # "buy" or "sell"
    
    # Trade amounts and pricing
    original_amount_usd = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    copy_amount_usd = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    execution_price = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        null=True,
        blank=True
    )
    
    # Execution results
    status = models.CharField(
        max_length=20,
        choices=CopyStatus.choices,
        default=CopyStatus.PENDING,
        db_index=True
    )
    slippage_bps = models.IntegerField(null=True, blank=True)
    gas_fee_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Risk assessment
    risk_score = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Risk score from 0.0-10.0"
    )
    risk_reason = models.TextField(blank=True)
    
    # P&L tracking
    pnl_usd = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    is_profitable = models.BooleanField(null=True, blank=True)
    
    # Metadata
    is_paper = models.BooleanField(
        default=False,
        help_text="True if this was a paper trading copy"
    )
    trace_id = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "storage"  # FIXED: Added explicit app_label
        verbose_name = "Copy Trade"
        verbose_name_plural = "Copy Trades"
        db_table = "copy_trades"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['followed_trader', '-created_at']),
            models.Index(fields=['original_tx_hash']),
            models.Index(fields=['chain', 'token_address']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['is_paper', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"Copy {self.action} {self.token_symbol} for {self.followed_trader}"


class CopyTradeFilter(models.Model):
    """
    Advanced filtering rules for copy trading.
    Allows complex filtering logic beyond basic trader settings.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Filter metadata
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.PositiveIntegerField(
        default=100,
        help_text="Filter priority (lower = higher priority)"
    )
    
    # Liquidity filters
    min_liquidity_usd = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("10000.0")
    )
    
    # Token filters
    max_tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("5.0")
    )
    blacklisted_tokens = models.JSONField(default=list)
    whitelisted_tokens = models.JSONField(default=list)
    
    # Trade size filters
    min_trade_usd = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("100.0")
    )
    max_trade_usd = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("10000.0")
    )
    
    # Risk filters
    max_risk_score = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=Decimal("7.0")
    )
    require_verified_contract = models.BooleanField(default=True)
    
    # Trader quality filters
    min_trader_success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("60.0"),
        help_text="Minimum trader success rate percentage"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "storage"  # FIXED: Added explicit app_label
        verbose_name = "Copy Trade Filter"
        verbose_name_plural = "Copy Trade Filters"
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['is_active', 'priority']),
            models.Index(fields=['min_liquidity_usd']),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({'active' if self.is_active else 'inactive'})"