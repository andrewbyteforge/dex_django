# APP: backend
# FILE: backend/app/storage/copy_trading_models.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column, String, Decimal as SQLDecimal, DateTime, Boolean, Text, Integer,
    Float, Index, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.sqlite import CHAR
import enum

Base = declarative_base()


class ChainType(enum.Enum):
    """Supported blockchain types."""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    BASE = "base"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    SOLANA = "solana"


class WalletStatus(enum.Enum):
    """Status of tracked wallet."""
    ACTIVE = "active"
    PAUSED = "paused"
    BLACKLISTED = "blacklisted"


class CopyMode(enum.Enum):
    """Copy trading mode."""
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount" 
    PROPORTIONAL = "proportional"


class CopyTradeStatus(enum.Enum):
    """Status of copy trade execution."""
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class TrackedWallet(Base):
    """Tracked wallets for copy trading."""
    __tablename__ = "tracked_wallets"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    address = Column(String(50), nullable=False, index=True)
    chain = Column(SQLEnum(ChainType), nullable=False, index=True)
    nickname = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SQLEnum(WalletStatus), nullable=False, default=WalletStatus.ACTIVE, index=True)
    
    # Copy settings
    copy_mode = Column(SQLEnum(CopyMode), nullable=False, default=CopyMode.PERCENTAGE)
    copy_percentage = Column(SQLDecimal(5, 2), nullable=False, default=Decimal("5.0"))
    fixed_amount_usd = Column(SQLDecimal(12, 2), nullable=True)
    
    # Risk controls
    max_position_usd = Column(SQLDecimal(12, 2), nullable=False, default=Decimal("1000.0"))
    min_trade_value_usd = Column(SQLDecimal(12, 2), nullable=False, default=Decimal("100.0"))
    max_slippage_bps = Column(Integer, nullable=False, default=300)
    
    # Restrictions
    allowed_chains = Column(String(200), nullable=True)  # JSON string of allowed chains
    copy_buy_only = Column(Boolean, nullable=False, default=False)
    copy_sell_only = Column(Boolean, nullable=False, default=False)
    
    # Performance tracking
    total_trades_copied = Column(Integer, nullable=False, default=0)
    successful_copies = Column(Integer, nullable=False, default=0)
    total_pnl_usd = Column(SQLDecimal(15, 2), nullable=False, default=Decimal("0.0"))
    win_rate = Column(Float, nullable=False, default=0.0)
    avg_profit_pct = Column(Float, nullable=False, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    detected_transactions = relationship("DetectedTransaction", back_populates="wallet", cascade="all, delete-orphan")
    copy_trades = relationship("CopyTrade", back_populates="wallet", cascade="all, delete-orphan")
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_tracked_wallets_address_chain', 'address', 'chain', unique=True),
        Index('idx_tracked_wallets_status', 'status'),
        Index('idx_tracked_wallets_created_at', 'created_at'),
    )


class DetectedTransaction(Base):
    """Transactions detected from tracked wallets."""
    __tablename__ = "detected_transactions"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tx_hash = Column(String(100), nullable=False, index=True, unique=True)
    wallet_id = Column(CHAR(36), ForeignKey('tracked_wallets.id'), nullable=False, index=True)
    
    # Transaction details
    block_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    chain = Column(SQLEnum(ChainType), nullable=False, index=True)
    
    # Token and DEX info
    token_address = Column(String(50), nullable=False, index=True)
    token_symbol = Column(String(24), nullable=True)
    token_name = Column(String(100), nullable=True)
    pair_address = Column(String(50), nullable=True)
    dex_name = Column(String(50), nullable=True, index=True)
    
    # Trade details
    action = Column(String(10), nullable=False, index=True)  # "buy", "sell"
    amount_token = Column(SQLDecimal(38, 18), nullable=False, default=Decimal("0"))
    amount_in = Column(SQLDecimal(38, 18), nullable=False, default=Decimal("0"))
    amount_out = Column(SQLDecimal(38, 18), nullable=False, default=Decimal("0"))
    amount_usd = Column(SQLDecimal(15, 2), nullable=False, default=Decimal("0"))
    gas_fee_usd = Column(SQLDecimal(10, 2), nullable=False, default=Decimal("0"))
    
    # Analysis metadata
    confidence_score = Column(Float, nullable=False, default=0.0)
    risk_flags = Column(Text, nullable=True)  # JSON string of risk flags
    slippage_bps = Column(Integer, nullable=True)
    
    # Processing status
    processed = Column(Boolean, nullable=False, default=False, index=True)
    copy_eligible = Column(Boolean, nullable=False, default=False, index=True)
    skip_reason = Column(String(200), nullable=True)
    
    # Timestamps
    detected_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    wallet = relationship("TrackedWallet", back_populates="detected_transactions")
    copy_trades = relationship("CopyTrade", back_populates="original_transaction")
    
    # Indexes
    __table_args__ = (
        Index('idx_detected_tx_wallet_timestamp', 'wallet_id', 'timestamp'),
        Index('idx_detected_tx_chain_action', 'chain', 'action'),
        Index('idx_detected_tx_token_dex', 'token_address', 'dex_name'),
        Index('idx_detected_tx_eligible', 'copy_eligible', 'processed'),
    )


