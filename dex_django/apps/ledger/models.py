# APP: backend
# FILE: dex_django/apps/ledger/models.py
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Dict, Any, Optional

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class Trade(models.Model):
    """Record of executed trades for portfolio tracking."""
    
    # Trade identification
    user_address = models.CharField(max_length=42, db_index=True)
    tx_hash = models.CharField(max_length=66, unique=True, null=True, blank=True)
    
    # Trade details
    chain = models.CharField(max_length=20, db_index=True)
    dex = models.CharField(max_length=30)
    token_in = models.CharField(max_length=42)
    token_out = models.CharField(max_length=42) 
    amount_in = models.DecimalField(max_digits=36, decimal_places=18)
    amount_out = models.DecimalField(max_digits=36, decimal_places=18, null=True)
    
    # Execution details
    gas_used = models.IntegerField(null=True)
    gas_price_gwei = models.DecimalField(max_digits=12, decimal_places=6, null=True)
    slippage_bps = models.IntegerField(null=True)
    execution_time_ms = models.IntegerField(null=True)
    
    # Status and metadata  
    is_paper = models.BooleanField(default=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)
    risk_warnings = models.JSONField(default=list)
    
    # Timestamps - FIXED
    executed_at = models.DateTimeField(default=timezone.now)  # Changed to timezone.now
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-executed_at']
        indexes = [
            models.Index(fields=['user_address', '-executed_at']),
            models.Index(fields=['chain', '-executed_at']),
            models.Index(fields=['is_paper', '-executed_at']),
        ]
    
    def __str__(self):
        return f"{self.amount_in} {self.token_in} -> {self.token_out} on {self.chain}"


class Position(models.Model):
    """Active positions for portfolio tracking."""
    
    user_address = models.CharField(max_length=42, db_index=True)
    token_address = models.CharField(max_length=42)
    chain = models.CharField(max_length=20)
    
    # Position details
    amount = models.DecimalField(max_digits=36, decimal_places=18)
    entry_price_usd = models.DecimalField(max_digits=18, decimal_places=8)
    current_price_usd = models.DecimalField(max_digits=18, decimal_places=8, null=True)
    
    # P&L tracking
    unrealized_pnl_usd = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    realized_pnl_usd = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    
    # Entry trade reference
    entry_trade = models.ForeignKey(Trade, on_delete=models.SET_NULL, null=True)
    
    # Status
    is_paper = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user_address', 'token_address', 'chain', 'is_paper']
        indexes = [
            models.Index(fields=['user_address', 'is_active']),
            models.Index(fields=['chain', 'is_active']),
        ]
    
    def calculate_pnl(self) -> Dict[str, Decimal]:
        """Calculate current P&L for this position."""
        if not self.current_price_usd or not self.entry_price_usd:
            return {"unrealized_pnl": Decimal(0), "pnl_percent": Decimal(0)}
        
        position_value = self.amount * self.current_price_usd
        cost_basis = self.amount * self.entry_price_usd
        unrealized_pnl = position_value - cost_basis
        pnl_percent = (unrealized_pnl / cost_basis) * 100 if cost_basis > 0 else Decimal(0)
        
        return {
            "unrealized_pnl": unrealized_pnl,
            "pnl_percent": pnl_percent,
            "position_value": position_value,
            "cost_basis": cost_basis
        }


class Portfolio(models.Model):
    """Portfolio summary for a user."""
    
    user_address = models.CharField(max_length=42, unique=True, db_index=True)
    
    # Portfolio totals
    total_value_usd = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    total_realized_pnl_usd = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    total_unrealized_pnl_usd = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    
    # Performance metrics
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    total_fees_paid_usd = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    
    # Risk metrics
    max_drawdown_pct = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    win_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    
    # Mode tracking
    is_paper = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def update_metrics(self):
        """Update portfolio metrics from trades."""
        trades = Trade.objects.filter(
            user_address=self.user_address,
            is_paper=self.is_paper,
            success=True
        )
        
        self.total_trades = trades.count()
        if self.total_trades > 0:
            # Calculate win rate (simplified)
            self.winning_trades = trades.filter(amount_out__gt=models.F('amount_in')).count()
            self.win_rate = Decimal(self.winning_trades) / Decimal(self.total_trades) * 100
        
        self.save()


