# APP: backend/app/services
# FILE: backend/app/services/copy_trading_service.py
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger("services.copy_trading")


class TraderRecord(BaseModel):
    """Trader record with copy settings."""
    
    id: str
    wallet_address: str
    trader_name: Optional[str]
    description: Optional[str]
    chain: str
    
    # Copy settings
    copy_mode: str = "percentage"
    copy_percentage: Decimal = Decimal("5.0")
    fixed_amount_usd: Optional[Decimal] = None
    max_position_usd: Decimal = Decimal("1000.0")
    min_trade_value_usd: Decimal = Decimal("100.0")
    max_slippage_bps: int = 300
    
    # Filters
    allowed_chains: List[str] = Field(default_factory=lambda: ["ethereum", "bsc", "base"])
    copy_buy_only: bool = False
    copy_sell_only: bool = False
    
    # Status
    is_active: bool = True
    monitoring_active: bool = False
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }


class CopyTradingServiceStatus(BaseModel):
    """Copy trading service status."""
    
    is_enabled: bool
    monitoring_active: bool
    followed_traders_count: int
    active_monitoring_count: int
    paper_mode: bool
    
    # Statistics
    trades_today: int = 0
    total_trades: int = 0
    success_rate: float = 0.0
    total_pnl_usd: Decimal = Decimal("0.0")
    
    class Config:
        json_encoders = {
            Decimal: str,
        }