class CopyTrade(Base):
    """Copy trades executed based on detected transactions."""
    __tablename__ = "copy_trades"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_id = Column(CHAR(36), ForeignKey('tracked_wallets.id'), nullable=False, index=True)
    original_tx_id = Column(CHAR(36), ForeignKey('detected_transactions.id'), nullable=False, index=True)
    
    # Copy trade identification
    copy_tx_hash = Column(String(100), nullable=True, index=True)
    trace_id = Column(String(50), nullable=False, index=True)
    
    # Copy configuration at time of trade
    copy_mode_used = Column(SQLEnum(CopyMode), nullable=False)
    copy_percentage_used = Column(SQLDecimal(5, 2), nullable=True)
    fixed_amount_used = Column(SQLDecimal(12, 2), nullable=True)
    
    # Trade details
    chain = Column(SQLEnum(ChainType), nullable=False, index=True)
    dex_name = Column(String(50), nullable=False)
    token_address = Column(String(50), nullable=False, index=True)
    token_symbol = Column(String(24), nullable=True)
    action = Column(String(10), nullable=False, index=True)  # "buy", "sell"
    
    # Amounts and pricing
    target_amount_usd = Column(SQLDecimal(15, 2), nullable=False)
    actual_amount_usd = Column(SQLDecimal(15, 2), nullable=True)
    amount_token = Column(SQLDecimal(38, 18), nullable=True)
    execution_price = Column(SQLDecimal(38, 18), nullable=True)
    
    # Slippage and fees
    target_slippage_bps = Column(Integer, nullable=False)
    actual_slippage_bps = Column(Integer, nullable=True)
    gas_fee_usd = Column(SQLDecimal(10, 2), nullable=True)
    dex_fee_usd = Column(SQLDecimal(10, 2), nullable=True)
    total_fees_usd = Column(SQLDecimal(10, 2), nullable=True)
    
    # Execution tracking
    status = Column(SQLEnum(CopyTradeStatus), nullable=False, default=CopyTradeStatus.PENDING, index=True)
    failure_reason = Column(Text, nullable=True)
    execution_delay_seconds = Column(Integer, nullable=True)
    
    # P&L tracking (for closed positions)
    entry_price = Column(SQLDecimal(38, 18), nullable=True)
    exit_price = Column(SQLDecimal(38, 18), nullable=True)
    pnl_usd = Column(SQLDecimal(15, 2), nullable=True)
    pnl_percentage = Column(Float, nullable=True)
    position_closed = Column(Boolean, nullable=False, default=False)
    
    # Risk assessment
    risk_score = Column(Float, nullable=True)
    risk_warnings = Column(Text, nullable=True)  # JSON string
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    executed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    wallet = relationship("TrackedWallet", back_populates="copy_trades")
    original_transaction = relationship("DetectedTransaction", back_populates="copy_trades")
    
    # Indexes
    __table_args__ = (
        Index('idx_copy_trades_wallet_status', 'wallet_id', 'status'),
        Index('idx_copy_trades_chain_action', 'chain', 'action'),
        Index('idx_copy_trades_token_created', 'token_address', 'created_at'),
        Index('idx_copy_trades_pnl', 'pnl_usd'),
        Index('idx_copy_trades_execution_time', 'executed_at'),
    )