# ============================================================================
# COPY TRADING MODELS - New models for copy trading functionality
# ============================================================================

class FollowedTrader(models.Model):
    """Model for traders being followed for copy trading."""
    
    # Primary identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet_address = models.CharField(max_length=42, db_index=True)
    trader_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    chain = models.CharField(max_length=20, default="ethereum")
    
    # Copy settings
    copy_mode = models.CharField(
        max_length=20, 
        choices=[
            ("percentage", "Percentage of Portfolio"),
            ("fixed", "Fixed Amount"),
            ("proportional", "Proportional to Original")
        ],
        default="percentage"
    )
    copy_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal("3.00"),
        validators=[MinValueValidator(Decimal("0.1")), MaxValueValidator(Decimal("50.0"))]
    )
    fixed_amount_usd = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(Decimal("10.0"))]
    )
    
    # Risk controls
    max_position_usd = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal("1000.00"),
        validators=[MinValueValidator(Decimal("50.0"))]
    )
    min_trade_value_usd = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=Decimal("50.00"),
        validators=[MinValueValidator(Decimal("10.0"))]
    )
    max_slippage_bps = models.IntegerField(
        default=300,
        validators=[MinValueValidator(50), MaxValueValidator(1000)]
    )
    
    # Trading filters
    allowed_chains = models.JSONField(default=list)
    copy_buy_only = models.BooleanField(default=False)
    copy_sell_only = models.BooleanField(default=False)
    
    # Status and control
    status = models.CharField(
        max_length=20,
        choices=[
            ("active", "Active"),
            ("paused", "Paused"), 
            ("blacklisted", "Blacklisted")
        ],
        default="active"
    )
    is_active = models.BooleanField(default=True)
    
    # Performance tracking (updated periodically)
    quality_score = models.IntegerField(null=True, blank=True)
    total_pnl_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    win_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    total_trades = models.IntegerField(default=0)
    avg_trade_size_usd = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    last_activity_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "ledger_followedtrader"
        unique_together = [["wallet_address", "chain"]]
        indexes = [
            models.Index(fields=["wallet_address"]),
            models.Index(fields=["chain", "status"]),
            models.Index(fields=["is_active", "status"]),
        ]
    
    def __str__(self) -> str:
        return f"{self.trader_name} ({self.wallet_address[:8]}...)"
    
    @property
    def short_address(self) -> str:
        """Get shortened address for display."""
        return f"{self.wallet_address[:6]}...{self.wallet_address[-4:]}"