class CopyTradingService:
    """
    Central orchestrator for copy trading system.
    
    Coordinates between:
    - Database storage (trader records)
    - Wallet monitoring (transaction detection)
    - Strategy evaluation (copy decisions)
    - WebSocket broadcasting (real-time updates)
    - Trade execution (paper/live modes)
    """
    
    def __init__(self):
        self._is_running = False
        self._followed_traders: Dict[str, TraderRecord] = {}
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        
        # Component references (will be injected)
        self._wallet_monitor = None
        self._copy_strategy = None
        self._websocket_hub = None
        self._database = None
        
        # Service state
        self._paper_mode = True
        self._daily_stats = {
            "trades_executed": 0,
            "trades_successful": 0,
            "total_pnl_usd": Decimal("0.0"),
            "last_reset": datetime.now(timezone.utc).date()
        }
    
    async def initialize(
        self,
        wallet_monitor=None,
        copy_strategy=None,
        websocket_hub=None,
        database=None
    ) -> None:
        """Initialize the service with component dependencies."""
        logger.info("Initializing CopyTradingService")
        
        self._wallet_monitor = wallet_monitor
        self._copy_strategy = copy_strategy
        self._websocket_hub = websocket_hub
        self._database = database
        
        # Load existing traders from database if available
        if self._database:
            await self._load_traders_from_database()
        
        logger.info("CopyTradingService initialized with %d traders", 
                   len(self._followed_traders))
    
    async def start_service(self) -> Dict[str, Any]:
        """Start the copy trading service."""
        if self._is_running:
            return {"success": False, "message": "Service already running"}
        
        try:
            logger.info("Starting CopyTradingService")
            self._is_running = True
            
            # Start monitoring for active traders
            active_traders = [t for t in self._followed_traders.values() if t.is_active]
            
            if active_traders:
                await self._start_monitoring_traders(active_traders)
            
            # Emit status update
            await self._emit_status_update("service_started")
            
            return {
                "success": True,
                "message": f"Copy trading service started with {len(active_traders)} active traders"
            }
            
        except Exception as e:
            logger.error(f"Failed to start copy trading service: {e}")
            self._is_running = False
            return {"success": False, "message": str(e)}
    
    async def stop_service(self) -> Dict[str, Any]:
        """Stop the copy trading service."""
        if not self._is_running:
            return {"success": False, "message": "Service not running"}
        
        try:
            logger.info("Stopping CopyTradingService")
            self._is_running = False
            
            # Stop all monitoring tasks
            await self._stop_all_monitoring()
            
            # Emit status update
            await self._emit_status_update("service_stopped")
            
            return {"success": True, "message": "Copy trading service stopped"}
            
        except Exception as e:
            logger.error(f"Failed to stop copy trading service: {e}")
            return {"success": False, "message": str(e)}
    
    async def add_trader(
        self,
        wallet_address: str,
        trader_name: Optional[str] = None,
        description: Optional[str] = None,
        chain: str = "ethereum",
        copy_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a new trader to follow and start monitoring.
        
        This is the main integration point called from API endpoints.
        """
        try:
            wallet_address = wallet_address.lower()
            trader_key = f"{chain}:{wallet_address}"
            
            # Check if already following
            if trader_key in self._followed_traders:
                return {
                    "success": False,
                    "message": "Trader is already being followed",
                    "trader_id": trader_key
                }
            
            # Create trader record
            trader_record = self._create_trader_record(
                wallet_address=wallet_address,
                trader_name=trader_name,
                description=description,
                chain=chain,
                copy_settings=copy_settings or {}
            )
            
            # Save to database if available
            if self._database:
                await self._save_trader_to_database(trader_record)
            
            # Add to in-memory storage
            self._followed_traders[trader_key] = trader_record
            
            # Start monitoring if service is running
            if self._is_running and trader_record.is_active:
                await self._start_monitoring_single_trader(trader_record)
            
            # Emit updates
            await self._emit_trader_added(trader_record)
            await self._emit_status_update("trader_added")
            
            logger.info("Added trader %s (%s) on %s", 
                       wallet_address[:8], trader_name or "Unknown", chain)
            
            return {
                "success": True,
                "message": f"Started monitoring trader {wallet_address[:8]}... on {chain}",
                "trader": trader_record.dict(),
                "monitoring_active": trader_record.monitoring_active
            }
            
        except Exception as e:
            logger.error(f"Failed to add trader {wallet_address}: {e}")
            return {"success": False, "message": str(e)}
    
    async def remove_trader(self, trader_key: str) -> Dict[str, Any]:
        """Remove a trader and stop monitoring."""
        try:
            if trader_key not in self._followed_traders:
                return {"success": False, "message": "Trader not found"}
            
            trader_record = self._followed_traders[trader_key]
            
            # Stop monitoring
            await self._stop_monitoring_single_trader(trader_key)
            
            # Remove from database
            if self._database:
                await self._remove_trader_from_database(trader_record.id)
            
            # Remove from memory
            del self._followed_traders[trader_key]
            
            # Emit updates
            await self._emit_trader_removed(trader_record)
            await self._emit_status_update("trader_removed")
            
            logger.info("Removed trader %s", trader_record.wallet_address[:8])
            
            return {
                "success": True,
                "message": f"Stopped monitoring trader {trader_record.wallet_address[:8]}..."
            }
            
        except Exception as e:
            logger.error(f"Failed to remove trader {trader_key}: {e}")
            return {"success": False, "message": str(e)}
    
    async def get_service_status(self) -> CopyTradingServiceStatus:
        """Get comprehensive service status."""
        self._reset_daily_stats_if_needed()
        
        active_traders = [t for t in self._followed_traders.values() if t.is_active]
        monitoring_count = len([t for t in active_traders if t.monitoring_active])
        
        return CopyTradingServiceStatus(
            is_enabled=self._is_running,
            monitoring_active=monitoring_count > 0,
            followed_traders_count=len(self._followed_traders),
            active_monitoring_count=monitoring_count,
            paper_mode=self._paper_mode,
            trades_today=self._daily_stats["trades_executed"],
            total_trades=self._daily_stats["trades_executed"],  # Would track historically
            success_rate=self._calculate_success_rate(),
            total_pnl_usd=self._daily_stats["total_pnl_usd"]
        )
    
    async def get_followed_traders(self) -> List[TraderRecord]:
        """Get all followed traders."""
        return list(self._followed_traders.values())
    
    async def set_paper_mode(self, enabled: bool) -> None:
        """Set paper trading mode."""
        self._paper_mode = enabled
        await self._emit_status_update("paper_mode_changed")
        logger.info("Paper mode set to %s", enabled)
    
    def is_paper_mode(self) -> bool:
        """Check if in paper mode."""
        return self._paper_mode
    
    # ---------- PRIVATE METHODS ----------
    
    def _create_trader_record(
        self,
        wallet_address: str,
        trader_name: Optional[str],
        description: Optional[str],
        chain: str,
        copy_settings: Dict[str, Any]
    ) -> TraderRecord:
        """Create a trader record with default settings."""
        now = datetime.now(timezone.utc)
        trader_id = str(uuid4())
        
        return TraderRecord(
            id=trader_id,
            wallet_address=wallet_address,
            trader_name=trader_name or f"Trader_{wallet_address[-4:]}",
            description=description,
            chain=chain,
            copy_mode=copy_settings.get("copy_mode", "percentage"),
            copy_percentage=Decimal(str(copy_settings.get("copy_percentage", 5.0))),
            fixed_amount_usd=Decimal(str(copy_settings.get("fixed_amount_usd", 100))) 
                if copy_settings.get("fixed_amount_usd") else None,
            max_position_usd=Decimal(str(copy_settings.get("max_position_usd", 1000))),
            min_trade_value_usd=Decimal(str(copy_settings.get("min_trade_value_usd", 100))),
            max_slippage_bps=copy_settings.get("max_slippage_bps", 300),
            allowed_chains=copy_settings.get("allowed_chains", [chain]),
            copy_buy_only=copy_settings.get("copy_buy_only", False),
            copy_sell_only=copy_settings.get("copy_sell_only", False),
            created_at=now,
            updated_at=now
        )
    
    async def _start_monitoring_traders(self, traders: List[TraderRecord]) -> None:
        """Start monitoring multiple traders."""
        if not self._wallet_monitor:
            logger.warning("Wallet monitor not available - cannot start monitoring")
            return
        
        wallet_addresses = [t.wallet_address for t in traders]
        
        try:
            await self._wallet_monitor.start_monitoring(wallet_addresses)
            
            # Mark traders as monitoring active
            for trader in traders:
                trader.monitoring_active = True
            
            logger.info("Started monitoring %d traders", len(traders))
            
        except Exception as e:
            logger.error(f"Failed to start wallet monitoring: {e}")
    
    async def _start_monitoring_single_trader(self, trader: TraderRecord) -> None:
        """Start monitoring a single trader."""
        if not self._wallet_monitor:
            logger.warning("Wallet monitor not available")
            return
        
        try:
            # For single trader, we might need to add to existing monitoring
            # This depends on wallet_monitor implementation
            await self._wallet_monitor.start_monitoring([trader.wallet_address])
            trader.monitoring_active = True
            
            logger.info("Started monitoring trader %s on %s", 
                       trader.wallet_address[:8], trader.chain)
            
        except Exception as e:
            logger.error(f"Failed to start monitoring trader {trader.wallet_address}: {e}")
    
    async def _stop_monitoring_single_trader(self, trader_key: str) -> None:
        """Stop monitoring a single trader."""
        if trader_key in self._monitoring_tasks:
            task = self._monitoring_tasks[trader_key]
            task.cancel()
            del self._monitoring_tasks[trader_key]
        
        if trader_key in self._followed_traders:
            self._followed_traders[trader_key].monitoring_active = False
    
    async def _stop_all_monitoring(self) -> None:
        """Stop all monitoring tasks."""
        if self._wallet_monitor:
            try:
                await self._wallet_monitor.stop_monitoring()
            except Exception as e:
                logger.error(f"Failed to stop wallet monitor: {e}")
        
        # Cancel all individual tasks
        for task in self._monitoring_tasks.values():
            task.cancel()
        self._monitoring_tasks.clear()
        
        # Mark all traders as not monitoring
        for trader in self._followed_traders.values():
            trader.monitoring_active = False
    
    async def _emit_trader_added(self, trader: TraderRecord) -> None:
        """Emit trader added event to WebSocket."""
        if not self._websocket_hub:
            return
        
        try:
            await self._websocket_hub.broadcast_trader_activity(
                trader.wallet_address,
                {
                    "event": "trader_added",
                    "trader_name": trader.trader_name,
                    "chain": trader.chain,
                    "copy_percentage": float(trader.copy_percentage),
                    "monitoring_active": trader.monitoring_active
                }
            )
        except Exception as e:
            logger.error(f"Failed to emit trader added event: {e}")
    
    async def _emit_trader_removed(self, trader: TraderRecord) -> None:
        """Emit trader removed event to WebSocket."""
        if not self._websocket_hub:
            return
        
        try:
            await self._websocket_hub.broadcast_trader_activity(
                trader.wallet_address,
                {
                    "event": "trader_removed",
                    "trader_name": trader.trader_name,
                    "chain": trader.chain
                }
            )
        except Exception as e:
            logger.error(f"Failed to emit trader removed event: {e}")
    
    async def _emit_status_update(self, event: str) -> None:
        """Emit status update to WebSocket."""
        if not self._websocket_hub:
            return
        
        try:
            status = await self.get_service_status()
            await self._websocket_hub.broadcast_copy_trading_status({
                "event": event,
                "status": status.dict(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to emit status update: {e}")
    
    def _calculate_success_rate(self) -> float:
        """Calculate current success rate."""
        if self._daily_stats["trades_executed"] == 0:
            return 0.0
        return (self._daily_stats["trades_successful"] / self._daily_stats["trades_executed"]) * 100
    
    def _reset_daily_stats_if_needed(self) -> None:
        """Reset daily stats if date changed."""
        today = datetime.now(timezone.utc).date()
        if self._daily_stats["last_reset"] != today:
            self._daily_stats = {
                "trades_executed": 0,
                "trades_successful": 0,
                "total_pnl_usd": Decimal("0.0"),
                "last_reset": today
            }
    
    async def _load_traders_from_database(self) -> None:
        """Load existing traders from database."""
        # Placeholder - would integrate with actual database
        logger.info("Loading traders from database (placeholder)")
    
    async def _save_trader_to_database(self, trader: TraderRecord) -> None:
        """Save trader to database."""
        # Placeholder - would integrate with actual database
        logger.info("Saving trader %s to database (placeholder)", trader.wallet_address[:8])
    
    async def _remove_trader_from_database(self, trader_id: str) -> None:
        """Remove trader from database."""
        # Placeholder - would integrate with actual database
        logger.info("Removing trader %s from database (placeholder)", trader_id)


# Global service instance
copy_trading_service = CopyTradingService()