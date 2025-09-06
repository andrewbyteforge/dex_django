# APP: dex_django
# FILE: dex_django/apps/core/data_seeder.py
from __future__ import annotations

import logging
from typing import Dict, Any

logger = logging.getLogger("core.data_seeder")


class CopyTradingSeeder:
    """Placeholder class - all mock data seeding has been removed."""
    
    def __init__(self):
        self.imports_available = False
    
    async def seed_copy_trading_data(self, force_reseed: bool = False) -> Dict[str, Any]:
        """Seeding functionality has been removed."""
        logger.info("Mock data seeding has been disabled")
        return {
            "status": "disabled",
            "message": "Mock data seeding functionality has been removed",
            "seeded_count": 0
        }
    
    async def create_sample_transactions(self) -> Dict[str, Any]:
        """Sample transaction creation has been removed."""
        logger.info("Sample transaction creation has been disabled")
        return {
            "status": "disabled",
            "message": "Sample transaction creation has been removed",
            "created_transactions": 0
        }
    
    async def get_seeding_status(self) -> Dict[str, Any]:
        """Get seeding status - always returns disabled."""
        return {
            "status": "disabled",
            "seeding_needed": False,
            "message": "Mock data seeding has been removed"
        }


# Global seeder instance (kept for compatibility but does nothing)
copy_trading_seeder = CopyTradingSeeder()