class CopyTrade(models.Model):
    """Model for executed copy trades."""
    
    # Primary identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    followed_trader = models.ForeignKey(FollowedTrader, on_delete=models.CASCADE, related_name="copy_trades")
    
    # Original trade details
    original_tx_hash = models.CharField(max_length=66, db_index=True)
    chain = models.CharField(max_length=20)
    dex_name = models.CharField(max_length=50, null=True, blank=True)
    
    # Token information
    token_address = models.CharField(max_length=42, null=True, blank=True)
    token_symbol = models.CharField(max_length=20, null=True, blank=True)
    token_decimals = models.IntegerField(null=True, blank=True)
    
    # Trade details
    action = models.CharField(
        max_length=10,
        choices=[
            ("BUY", "Buy"),
            ("SELL", "Sell")
        ]
    )
    original_amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    copy_amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Execution details
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("executed", "Executed"),
            ("failed", "Failed"),
            ("skipped", "Skipped")
        ],
        default="pending"
    )
    copy_tx_hash = models.CharField(max_length=66, null=True, blank=True)
    execution_delay_seconds = models.IntegerField(null=True, blank=True)
    actual_slippage_bps = models.IntegerField(null=True, blank=True)
    gas_used = models.BigIntegerField(null=True, blank=True)
    gas_price_gwei = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Performance tracking
    entry_price_usd = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    current_price_usd = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    pnl_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    pnl_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("0.00"))
    
    # Risk and filtering
    risk_score = models.IntegerField(null=True, blank=True)
    skip_reason = models.CharField(max_length=200, null=True, blank=True)
    
    # Paper trading flag
    is_paper = models.BooleanField(default=False)
    
    # Timestamps
    original_trade_time = models.DateTimeField(null=True, blank=True)
    detected_at = models.DateTimeField(default=timezone.now)
    executed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "ledger_copytrade"
        indexes = [
            models.Index(fields=["followed_trader", "-created_at"]),
            models.Index(fields=["chain", "status"]),
            models.Index(fields=["original_tx_hash"]),
            models.Index(fields=["copy_tx_hash"]),
            models.Index(fields=["is_paper", "status"]),
        ]
    
    def __str__(self) -> str:
        return f"Copy {self.action} {self.token_symbol} - ${self.copy_amount_usd}"
    
    @property
    def is_profitable(self) -> bool:
        """Check if trade is currently profitable."""
        return self.pnl_usd > 0


class TraderCandidate(models.Model):
    """Model for discovered trader candidates from auto discovery."""
    
    # Primary identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet_address = models.CharField(max_length=42, db_index=True)
    chain = models.CharField(max_length=20)
    
    # Discovery metadata
    discovered_via = models.CharField(
        max_length=50,
        choices=[
            ("auto_discovery", "Auto Discovery"),
            ("manual_analysis", "Manual Analysis"),
            ("social_signal", "Social Signal"),
            ("performance_scan", "Performance Scan")
        ],
        default="auto_discovery"
    )
    discovery_run_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Analysis results
    quality_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    confidence_level = models.CharField(
        max_length=20,
        choices=[
            ("low", "Low"),
            ("medium", "Medium"), 
            ("high", "High")
        ],
        default="medium"
    )
    
    # Performance metrics
    total_volume_usd = models.DecimalField(max_digits=15, decimal_places=2)
    win_rate_pct = models.DecimalField(max_digits=5, decimal_places=2)
    total_trades = models.IntegerField()
    avg_trade_size_usd = models.DecimalField(max_digits=10, decimal_places=2)
    max_drawdown_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sharpe_ratio = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    
    # Risk assessment
    risk_level = models.CharField(
        max_length=20,
        choices=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High")
        ],
        default="medium"
    )
    risk_factors = models.JSONField(default=list)
    
    # Recommendations
    recommended_copy_pct = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.1")), MaxValueValidator(Decimal("10.0"))]
    )
    strengths = models.JSONField(default=list)
    weaknesses = models.JSONField(default=list)
    recommendation_text = models.TextField(null=True, blank=True)
    
    # Analysis period
    analysis_start_date = models.DateTimeField()
    analysis_end_date = models.DateTimeField()
    last_active_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ("candidate", "Candidate"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("following", "Following")
        ],
        default="candidate"
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "intelligence_tradercandidate"
        unique_together = [["wallet_address", "chain", "discovery_run_id"]]
        indexes = [
            models.Index(fields=["wallet_address", "chain"]),
            models.Index(fields=["quality_score", "-created_at"]),
            models.Index(fields=["status", "confidence_level"]),
        ]
    
    def __str__(self) -> str:
        return f"Candidate {self.wallet_address[:8]}... (Score: {self.quality_score})"
    
    @property
    def short_address(self) -> str:
        """Get shortened address for display."""
        return f"{self.wallet_address[:6]}...{self.wallet_address[-4:]}"


