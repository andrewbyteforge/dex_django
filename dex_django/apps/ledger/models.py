from __future__ import annotations

from django.db import models
from django.utils import timezone  # Changed from datetime.timezone
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any

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