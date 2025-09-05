# APP: dex_django/apps/strategy
# FILE: orders.py
"""
Order Management System for DEX Sniper Pro Copy Trading

Handles order creation, execution, tracking, and management for copy trading operations.
Supports both paper trading and live execution modes.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("strategy.orders")


class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    FAILED = "failed"
    EXPIRED = "expired"


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class OrderRequest:
    """Request to create a new order."""
    pair_address: str
    chain: str
    side: OrderSide
    order_type: OrderType
    amount_usd: Decimal
    token_address: str
    token_symbol: str
    dex_name: str
    
    # Optional parameters
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    slippage_tolerance_bps: int = 300
    gas_limit: Optional[int] = None
    gas_price_gwei: Optional[Decimal] = None
    
    # Copy trading specific
    original_tx_hash: Optional[str] = None
    trader_address: Optional[str] = None
    copy_percentage: Optional[Decimal] = None
    
    # Risk management
    max_slippage_bps: int = 500
    timeout_seconds: int = 300
    
    # Metadata
    notes: str = ""
    is_paper: bool = False


@dataclass
class OrderFill:
    """Information about an order fill."""
    fill_id: str
    order_id: str
    filled_amount_usd: Decimal
    fill_price: Decimal
    timestamp: datetime
    tx_hash: Optional[str] = None
    gas_used: Optional[int] = None
    gas_price_gwei: Optional[Decimal] = None
    fees_usd: Optional[Decimal] = None


@dataclass
class Order:
    """Order representation with full lifecycle tracking."""
    order_id: str
    request: OrderRequest
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    
    # Execution details
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    
    # Fill information
    filled_amount_usd: Decimal = Decimal("0")
    average_fill_price: Optional[Decimal] = None
    fills: List[OrderFill] = None
    
    # Transaction details
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    
    # Fees and costs
    total_fees_usd: Decimal = Decimal("0")
    gas_cost_usd: Decimal = Decimal("0")
    realized_slippage_bps: Optional[int] = None
    
    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def __post_init__(self):
        if self.fills is None:
            self.fills = []
    
    @property
    def is_complete(self) -> bool:
        """Check if order is completely filled."""
        return self.status == OrderStatus.FILLED
    
    @property
    def is_active(self) -> bool:
        """Check if order is still active."""
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]
    
    @property
    def fill_percentage(self) -> Decimal:
        """Calculate fill percentage."""
        if self.request.amount_usd == 0:
            return Decimal("0")
        return (self.filled_amount_usd / self.request.amount_usd) * 100


class OrderManager:
    """
    Order management system for copy trading.
    
    Handles order lifecycle from creation through execution and settlement.
    Supports both paper trading and live execution modes.
    """
    
    def __init__(self):
        self.active_orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []
        self.paper_mode = True  # Default to paper mode for safety
        
        # Order tracking
        self.daily_order_count = 0
        self.daily_volume_usd = Decimal("0")
        self.success_rate = Decimal("0")
        
        logger.info("OrderManager initialized in paper mode")
    
    async def create_order(self, request: OrderRequest) -> Order:
        """
        Create a new order from request.
        
        Args:
            request: OrderRequest with all order details
            
        Returns:
            Created Order object
        """
        order_id = f"ord_{uuid.uuid4().hex[:8]}"
        
        # Validate request
        validation_result = await self._validate_order_request(request)
        if not validation_result["valid"]:
            raise ValueError(f"Invalid order request: {validation_result['reason']}")
        
        # Create order
        order = Order(
            order_id=order_id,
            request=request,
            status=OrderStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Add to active orders
        self.active_orders[order_id] = order
        
        logger.info(f"Created order {order_id}: {request.side.value} {request.token_symbol} for ${request.amount_usd}")
        
        return order
    
    async def submit_order(self, order_id: str) -> bool:
        """
        Submit order for execution.
        
        Args:
            order_id: Order ID to submit
            
        Returns:
            True if submission successful
        """
        order = self.active_orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        if order.status != OrderStatus.PENDING:
            raise ValueError(f"Order {order_id} is not pending (status: {order.status.value})")
        
        try:
            # Update status
            order.status = OrderStatus.SUBMITTED
            order.submitted_at = datetime.now(timezone.utc)
            order.updated_at = datetime.now(timezone.utc)
            
            # Submit based on mode
            if self.paper_mode or order.request.is_paper:
                success = await self._submit_paper_order(order)
            else:
                success = await self._submit_live_order(order)
            
            if success:
                logger.info(f"Order {order_id} submitted successfully")
                
                # Start execution monitoring
                asyncio.create_task(self._monitor_order_execution(order_id))
                
            return success
            
        except Exception as e:
            order.status = OrderStatus.FAILED
            order.error_message = str(e)
            order.updated_at = datetime.now(timezone.utc)
            
            logger.error(f"Failed to submit order {order_id}: {e}")
            return False
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an active order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancellation successful
        """
        order = self.active_orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        if not order.is_active:
            logger.warning(f"Order {order_id} is not active (status: {order.status.value})")
            return False
        
        try:
            # Cancel based on mode
            if self.paper_mode or order.request.is_paper:
                success = await self._cancel_paper_order(order)
            else:
                success = await self._cancel_live_order(order)
            
            if success:
                order.status = OrderStatus.CANCELLED
                order.cancelled_at = datetime.now(timezone.utc)
                order.updated_at = datetime.now(timezone.utc)
                
                logger.info(f"Order {order_id} cancelled")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.active_orders.get(order_id)
    
    async def get_active_orders(
        self, 
        chain: Optional[str] = None,
        trader_address: Optional[str] = None
    ) -> List[Order]:
        """
        Get active orders with optional filtering.
        
        Args:
            chain: Filter by chain
            trader_address: Filter by trader address
            
        Returns:
            List of active orders
        """
        orders = list(self.active_orders.values())
        
        if chain:
            orders = [o for o in orders if o.request.chain == chain]
        
        if trader_address:
            orders = [o for o in orders if o.request.trader_address == trader_address]
        
        return orders
    
    async def get_order_history(
        self, 
        limit: int = 100,
        chain: Optional[str] = None
    ) -> List[Order]:
        """
        Get order history with optional filtering.
        
        Args:
            limit: Maximum number of orders to return
            chain: Filter by chain
            
        Returns:
            List of historical orders
        """
        orders = self.order_history.copy()
        
        if chain:
            orders = [o for o in orders if o.request.chain == chain]
        
        # Sort by created_at descending
        orders.sort(key=lambda x: x.created_at, reverse=True)
        
        return orders[:limit]
    
    def set_paper_mode(self, enabled: bool) -> None:
        """Enable or disable paper trading mode."""
        self.paper_mode = enabled
        mode_text = "paper" if enabled else "live"
        logger.info(f"OrderManager set to {mode_text} mode")
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get order execution statistics."""
        all_orders = list(self.active_orders.values()) + self.order_history
        
        if not all_orders:
            return {
                "total_orders": 0,
                "success_rate": 0.0,
                "total_volume_usd": 0.0,
                "average_fill_time_seconds": 0.0,
                "active_orders": 0
            }
        
        filled_orders = [o for o in all_orders if o.status == OrderStatus.FILLED]
        failed_orders = [o for o in all_orders if o.status == OrderStatus.FAILED]
        
        # Calculate fill times
        fill_times = []
        for order in filled_orders:
            if order.submitted_at and order.filled_at:
                fill_time = (order.filled_at - order.submitted_at).total_seconds()
                fill_times.append(fill_time)
        
        avg_fill_time = sum(fill_times) / len(fill_times) if fill_times else 0.0
        
        return {
            "total_orders": len(all_orders),
            "filled_orders": len(filled_orders),
            "failed_orders": len(failed_orders),
            "success_rate": len(filled_orders) / len(all_orders) * 100 if all_orders else 0.0,
            "total_volume_usd": float(sum(o.filled_amount_usd for o in filled_orders)),
            "average_fill_time_seconds": avg_fill_time,
            "active_orders": len(self.active_orders)
        }
    
    # Private methods
    
    async def _validate_order_request(self, request: OrderRequest) -> Dict[str, Any]:
        """Validate order request parameters."""
        
        # Basic validation
        if request.amount_usd <= 0:
            return {"valid": False, "reason": "Amount must be positive"}
        
        if not request.pair_address:
            return {"valid": False, "reason": "Pair address required"}
        
        if not request.token_address:
            return {"valid": False, "reason": "Token address required"}
        
        if request.slippage_tolerance_bps < 0 or request.slippage_tolerance_bps > 5000:
            return {"valid": False, "reason": "Invalid slippage tolerance"}
        
        # Chain validation
        supported_chains = ["ethereum", "bsc", "base", "polygon"]
        if request.chain not in supported_chains:
            return {"valid": False, "reason": f"Unsupported chain: {request.chain}"}
        
        # Limit order validation
        if request.order_type == OrderType.LIMIT and not request.limit_price:
            return {"valid": False, "reason": "Limit price required for limit orders"}
        
        # Stop order validation
        if request.order_type == OrderType.STOP_LOSS and not request.stop_price:
            return {"valid": False, "reason": "Stop price required for stop orders"}
        
        return {"valid": True, "reason": None}
    
    async def _submit_paper_order(self, order: Order) -> bool:
        """Submit order in paper trading mode."""
        
        # Simulate immediate execution for market orders
        if order.request.order_type == OrderType.MARKET:
            # Simulate realistic execution with slight delay
            await asyncio.sleep(0.5)
            
            # Create simulated fill
            fill_id = f"fill_{uuid.uuid4().hex[:8]}"
            simulated_price = Decimal("1.0")  # Mock price
            
            fill = OrderFill(
                fill_id=fill_id,
                order_id=order.order_id,
                filled_amount_usd=order.request.amount_usd,
                fill_price=simulated_price,
                timestamp=datetime.now(timezone.utc),
                tx_hash=f"0xpaper{uuid.uuid4().hex[:8]}",
                fees_usd=order.request.amount_usd * Decimal("0.003")  # 0.3% fees
            )
            
            order.fills.append(fill)
            order.filled_amount_usd = order.request.amount_usd
            order.average_fill_price = simulated_price
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now(timezone.utc)
            order.updated_at = datetime.now(timezone.utc)
            order.tx_hash = fill.tx_hash
            order.total_fees_usd = fill.fees_usd or Decimal("0")
            
            logger.info(f"Paper order {order.order_id} filled at ${simulated_price}")
        
        return True
    
    async def _submit_live_order(self, order: Order) -> bool:
        """Submit order for live execution."""
        
        # TODO: Implement live order submission
        # This would integrate with actual DEX routers and execute real trades
        
        logger.warning(f"Live trading not implemented - order {order.order_id} failed")
        order.status = OrderStatus.FAILED
        order.error_message = "Live trading not implemented"
        
        return False
    
    async def _cancel_paper_order(self, order: Order) -> bool:
        """Cancel paper order."""
        logger.info(f"Cancelled paper order {order.order_id}")
        return True
    
    async def _cancel_live_order(self, order: Order) -> bool:
        """Cancel live order."""
        
        # TODO: Implement live order cancellation
        logger.warning(f"Live order cancellation not implemented - order {order.order_id}")
        return False
    
    async def _monitor_order_execution(self, order_id: str) -> None:
        """Monitor order execution and update status."""
        
        order = self.active_orders.get(order_id)
        if not order:
            return
        
        max_wait_time = order.request.timeout_seconds
        start_time = datetime.now(timezone.utc)
        
        while order.is_active:
            # Check timeout
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed > max_wait_time:
                order.status = OrderStatus.EXPIRED
                order.error_message = "Order timed out"
                order.updated_at = datetime.now(timezone.utc)
                logger.warning(f"Order {order_id} expired after {elapsed}s")
                break
            
            # For paper mode, orders fill immediately in _submit_paper_order
            if self.paper_mode or order.request.is_paper:
                break
            
            # For live mode, would check actual execution status
            # TODO: Implement live order status checking
            
            await asyncio.sleep(1)
        
        # Move completed orders to history
        if not order.is_active and order_id in self.active_orders:
            completed_order = self.active_orders.pop(order_id)
            self.order_history.append(completed_order)
            
            # Update daily statistics
            if completed_order.status == OrderStatus.FILLED:
                self.daily_volume_usd += completed_order.filled_amount_usd
            
            self.daily_order_count += 1

@dataclass
class TradeIntent:
    """
    Represents the intent to execute a trade in copy trading.
    Used for evaluation before creating actual orders.
    """
    trader_address: str
    original_tx_hash: str
    chain: str
    dex_name: str
    
    # Token details
    token_address: str
    token_symbol: str
    pair_address: str
    
    # Trade details
    side: OrderSide
    original_amount_usd: Decimal
    suggested_copy_amount_usd: Decimal
    
    # Timing
    detected_at: datetime
    original_timestamp: datetime
    
    # Metadata
    confidence_score: float = 0.5
    risk_score: float = 5.0
    notes: str = ""
    
    @property
    def delay_ms(self) -> int:
        """Calculate detection delay in milliseconds."""
        delay = (self.detected_at - self.original_timestamp).total_seconds() * 1000
        return max(0, int(delay))
    
    @property
    def is_stale(self) -> bool:
        """Check if trade intent is too old to be useful."""
        age_seconds = (datetime.now(timezone.utc) - self.original_timestamp).total_seconds()
        return age_seconds > 300  # 5 minutes


# Global order manager instance
order_manager = OrderManager()


# Utility functions for easy access
async def create_copy_order(
    original_tx_hash: str,
    trader_address: str,
    pair_address: str,
    chain: str,
    side: OrderSide,
    amount_usd: Decimal,
    token_address: str,
    token_symbol: str,
    dex_name: str,
    copy_percentage: Decimal,
    is_paper: bool = True
) -> Order:
    """
    Convenience function to create a copy trading order.
    
    Returns:
        Created Order object
    """
    request = OrderRequest(
        pair_address=pair_address,
        chain=chain,
        side=side,
        order_type=OrderType.MARKET,
        amount_usd=amount_usd,
        token_address=token_address,
        token_symbol=token_symbol,
        dex_name=dex_name,
        original_tx_hash=original_tx_hash,
        trader_address=trader_address,
        copy_percentage=copy_percentage,
        is_paper=is_paper,
        notes=f"Copy trade from {trader_address[:8]}..."
    )
    
    return await order_manager.create_order(request)