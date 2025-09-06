# APP: dex_django
# FILE: dex_django/apps/core/data_seeder.py
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Any
from datetime import datetime

# FIXED IMPORTS - Remove dex_django. prefix since we're in dex_django/apps/
try:
    from apps.storage.copy_trading_repo import create_copy_trading_repositories
    from apps.storage.copy_trading_models import ChainType, WalletStatus, CopyMode
    from apps.copy_trading.copy_trading_coordinator import copy_trading_coordinator
    from apps.core.database import get_db
    
    imports_available = True
except ImportError as e:
    logging.warning(f"Copy trading imports not available: {e}")
    imports_available = False

logger = logging.getLogger("core.data_seeder")


class CopyTradingSeeder:
    """Seed copy trading database with initial high-quality traders."""
    
    def __init__(self):
        self.imports_available = imports_available
    
    def get_seed_traders(self) -> List[Dict[str, Any]]:
        """
        Get seed traders - NOW REQUIRES REAL WALLET ADDRESSES.
        Returns empty list - real traders must be added manually.
        """
        logger.warning("No seed traders configured - please add real wallet addresses")
        logger.info("Use the Copy Trading UI to manually add verified profitable traders")
        logger.info("Research traders using: Nansen, Arkham, DexScreener, Etherscan")
        
        # Return empty list - no mock data
        return []









    async def seed_copy_trading_data(self, force_reseed: bool = False) -> Dict[str, Any]:
        """Seed the copy trading system with high-quality traders."""
        
        if not self.imports_available:
            return {
                "status": "skipped",
                "message": "Copy trading modules not available",
                "seeded_count": 0
            }
        
        logger.info("Starting copy trading data seeding...")
        
        try:
            async with get_db() as session:
                repos = create_copy_trading_repositories(session)
                
                # Check if data already exists
                existing_wallets = await repos["wallets"].list_wallets(limit=1)
                if existing_wallets and not force_reseed:
                    logger.info("Copy trading data already seeded. Use force_reseed=True to override.")
                    return {
                        "status": "skipped",
                        "message": "Data already exists",
                        "existing_count": len(existing_wallets)
                    }
                
                seeded_count = 0
                errors = []
                seed_traders = self.get_seed_traders()
                
                for trader_data in seed_traders:
                    try:
                        # Check if wallet already exists
                        existing = await repos["wallets"].get_wallet_by_address(
                            trader_data["wallet_address"],
                            trader_data["chain"]
                        )
                        
                        if existing and not force_reseed:
                            logger.info(f"Trader {trader_data['trader_name']} already exists, skipping")
                            continue
                        
                        # Create the trader
                        wallet = await repos["wallets"].create_wallet(
                            address=trader_data["wallet_address"],
                            chain=trader_data["chain"],
                            nickname=trader_data["trader_name"],
                            description=trader_data.get("description"),
                            status=trader_data["status"],
                            copy_mode=trader_data["copy_mode"],
                            copy_percentage=trader_data.get("copy_percentage", Decimal("3.0")),
                            fixed_amount_usd=trader_data.get("fixed_amount_usd"),
                            max_position_usd=trader_data["max_position_usd"],
                            min_trade_value_usd=trader_data["min_trade_value_usd"],
                            max_slippage_bps=trader_data["max_slippage_bps"],
                            allowed_chains=",".join(trader_data["allowed_chains"]),
                            copy_buy_only=trader_data["copy_buy_only"],
                            copy_sell_only=trader_data["copy_sell_only"]
                        )
                        
                        logger.info(f"Seeded trader: {trader_data['trader_name']} ({wallet.id})")
                        seeded_count += 1
                        
                        # Add to wallet tracker if active
                        if trader_data["status"] == WalletStatus.ACTIVE:
                            await copy_trading_coordinator.add_tracked_wallet(
                                address=trader_data["wallet_address"],
                                chain=trader_data["chain"],
                                nickname=trader_data["trader_name"],
                                copy_settings={
                                    "copy_mode": trader_data["copy_mode"].value if hasattr(trader_data["copy_mode"], 'value') else trader_data["copy_mode"],
                                    "copy_percentage": float(trader_data.get("copy_percentage", 3.0)),
                                    "fixed_amount_usd": float(trader_data.get("fixed_amount_usd", 100)) if trader_data.get("fixed_amount_usd") else 100,
                                    "max_position_usd": float(trader_data["max_position_usd"]),
                                    "min_trade_value_usd": float(trader_data["min_trade_value_usd"]),
                                    "max_slippage_bps": trader_data["max_slippage_bps"],
                                    "allowed_chains": trader_data["allowed_chains"],
                                    "copy_buy_only": trader_data["copy_buy_only"],
                                    "copy_sell_only": trader_data["copy_sell_only"]
                                }
                            )
                        
                    except Exception as e:
                        error_msg = f"Failed to seed {trader_data['trader_name']}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                
                logger.info(f"Copy trading data seeding completed. Seeded {seeded_count} traders.")
                
                return {
                    "status": "success",
                    "seeded_count": seeded_count,
                    "errors": errors,
                    "total_attempted": len(seed_traders)
                }
                
        except Exception as e:
            logger.error(f"Copy trading seeding failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "seeded_count": 0
            }
    
    async def create_sample_transactions(self) -> Dict[str, Any]:
        """Create sample detected transactions for testing."""
        
        if not self.imports_available:
            return {
                "status": "skipped",
                "message": "Copy trading modules not available"
            }
        
        logger.info("Creating sample transactions for testing...")
        
        try:
            async with get_db() as session:
                repos = create_copy_trading_repositories(session)
                
                # Get first active wallet
                active_wallets = await repos["wallets"].get_active_wallets()
                if not active_wallets:
                    return {"status": "error", "error": "No active wallets to create transactions for"}
                
                wallet = active_wallets[0]
                
                # Create sample transactions
                sample_transactions = [
                    {
                        "tx_hash": "0xabc123def456ghi789jkl012mno345pqr678stu901vwx234yz",
                        "block_number": 19000000,
                        "chain": wallet.chain,
                        "token_address": "0x1234567890abcdef1234567890abcdef12345678",
                        "token_symbol": "ALPHA",
                        "action": "buy",
                        "amount_token": Decimal("1000.0"),
                        "amount_usd": Decimal("500.0"),
                        "gas_fee_usd": Decimal("15.0"),
                        "confidence_score": 0.85,
                        "dex_name": "uniswap_v3"
                    },
                    {
                        "tx_hash": "0xdef456ghi789jkl012mno345pqr678stu901vwx234yza567bc",
                        "block_number": 19000100,
                        "chain": wallet.chain,
                        "token_address": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
                        "token_symbol": "BETA",
                        "action": "sell",
                        "amount_token": Decimal("2000.0"),
                        "amount_usd": Decimal("750.0"),
                        "gas_fee_usd": Decimal("12.0"),
                        "confidence_score": 0.92,
                        "dex_name": "pancakeswap_v2"
                    }
                ]
                
                created_count = 0
                for tx_data in sample_transactions:
                    await repos["transactions"].create_transaction(
                        wallet_id=wallet.id,
                        timestamp=datetime.now(),
                        **tx_data
                    )
                    created_count += 1
                
                return {
                    "status": "success", 
                    "created_transactions": created_count,
                    "wallet_name": wallet.nickname
                }
                
        except Exception as e:
            logger.error(f"Failed to create sample transactions: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_seeding_status(self) -> Dict[str, Any]:
        """Get current seeding status and statistics."""
        
        if not self.imports_available:
            return {
                "status": "unavailable",
                "seeding_needed": False,
                "message": "Copy trading modules not available"
            }
        
        try:
            async with get_db() as session:
                repos = create_copy_trading_repositories(session)
                
                stats = await repos["wallets"].get_wallet_statistics()
                seed_traders = self.get_seed_traders()
                
                return {
                    "status": "success",
                    "wallet_stats": stats,
                    "seed_traders_available": len(seed_traders),
                    "seeding_needed": stats["status_counts"].get("active", 0) == 0
                }
                
        except Exception as e:
            return {"status": "error", "error": str(e)}


# Global seeder instance
copy_trading_seeder = CopyTradingSeeder()


# API endpoint for manual seeding
async def seed_copy_trading_data_endpoint(force_reseed: bool = False) -> Dict[str, Any]:
    """API endpoint to trigger copy trading data seeding."""
    return await copy_trading_seeder.seed_copy_trading_data(force_reseed=force_reseed)