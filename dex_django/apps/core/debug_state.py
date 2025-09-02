# APP: dex_django
# FILE: dex_django/apps/core/debug_state.py
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Set
from fastapi import WebSocket

logger = logging.getLogger("core.debug_state")


class DebugServerState:
    """
    Global state manager for debug server.
    
    Manages WebSocket connections, thread pools, and runtime flags
    for the debug development server.
    """
    
    def __init__(self) -> None:
        """Initialize debug server state."""
        # WebSocket client registries
        self.paper_clients: Set[WebSocket] = set()
        self.metrics_clients: Set[WebSocket] = set()
        
        # Runtime flags
        self.thought_log_active: bool = False
        
        # Thread pool for background tasks
        self.executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=2)
        
        # Module availability flags
        self.copy_mock_available: bool = False
        self.copy_trading_system_ready: bool = False
        self.django_initialized: bool = False
        
        logger.info("Debug server state initialized")
    
    def add_paper_client(self, websocket: WebSocket) -> None:
        """
        Add a WebSocket client to the paper trading channel.
        
        Args:
            websocket: WebSocket connection to add.
        """
        self.paper_clients.add(websocket)
        logger.info(f"Added paper client. Total clients: {len(self.paper_clients)}")
    
    def remove_paper_client(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket client from the paper trading channel.
        
        Args:
            websocket: WebSocket connection to remove.
        """
        self.paper_clients.discard(websocket)
        logger.info(f"Removed paper client. Total clients: {len(self.paper_clients)}")
    
    def add_metrics_client(self, websocket: WebSocket) -> None:
        """
        Add a WebSocket client to the metrics channel.
        
        Args:
            websocket: WebSocket connection to add.
        """
        self.metrics_clients.add(websocket)
        logger.info(f"Added metrics client. Total clients: {len(self.metrics_clients)}")
    
    def remove_metrics_client(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket client from the metrics channel.
        
        Args:
            websocket: WebSocket connection to remove.
        """
        self.metrics_clients.discard(websocket)
        logger.info(f"Removed metrics client. Total clients: {len(self.metrics_clients)}")
    
    def get_paper_client_count(self) -> int:
        """Get the number of connected paper trading clients."""
        return len(self.paper_clients)
    
    def get_metrics_client_count(self) -> int:
        """Get the number of connected metrics clients."""
        return len(self.metrics_clients)
    
    def has_paper_clients(self) -> bool:
        """Check if any paper trading clients are connected."""
        return len(self.paper_clients) > 0
    
    def has_metrics_clients(self) -> bool:
        """Check if any metrics clients are connected."""
        return len(self.metrics_clients) > 0
    
    def enable_thought_log(self) -> None:
        """Enable AI thought log streaming."""
        self.thought_log_active = True
        logger.info("AI thought log streaming enabled")
    
    def disable_thought_log(self) -> None:
        """Disable AI thought log streaming."""
        self.thought_log_active = False
        logger.info("AI thought log streaming disabled")
    
    def set_module_availability(
        self, 
        copy_mock: bool = False, 
        copy_trading_system: bool = False,
        django: bool = False
    ) -> None:
        """
        Set module availability flags.
        
        Args:
            copy_mock: Whether copy_mock module is available.
            copy_trading_system: Whether complete copy trading system is ready.
            django: Whether Django ORM is initialized.
        """
        self.copy_mock_available = copy_mock
        self.copy_trading_system_ready = copy_trading_system
        self.django_initialized = django
        
        logger.info(f"Module availability updated: "
                   f"copy_mock={copy_mock}, "
                   f"copy_trading={copy_trading_system}, "
                   f"django={django}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.
        
        Returns:
            Dict containing current system state and connection counts.
        """
        return {
            "connections": {
                "paper_clients": len(self.paper_clients),
                "metrics_clients": len(self.metrics_clients),
                "total_clients": len(self.paper_clients) + len(self.metrics_clients)
            },
            "features": {
                "thought_log_active": self.thought_log_active,
                "copy_mock_available": self.copy_mock_available,
                "copy_trading_system_ready": self.copy_trading_system_ready,
                "django_initialized": self.django_initialized
            },
            "thread_pool": {
                "max_workers": self.executor._max_workers,
                "active_threads": len([t for t in self.executor._threads if t.is_alive()]) if hasattr(self.executor, '_threads') else 0
            }
        }
    
    def cleanup_disconnected_clients(self) -> int:
        """
        Clean up disconnected WebSocket clients.
        
        Returns:
            int: Number of clients removed.
        """
        initial_paper_count = len(self.paper_clients)
        initial_metrics_count = len(self.metrics_clients)
        
        # Remove disconnected paper clients
        disconnected_paper = set()
        for client in self.paper_clients.copy():
            try:
                # Check if client is still connected
                if client.client_state.value >= 3:  # DISCONNECTED or CLOSED
                    disconnected_paper.add(client)
            except Exception:
                # If we can't check state, assume disconnected
                disconnected_paper.add(client)
        
        for client in disconnected_paper:
            self.paper_clients.discard(client)
        
        # Remove disconnected metrics clients
        disconnected_metrics = set()
        for client in self.metrics_clients.copy():
            try:
                if client.client_state.value >= 3:  # DISCONNECTED or CLOSED
                    disconnected_metrics.add(client)
            except Exception:
                disconnected_metrics.add(client)
        
        for client in disconnected_metrics:
            self.metrics_clients.discard(client)
        
        total_removed = len(disconnected_paper) + len(disconnected_metrics)
        
        if total_removed > 0:
            logger.info(f"Cleaned up {total_removed} disconnected clients "
                       f"(paper: {len(disconnected_paper)}, metrics: {len(disconnected_metrics)})")
        
        return total_removed
    
    def shutdown(self) -> None:
        """Shutdown debug server state and cleanup resources."""
        logger.info("Shutting down debug server state...")
        
        # Close all WebSocket connections
        total_clients = len(self.paper_clients) + len(self.metrics_clients)
        
        self.paper_clients.clear()
        self.metrics_clients.clear()
        
        # Shutdown thread pool
        self.executor.shutdown(wait=True)
        
        # Reset flags
        self.thought_log_active = False
        self.copy_mock_available = False
        self.copy_trading_system_ready = False
        self.django_initialized = False
        
        logger.info(f"Debug server state shutdown complete. Closed {total_clients} connections.")


# Global instance for the debug server
debug_state = DebugServerState()