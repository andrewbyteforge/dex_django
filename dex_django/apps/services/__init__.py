# APP: backend/app/services
# FILE: backend/app/services/__init__.py
from __future__ import annotations

import logging

logger = logging.getLogger("services")

# Import main services
try:
    from .copy_trading_service import copy_trading_service, CopyTradingService, TraderRecord, CopyTradingServiceStatus
    
    logger.info("Copy trading service imported successfully")
    COPY_TRADING_SERVICE_AVAILABLE = True
    
except ImportError as e:
    logger.warning(f"Copy trading service not available: {e}")
    copy_trading_service = None
    CopyTradingService = None
    TraderRecord = None
    CopyTradingServiceStatus = None
    COPY_TRADING_SERVICE_AVAILABLE = False

# Export public API
__all__ = [
    "copy_trading_service",
    "CopyTradingService", 
    "TraderRecord",
    "CopyTradingServiceStatus",
    "COPY_TRADING_SERVICE_AVAILABLE"
]