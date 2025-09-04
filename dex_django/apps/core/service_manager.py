# APP: backend/app/core
# FILE: backend/app/core/service_manager.py
from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("core.service_manager")


class ServiceManager:
    """
    Central manager for initializing and wiring all services.
    
    This class coordinates the initialization of:
    - CopyTradingService (central orchestrator)  
    - WalletMonitor (transaction detection)
    - CopyTradingStrategy (decision making)
    - WebSocket Hub (real-time updates)
    - Database connections
    """
    
    def __init__(self):
        self._initialized = False
        self._services = {}
        
        # Service instances
        self.copy_trading_service = None
        self.wallet_monitor = None
        self.copy_strategy = None
        self.websocket_hub = None
    
    async def initialize_all_services(self) -> dict:
        """
        Initialize all services and wire them together.
        
        Returns status of initialization.
        """
        if self._initialized:
            return {"success": True, "message": "Services already initialized"}
        
        try:
            logger.info("Initializing all services...")
            
            # Step 1: Initialize CopyTradingService
            await self._initialize_copy_trading_service()
            
            # Step 2: Initialize WalletMonitor  
            await self._initialize_wallet_monitor()
            
            # Step 3: Initialize CopyTradingStrategy
            await self._initialize_copy_strategy()
            
            # Step 4: Initialize WebSocket Hub
            await self._initialize_websocket_hub()
            
            # Step 5: Wire services together
            await self._wire_services()
            
            # Step 6: Initialize API endpoints
            await self._initialize_api_endpoints()
            
            self._initialized = True
            
            logger.info("✅ All services initialized successfully")
            
            return {
                "success": True,
                "message": "All copy trading services initialized",
                "services": {
                    "copy_trading_service": self.copy_trading_service is not None,
                    "wallet_monitor": self.wallet_monitor is not None,
                    "copy_strategy": self.copy_strategy is not None,
                    "websocket_hub": self.websocket_hub is not None
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Service initialization failed: {e}")
            return {"success": False, "message": str(e)}
    
    async def shutdown_all_services(self) -> dict:
        """Gracefully shutdown all services."""
        if not self._initialized:
            return {"success": True, "message": "Services not initialized"}
        
        try:
            logger.info("Shutting down all services...")
            
            # Stop copy trading service (which stops monitoring)
            if self.copy_trading_service:
                await self.copy_trading_service.stop_service()
            
            # Stop WebSocket hub
            if self.websocket_hub:
                await self.websocket_hub.stop()
            
            # Stop wallet monitor
            if self.wallet_monitor:
                await self.wallet_monitor.stop_monitoring()
            
            self._initialized = False
            
            logger.info("✅ All services shut down successfully")
            
            return {"success": True, "message": "All services shut down"}
            
        except Exception as e:
            logger.error(f"❌ Service shutdown failed: {e}")
            return {"success": False, "message": str(e)}
    
    def is_initialized(self) -> bool:
        """Check if services are initialized."""
        return self._initialized
    
    def get_service_status(self) -> dict:
        """Get status of all services."""
        return {
            "initialized": self._initialized,
            "services": {
                "copy_trading_service": {
                    "available": self.copy_trading_service is not None,
                    "running": getattr(self.copy_trading_service, '_is_running', False) if self.copy_trading_service else False
                },
                "wallet_monitor": {
                    "available": self.wallet_monitor is not None,
                    "running": getattr(self.wallet_monitor, '_is_running', False) if self.wallet_monitor else False
                },
                "copy_strategy": {
                    "available": self.copy_strategy is not None,
                },
                "websocket_hub": {
                    "available": self.websocket_hub is not None,
                    "running": getattr(self.websocket_hub, '_is_running', False) if self.websocket_hub else False
                }
            }
        }
    
    # ---------- PRIVATE INITIALIZATION METHODS ----------
    
    async def _initialize_copy_trading_service(self) -> None:
        """Initialize the main CopyTradingService."""
        try:
            from dex_django.services import copy_trading_service, COPY_TRADING_SERVICE_AVAILABLE
            
            if not COPY_TRADING_SERVICE_AVAILABLE:
                raise ImportError("CopyTradingService not available")
            
            self.copy_trading_service = copy_trading_service
            logger.info("✅ CopyTradingService initialized")
            
        except ImportError as e:
            logger.error(f"❌ Failed to initialize CopyTradingService: {e}")
            raise
    
    async def _initialize_wallet_monitor(self) -> None:
        """Initialize WalletMonitor for transaction detection."""
        try:
            # Try to import existing wallet monitor
            from dex_django.discovery.wallet_monitor import wallet_monitor
            self.wallet_monitor = wallet_monitor
            logger.info("✅ WalletMonitor initialized")
            
        except ImportError as e:
            logger.warning(f"⚠️ WalletMonitor not available: {e}")
            # Create a mock wallet monitor for development
            self.wallet_monitor = MockWalletMonitor()
            logger.info("✅ MockWalletMonitor initialized for development")
    
    async def _initialize_copy_strategy(self) -> None:
        """Initialize CopyTradingStrategy for decision making."""
        try:
            from dex_django.strategy.copy_trading_strategy import copy_trading_strategy
            self.copy_strategy = copy_trading_strategy
            logger.info("✅ CopyTradingStrategy initialized")
            
        except ImportError as e:
            logger.warning(f"⚠️ CopyTradingStrategy not available: {e}")
            # Create a mock strategy for development
            self.copy_strategy = MockCopyStrategy()
            logger.info("✅ MockCopyStrategy initialized for development")
    
    async def _initialize_websocket_hub(self) -> None:
        """Initialize WebSocket hub for real-time updates."""
        try:
            from dex_django.ws.copy_trading import copy_trading_hub
            self.websocket_hub = copy_trading_hub
            logger.info("✅ WebSocket Hub initialized")
            
        except ImportError as e:
            logger.warning(f"⚠️ WebSocket Hub not available: {e}")
            # Create a mock hub for development
            self.websocket_hub = MockWebSocketHub()
            logger.info("✅ MockWebSocketHub initialized for development")
    
    async def _wire_services(self) -> None:
        """Wire all services together."""
        logger.info("Wiring services together...")
        
        # Initialize CopyTradingService with dependencies
        await self.copy_trading_service.initialize(
            wallet_monitor=self.wallet_monitor,
            copy_strategy=self.copy_strategy,
            websocket_hub=self.websocket_hub,
            database=None  # Would connect to database here
        )
        
        logger.info("✅ Services wired together")
    
    async def _initialize_api_endpoints(self) -> None:
        """Initialize API endpoints with services."""
        try:
            from dex_django.api.copy_trading_integrated import initialize_copy_trading_api
            initialize_copy_trading_api(self.copy_trading_service)
            logger.info("✅ API endpoints initialized")
            
        except ImportError as e:
            logger.warning(f"⚠️ API endpoints not available: {e}")


# Mock classes for development when components aren't available
class MockWalletMonitor:
    """Mock wallet monitor for development."""
    
    def __init__(self):
        self._is_running = False
        self._followed_wallets = set()
    
    async def start_monitoring(self, wallet_addresses):
        """Mock start monitoring."""
        self._is_running = True
        self._followed_wallets.update(wallet_addresses)
        logger.info(f"Mock: Started monitoring {len(wallet_addresses)} wallets")
    
    async def stop_monitoring(self):
        """Mock stop monitoring."""
        self._is_running = False
        self._followed_wallets.clear()
        logger.info("Mock: Stopped monitoring")
    
    async def get_monitoring_status(self):
        """Mock get status."""
        return {
            "is_running": self._is_running,
            "followed_wallets": len(self._followed_wallets),
            "active_tasks": len(self._followed_wallets) if self._is_running else 0
        }


class MockCopyStrategy:
    """Mock copy strategy for development."""
    
    async def evaluate_copy_opportunity(self, wallet_tx, trader_config, trace_id):
        """Mock evaluation."""
        logger.info(f"Mock: Evaluating copy opportunity for {wallet_tx.get('tx_hash', 'unknown')}")
        return {
            "decision": "copy",
            "confidence": 0.75,
            "copy_amount_usd": 100.0,
            "risk_score": 3.5,
            "notes": "Mock evaluation - would copy this trade"
        }


class MockWebSocketHub:
    """Mock WebSocket hub for development."""
    
    def __init__(self):
        self._is_running = False
    
    async def start(self):
        """Mock start."""
        self._is_running = True
        logger.info("Mock: WebSocket hub started")
    
    async def stop(self):
        """Mock stop."""
        self._is_running = False
        logger.info("Mock: WebSocket hub stopped")
    
    async def broadcast_trader_activity(self, trader_address, activity_data):
        """Mock broadcast."""
        logger.info(f"Mock: Broadcasting trader activity for {trader_address[:8]}...")
    
    async def broadcast_copy_evaluation(self, evaluation_data):
        """Mock broadcast."""
        logger.info(f"Mock: Broadcasting copy evaluation: {evaluation_data.get('decision', 'unknown')}")
    
    async def broadcast_copy_execution(self, execution_data):
        """Mock broadcast."""
        logger.info(f"Mock: Broadcasting copy execution: {execution_data.get('status', 'unknown')}")
    
    async def broadcast_copy_trading_status(self, status_data):
        """Mock broadcast."""
        logger.info(f"Mock: Broadcasting status update: {status_data.get('event', 'unknown')}")


# Global service manager instance
service_manager = ServiceManager()