class CopyTradingMetrics(Base):
    """Daily aggregated metrics for copy trading performance."""
    __tablename__ = "copy_trading_metrics"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    wallet_id = Column(CHAR(36), ForeignKey('tracked_wallets.id'), nullable=True, index=True)  # NULL = global metrics
    
    # Volume metrics
    total_trades = Column(Integer, nullable=False, default=0)
    successful_trades = Column(Integer, nullable=False, default=0)
    failed_trades = Column(Integer, nullable=False, default=0)
    skipped_opportunities = Column(Integer, nullable=False, default=0)
    
    # Financial metrics
    total_volume_usd = Column(SQLDecimal(15, 2), nullable=False, default=Decimal("0"))
    total_fees_usd = Column(SQLDecimal(12, 2), nullable=False, default=Decimal("0"))
    realized_pnl_usd = Column(SQLDecimal(15, 2), nullable=False, default=Decimal("0"))
    unrealized_pnl_usd = Column(SQLDecimal(15, 2), nullable=False, default=Decimal("0"))
    
    # Performance ratios
    win_rate = Column(Float, nullable=False, default=0.0)
    avg_profit_pct = Column(Float, nullable=False, default=0.0)
    avg_loss_pct = Column(Float, nullable=False, default=0.0)
    profit_factor = Column(Float, nullable=False, default=0.0)  # Total profit / Total loss
    
    # Execution metrics
    avg_execution_delay_seconds = Column(Float, nullable=False, default=0.0)
    avg_slippage_bps = Column(Float, nullable=False, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    wallet = relationship("TrackedWallet", foreign_keys=[wallet_id])
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_copy_metrics_date_wallet', 'date', 'wallet_id', unique=True),
        Index('idx_copy_metrics_date', 'date'),
        Index('idx_copy_metrics_pnl', 'realized_pnl_usd'),
    )


class WalletPerformanceSnapshot(Base):
    """Periodic snapshots of wallet performance for historical analysis."""
    __tablename__ = "wallet_performance_snapshots"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_id = Column(CHAR(36), ForeignKey('tracked_wallets.id'), nullable=False, index=True)
    
    # Snapshot metadata
    snapshot_date = Column(DateTime(timezone=True), nullable=False, index=True)
    period_type = Column(String(20), nullable=False, index=True)  # "daily", "weekly", "monthly"
    
    # Portfolio composition
    total_positions = Column(Integer, nullable=False, default=0)
    active_positions = Column(Integer, nullable=False, default=0)
    total_portfolio_value_usd = Column(SQLDecimal(15, 2), nullable=False, default=Decimal("0"))
    
    # Trading activity
    trades_count = Column(Integer, nullable=False, default=0)
    volume_usd = Column(SQLDecimal(15, 2), nullable=False, default=Decimal("0"))
    unique_tokens_traded = Column(Integer, nullable=False, default=0)
    
    # Performance metrics
    period_pnl_usd = Column(SQLDecimal(15, 2), nullable=False, default=Decimal("0"))
    period_pnl_percentage = Column(Float, nullable=False, default=0.0)
    win_rate = Column(Float, nullable=False, default=0.0)
    best_trade_pnl_usd = Column(SQLDecimal(15, 2), nullable=True)
    worst_trade_pnl_usd = Column(SQLDecimal(15, 2), nullable=True)
    
    # Risk metrics
    max_drawdown_usd = Column(SQLDecimal(15, 2), nullable=True)
    max_drawdown_percentage = Column(Float, nullable=True)
    volatility = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    
    # Copy trading specific
    copy_accuracy = Column(Float, nullable=False, default=0.0)  # How well we copied their trades
    detection_speed_seconds = Column(Float, nullable=False, default=0.0)  # Avg detection delay
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    wallet = relationship("TrackedWallet", foreign_keys=[wallet_id])
    
    # Indexes
    __table_args__ = (
        Index('idx_wallet_snapshots_date_period', 'snapshot_date', 'period_type'),
        Index('idx_wallet_snapshots_wallet_date', 'wallet_id', 'snapshot_date'),
        Index('idx_wallet_snapshots_pnl', 'period_pnl_usd'),
    )


# Helper functions for database operations
def create_wallet_key(address: str, chain: ChainType) -> str:
    """Create unique wallet key from address and chain."""
    return f"{chain.value}:{address.lower()}"


def parse_wallet_key(wallet_key: str) -> tuple[str, ChainType]:
    """Parse wallet key into address and chain."""
    chain_str, address = wallet_key.split(":", 1)
    return address, ChainType(chain_str)