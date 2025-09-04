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
        """Get seed traders with proper conditional imports."""
        return [
            {
                "wallet_address": "0x8ba1f109551bd432803012645hac136c22c501ba", # Example address
                "trader_name": "DeFi Alpha Hunter",
                "description": "High-conviction DeFi plays with strong risk management. Focus on new token launches and yield opportunities.",
                "chain": "ethereum" if not self.imports_available else ChainType.ETHEREUM,
                "copy_mode": "percentage" if not self.imports_available else CopyMode.PERCENTAGE,
                "copy_percentage": Decimal("2.5"),  # Conservative 2.5%
                "max_position_usd": Decimal("500.0"),
                "min_trade_value_usd": Decimal("100.0"),
                "max_slippage_bps": 250,
                "allowed_chains": ["ethereum", "base"],
                "copy_buy_only": False,
                "copy_sell_only": False,
                "status": "active" if not self.imports_available else WalletStatus.ACTIVE,
                "tags": ["defi", "alpha", "risk_management"]
            },
            {
                "wallet_address": "0x742d35cc663c0532925a3b8d186dj8c06f42dbf0", # Example address
                "trader_name": "Swing Master Pro", 
                "description": "Swing trading specialist with clear invalidation levels. Strong technical analysis and narrative awareness.",
                "chain": "ethereum" if not self.imports_available else ChainType.ETHEREUM,
                "copy_mode": "percentage" if not self.imports_available else CopyMode.PERCENTAGE,
                "copy_percentage": Decimal("3.0"),
                "max_position_usd": Decimal("750.0"),
                "min_trade_value_usd": Decimal("150.0"),
                "max_slippage_bps": 300,
                "allowed_chains": ["ethereum", "arbitrum"],
                "copy_buy_only": False,
                "copy_sell_only": False,
                "status": "active" if not self.imports_available else WalletStatus.ACTIVE,
                "tags": ["swing_trading", "technical_analysis", "levels"]
            },
            {
                "wallet_address": "0x9f12d55fa84c4d13b36b2a1c8b7e3d9a2f8c5b3e", # Example address
                "trader_name": "Momentum Breakout Bot",
                "description": "Specializes in momentum and breakout trades. Transparent thesis and clear invalidations.",
                "chain": "bsc" if not self.imports_available else ChainType.BSC,
                "copy_mode": "fixed_amount" if not self.imports_available else CopyMode.FIXED_AMOUNT,
                "fixed_amount_usd": Decimal("200.0"),
                "max_position_usd": Decimal("400.0"),
                "min_trade_value_usd": Decimal("50.0"),
                "max_slippage_bps": 400,  # Higher for BSC
                "allowed_chains": ["bsc", "polygon"],
                "copy_buy_only": True,  # Only copy buy entries
                "copy_sell_only": False,
                "status": "active" if not self.imports_available else WalletStatus.ACTIVE,
                "tags": ["momentum", "breakouts", "bsc"]
            },
            {
                "wallet_address": "0xa3b4c5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2", # Example address
                "trader_name": "Macro Narrative Player",
                "description": "High-conviction narrative and macro plays. Focuses on ecosystem rotations and policy-driven moves.",
                "chain": "ethereum" if not self.imports_available else ChainType.ETHEREUM,
                "copy_mode": "percentage" if not self.imports_available else CopyMode.PERCENTAGE,
                "copy_percentage": Decimal("1.5"),  # Lower % for macro plays
                "max_position_usd": Decimal("1000.0"),
                "min_trade_value_usd": Decimal("200.0"),
                "max_slippage_bps": 200,  # Tighter slippage for large trades
                "allowed_chains": ["ethereum"],
                "copy_buy_only": False,
                "copy_sell_only": False,
                "status": "active" if not self.imports_available else WalletStatus.ACTIVE,
                "tags": ["macro", "narratives", "high_conviction"]
            },
            {
                "wallet_address": "0xb1c2d3e4f5g6h7i8j9k0l1m2n3o4p5q6r7s8t9u0", # Example address
                "trader_name": "Alt Season Specialist",
                "description": "Altcoin specialist with deep understanding of liquidity and liquidation dynamics. Educational focus on risk.",
                "chain": "ethereum" if not self.imports_available else ChainType.ETHEREUM,
                "copy_mode": "percentage" if not self.imports_available else CopyMode.PERCENTAGE,
                "copy_percentage": Decimal("4.0"),  # Higher % for alt plays
                "max_position_usd": Decimal("300.0"),
                "min_trade_value_usd": Decimal("75.0"),
                "max_slippage_bps": 350,
                "allowed_chains": ["ethereum", "bsc", "polygon"],
                "copy_buy_only": False,
                "copy_sell_only": False,
                "status": "active" if not self.imports_available else WalletStatus.ACTIVE,
                "tags": ["altcoins", "liquidity", "education"]
            },
            {
                "wallet_address": "0xc9d8e7f6g5h4i3j2k1l0m9n8o7p6q5r4s3t2u1v0", # Example address
                "trader_name": "On-Chain Analytics Pro",
                "description": "Data-driven trader using on-chain analytics to time BTC and major alt cycles. Strong macro framework.",
                "chain": "ethereum" if not self.imports_available else ChainType.ETHEREUM,
                "copy_mode": "percentage" if not self.imports_available else CopyMode.PERCENTAGE,
                "copy_percentage": Decimal("2.0"),
                "max_position_usd": Decimal("800.0"),
                "min_trade_value_usd": Decimal("250.0"),
                "max_slippage_bps": 200,
                "allowed_chains": ["ethereum"],
                "copy_buy_only": False,
                "copy_sell_only": False,
                "status": "paused" if not self.imports_available else WalletStatus.PAUSED,  # Start paused for review
                "tags": ["onchain", "analytics", "btc", "macro"]
            }
        ]
    
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