class WalletAnalysis(models.Model):
    """Model for storing detailed wallet analysis results."""
    
    # Primary identification  
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet_address = models.CharField(max_length=42, db_index=True)
    chain = models.CharField(max_length=20)
    
    # Analysis parameters
    analysis_type = models.CharField(
        max_length=30,
        choices=[
            ("discovery_scan", "Discovery Scan"),
            ("manual_request", "Manual Request"),
            ("periodic_update", "Periodic Update"),
            ("risk_assessment", "Risk Assessment")
        ]
    )
    days_analyzed = models.IntegerField()
    
    # Core metrics
    total_transactions = models.IntegerField()
    successful_transactions = models.IntegerField()
    total_volume_usd = models.DecimalField(max_digits=15, decimal_places=2)
    total_fees_usd = models.DecimalField(max_digits=10, decimal_places=2)
    net_pnl_usd = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Performance ratios
    win_rate_pct = models.DecimalField(max_digits=5, decimal_places=2)
    profit_factor = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    sharpe_ratio = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    max_drawdown_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Risk metrics
    risk_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    volatility_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    liquidity_risk = models.CharField(
        max_length=20,
        choices=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High")
        ]
    )
    
    # Token diversity
    unique_tokens_traded = models.IntegerField()
    top_tokens_concentration = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Trading patterns
    avg_position_size_usd = models.DecimalField(max_digits=10, decimal_places=2)
    avg_holding_period_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    trade_frequency_per_day = models.DecimalField(max_digits=6, decimal_places=2)
    
    # Analysis results stored as JSON for flexibility
    detailed_metrics = models.JSONField(default=dict)
    risk_factors = models.JSONField(default=list)
    strengths = models.JSONField(default=list)
    weaknesses = models.JSONField(default=list)
    
    # Recommendations
    overall_recommendation = models.CharField(
        max_length=20,
        choices=[
            ("avoid", "Avoid"),
            ("low_allocation", "Low Allocation"),
            ("moderate_allocation", "Moderate Allocation"),
            ("high_allocation", "High Allocation")
        ]
    )
    recommended_copy_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.0")), MaxValueValidator(Decimal("10.0"))]
    )
    confidence_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Analysis period
    analysis_start_date = models.DateTimeField()
    analysis_end_date = models.DateTimeField()
    
    # Status and metadata
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("expired", "Expired")
        ],
        default="pending"
    )
    error_message = models.TextField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "intelligence_walletanalysis"
        unique_together = [["wallet_address", "chain", "analysis_start_date"]]
        indexes = [
            models.Index(fields=["wallet_address", "chain"]),
            models.Index(fields=["risk_score", "-created_at"]),
            models.Index(fields=["status", "analysis_type"]),
            models.Index(fields=["overall_recommendation", "confidence_score"]),
        ]
    
    def __str__(self) -> str:
        return f"Analysis {self.wallet_address[:8]}... ({self.status})"
    
    @property
    def short_address(self) -> str:
        """Get shortened address for display."""
        return f"{self.wallet_address[:6]}...{self.wallet_address[-4:]}"
    
    def is_analysis_fresh(self, max_age_hours: int = 24) -> bool:
        """Check if analysis is still fresh based on age."""
        if not self.completed_at:
            return False
        
        from datetime import timedelta
        return (timezone.now() - self.completed_at) < timedelta(hours=max_age_hours)


class DiscoveryRun(models.Model):
    """Model for tracking auto discovery runs."""
    
    # Primary identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run_id = models.CharField(max_length=100, unique=True, db_index=True)
    
    # Discovery parameters
    chains = models.JSONField(default=list)
    min_volume_usd = models.DecimalField(max_digits=15, decimal_places=2)
    days_back = models.IntegerField()
    limit = models.IntegerField()
    auto_add_threshold = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Run status
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled")
        ],
        default="pending"
    )
    
    # Results
    total_candidates_found = models.IntegerField(default=0)
    high_quality_candidates = models.IntegerField(default=0)
    candidates_auto_added = models.IntegerField(default=0)
    
    # Performance tracking
    execution_time_seconds = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    
    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = "intelligence_discoveryrun"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["run_id"]),
        ]
    
    def __str__(self) -> str:
        return f"Discovery Run {self.run_id} ({self.status})"