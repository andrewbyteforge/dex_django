# ADD THESE LINES TO THE TOP OF YOUR EXISTING models.py FILE
# Right after the existing imports

import uuid
from datetime import datetime, timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# ADD THESE CLASSES TO THE END OF YOUR EXISTING models.py FILE
# After the existing LedgerEntry class

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
        validators=[MinValueValidator(Decimal("50.0"))],
        help_text="Maximum position size in USD"
    )
    max_slippage_bps = models.PositiveIntegerField(
        default=300,
        validators=[MinValueValidator(50), MaxValueValidator(1000)],
        help_text="Maximum slippage in basis points"
    )
    max_risk_score = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=Decimal("7.0"),
        validators=[MinValueValidator(Decimal("1.0")), MaxValueValidator(Decimal("10.0"))],
        help_text="Maximum risk score threshold (1.0-10.0)"
    )
    
    # Chain and token restrictions
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
    
    # Time and direction restrictions
    copy_buy_only = models.BooleanField(default=False)
    copy_sell_only = models.BooleanField(default=False)
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
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "copy_followed_traders"
        ordering = ["-created_at"]
        verbose_name = "Followed Trader"
        verbose_name_plural = "Followed Traders"
    
    def __str__(self) -> str:
        name = self.trader_name or f"{self.wallet_address[:8]}..."
        return f"{name} ({self.get_status_display()})"
    
    @property
    def win_rate_pct(self) -> float:
        """Calculate win rate percentage."""
        if self.total_copies == 0:
            return 0.0
        return (self.successful_copies / self.total_copies) * 100
    
    @property
    def short_address(self) -> str:
        """Get shortened wallet address for display."""
        return f"{self.wallet_address[:8]}...{self.wallet_address[-4:]}"
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = datetime.now(timezone.utc)
        self.save(update_fields=["last_activity_at"])
    
    def increment_copy_stats(self, pnl_usd: Decimal, is_successful: bool) -> None:
        """Update copy trading statistics."""
        self.total_copies += 1
        if is_successful:
            self.successful_copies += 1
        self.total_pnl_usd += pnl_usd
        self.save(update_fields=["total_copies", "successful_copies", "total_pnl_usd"])


class CopyTrade(models.Model):
    """
    Record of copy trade attempts and results.
    Links to existing LedgerEntry for audit trail.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    followed_trader = models.ForeignKey(
        FollowedTrader,
        on_delete=models.CASCADE,
        related_name="copy_trades"
    )
    # Link to LedgerEntry if trade was executed
    ledger_entry = models.ForeignKey(
        'LedgerEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="copy_trades"
    )
    # Link to original Trade if executed
    trade = models.ForeignKey(
        'Trade',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="copy_trades"
    )
    
    # Original trade details
    original_tx_hash = models.CharField(max_length=128, db_index=True)
    original_block_number = models.BigIntegerField()
    original_timestamp = models.DateTimeField()
    
    # Trade details
    chain = models.CharField(max_length=20)
    dex_name = models.CharField(max_length=50)
    token_address = models.CharField(max_length=64)
    token_symbol = models.CharField(max_length=20, blank=True)
    pair_address = models.CharField(max_length=64, blank=True)
    
    # Trade amounts (original)
    original_amount_in = models.DecimalField(max_digits=38, decimal_places=18)
    original_amount_out = models.DecimalField(max_digits=38, decimal_places=18)
    original_amount_usd = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Copy trade configuration
    copy_amount_usd = models.DecimalField(max_digits=15, decimal_places=2)
    copy_amount_in = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        null=True,
        blank=True
    )
    copy_amount_out = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        null=True,
        blank=True
    )
    
    # Execution details
    status = models.CharField(
        max_length=20,
        choices=CopyStatus.choices,
        default=CopyStatus.PENDING,
        db_index=True
    )
    copy_tx_hash = models.CharField(max_length=128, blank=True)
    copy_block_number = models.BigIntegerField(null=True, blank=True)
    
    # Slippage and timing
    execution_delay_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Delay between original tx and copy attempt"
    )
    realized_slippage_bps = models.IntegerField(null=True, blank=True)
    
    # Gas and fees
    gas_used = models.BigIntegerField(null=True, blank=True)
    gas_price_gwei = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    total_fees_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Risk checks
    risk_score = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Risk score from 0.0-10.0"
    )
    risk_reason = models.TextField(blank=True)
    
    # Result tracking
    pnl_usd = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    is_profitable = models.BooleanField(null=True, blank=True)
    
    # Copy trading specific flags
    is_paper = models.BooleanField(
        default=False,
        help_text="True if this was a paper trading copy"
    )
    
    # Metadata
    trace_id = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "copy_trades"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["followed_trader", "-created_at"]),
            models.Index(fields=["original_tx_hash"]),
            models.Index(fields=["chain", "token_address"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["is_paper", "-created_at"]),
        ]
        verbose_name = "Copy Trade"
        verbose_name_plural = "Copy Trades"
    
    def __str__(self) -> str:
        symbol = self.token_symbol or self.token_address[:8]
        paper_flag = " [PAPER]" if self.is_paper else ""
        return f"Copy {symbol} - {self.get_status_display()} (${self.copy_amount_usd}){paper_flag}"
    
    @property
    def success_display(self) -> str:
        """Display-friendly success indicator."""
        if self.status == CopyStatus.EXECUTED:
            return "✅ Executed"
        elif self.status == CopyStatus.FAILED:
            return "❌ Failed"
        elif self.status == CopyStatus.SKIPPED:
            return "⏭️ Skipped"
        else:
            return "⏳ Pending"


class CopyTradeFilter(models.Model):
    """
    Global filters to control which trades get copied.
    Can be applied across all followed traders.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Filter identification
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.PositiveIntegerField(
        default=100,
        help_text="Filter priority (lower = higher priority)"
    )
    
    # Token filters
    min_liquidity_usd = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("10000.0")
    )
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
    
    # Chain and DEX filters
    allowed_chains = models.JSONField(
        default=lambda: ["ethereum", "bsc", "base"]
    )
    allowed_dexes = models.JSONField(
        default=lambda: ["uniswap_v2", "uniswap_v3", "pancake_v2"]
    )
    
    # Performance filters
    min_trader_success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("60.0"),
        help_text="Minimum trader success rate percentage"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "copy_trade_filters"
        ordering = ["priority", "-created_at"]
        verbose_name = "Copy Trade Filter"
        verbose_name_plural = "Copy Trade Filters"
    
    def __str__(self) -> str:
        status = "🟢 Active" if self.is_active else "🔴 Inactive"
        return f"{self.name} - {status}"