# APP: dex_django
# FILE: dex_django/apps/api/copy_trading_real.py
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from asgiref.sync import sync_to_async

# Django imports
try:
    from django.db import connection
    from ledger.models import FollowedTrader, CopyTrade, DetectedTransaction
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False
    connection = None

router = APIRouter(prefix="/api/v1/copy-trading-real", tags=["copy-trading-real"])
logger = logging.getLogger("api.copy_trading_real")


# ============================================================================
# Database Check Functions
# ============================================================================

def check_database_tables_sync() -> Dict[str, Any]:
    """Check if database tables exist (synchronous)."""
    
    if not DJANGO_AVAILABLE or not connection:
        return {
            "status": "error",
            "message": "Django models not available",
            "tables_exist": False
        }
    
    try:
        with connection.cursor() as cursor:
            # Check for required tables
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_name IN ('ledger_followedtrader', 'ledger_copytrade', 'ledger_detectedtransaction')
                AND table_schema = 'public'
            """)
            
            result = cursor.fetchone()
            tables_count = result[0] if result else 0
            
            return {
                "status": "ok",
                "tables_exist": tables_count == 3,
                "tables_found": tables_count,
                "django_available": True
            }
            
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "tables_exist": False
        }


async def check_database_tables() -> Dict[str, Any]:
    """Check if database tables exist (async wrapper)."""
    return await sync_to_async(check_database_tables_sync)()


# ============================================================================
# Real Data Retrieval Functions
# ============================================================================

@sync_to_async
def get_real_trader_data_sync() -> List[Dict[str, Any]]:
    """Get real trader data from database (synchronous)."""
    traders = []
    
    if DJANGO_AVAILABLE and connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id, wallet_address, trader_name, description, chain,
                           copy_percentage, max_position_usd, status, created_at,
                           total_copies, successful_copies, total_pnl_usd,
                           win_rate, avg_profit_pct, total_volume_usd,
                           last_trade_at
                    FROM ledger_followedtrader
                    WHERE is_active = true
                    ORDER BY created_at DESC
                """)
                
                rows = cursor.fetchall()
                for row in rows:
                    trader = {
                        "id": row[0],
                        "wallet_address": row[1],
                        "trader_name": row[2],
                        "description": row[3],
                        "chain": row[4],
                        "copy_percentage": float(row[5]) if row[5] else 0.0,
                        "max_position_usd": float(row[6]) if row[6] else 0.0,
                        "status": row[7],
                        "created_at": row[8].isoformat() if row[8] else None,
                        "total_copies": row[9] or 0,
                        "successful_copies": row[10] or 0,
                        "total_pnl_usd": float(row[11]) if row[11] else 0.0,
                        "win_rate": float(row[12]) if row[12] else 0.0,
                        "avg_profit_pct": float(row[13]) if row[13] else 0.0,
                        "total_volume_usd": float(row[14]) if row[14] else 0.0,
                        "last_trade_at": row[15].isoformat() if row[15] else None
                    }
                    traders.append(trader)
                    
        except Exception as e:
            logger.error(f"Failed to fetch traders from database: {e}")
    
    return traders


async def get_real_trader_data() -> List[Dict[str, Any]]:
    """Get real trader data from database (async wrapper)."""
    return await get_real_trader_data_sync()


@sync_to_async
def get_real_copy_trades_sync(limit: int = 50) -> List[Dict[str, Any]]:
    """Get real copy trades from database (synchronous)."""
    trades = []
    
    if DJANGO_AVAILABLE and connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT ct.id, ct.original_tx_hash, ct.copy_tx_hash,
                           ct.trader_address, ct.token_address, ct.token_symbol,
                           ct.amount_usd, ct.copy_amount_usd, ct.status,
                           ct.created_at, ct.executed_at, ct.pnl_usd,
                           ft.trader_name
                    FROM ledger_copytrade ct
                    LEFT JOIN ledger_followedtrader ft ON ct.trader_address = ft.wallet_address
                    ORDER BY ct.created_at DESC
                    LIMIT %s
                """, [limit])
                
                rows = cursor.fetchall()
                for row in rows:
                    trade = {
                        "id": row[0],
                        "original_tx_hash": row[1],
                        "copy_tx_hash": row[2],
                        "trader_address": row[3],
                        "token_address": row[4],
                        "token_symbol": row[5],
                        "amount_usd": float(row[6]) if row[6] else 0.0,
                        "copy_amount_usd": float(row[7]) if row[7] else 0.0,
                        "status": row[8],
                        "created_at": row[9].isoformat() if row[9] else None,
                        "executed_at": row[10].isoformat() if row[10] else None,
                        "pnl_usd": float(row[11]) if row[11] else None,
                        "trader_name": row[12]
                    }
                    trades.append(trade)
                    
        except Exception as e:
            logger.error(f"Failed to fetch copy trades from database: {e}")
    
    return trades


async def get_real_copy_trades(limit: int = 50) -> List[Dict[str, Any]]:
    """Get real copy trades from database (async wrapper)."""
    return await get_real_copy_trades_sync(limit)


@sync_to_async
def get_detected_transactions_sync(hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
    """Get recently detected transactions (synchronous)."""
    transactions = []
    
    if DJANGO_AVAILABLE and connection:
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT dt.tx_hash, dt.block_number, dt.from_address,
                           dt.token_in, dt.token_out, dt.amount_in,
                           dt.amount_out, dt.amount_usd, dt.dex_name,
                           dt.chain, dt.timestamp, dt.gas_used,
                           ft.trader_name
                    FROM ledger_detectedtransaction dt
                    LEFT JOIN ledger_followedtrader ft ON dt.from_address = ft.wallet_address
                    WHERE dt.timestamp > %s
                    ORDER BY dt.timestamp DESC
                    LIMIT %s
                """, [cutoff_time, limit])
                
                rows = cursor.fetchall()
                for row in rows:
                    tx = {
                        "tx_hash": row[0],
                        "block_number": row[1],
                        "from_address": row[2],
                        "token_in": row[3],
                        "token_out": row[4],
                        "amount_in": float(row[5]) if row[5] else 0.0,
                        "amount_out": float(row[6]) if row[6] else 0.0,
                        "amount_usd": float(row[7]) if row[7] else 0.0,
                        "dex_name": row[8],
                        "chain": row[9],
                        "timestamp": row[10].isoformat() if row[10] else None,
                        "gas_used": row[11],
                        "trader_name": row[12]
                    }
                    transactions.append(tx)
                    
        except Exception as e:
            logger.error(f"Failed to fetch detected transactions: {e}")
    
    return transactions


async def get_detected_transactions(hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
    """Get recently detected transactions (async wrapper)."""
    return await get_detected_transactions_sync(hours, limit)


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/traders", summary="Get real traders from database")
async def get_traders() -> Dict[str, Any]:
    """Get all traders from the actual database."""
    
    try:
        traders = await get_real_trader_data()
        
        return {
            "status": "ok",
            "source": "database",
            "traders": traders,
            "count": len(traders)
        }
        
    except Exception as e:
        logger.error(f"Failed to get traders: {e}")
        raise HTTPException(500, f"Failed to retrieve traders: {str(e)}") from e


@router.get("/trades", summary="Get real copy trades")
async def get_copy_trades(
    limit: int = Query(50, ge=1, le=500)
) -> Dict[str, Any]:
    """Get recent copy trades from the database."""
    
    try:
        trades = await get_real_copy_trades(limit=limit)
        
        return {
            "status": "ok",
            "source": "database",
            "trades": trades,
            "count": len(trades)
        }
        
    except Exception as e:
        logger.error(f"Failed to get copy trades: {e}")
        raise HTTPException(500, f"Failed to retrieve copy trades: {str(e)}") from e


@router.get("/detected-transactions", summary="Get detected transactions")
async def get_detected_txs(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=1, le=1000)
) -> Dict[str, Any]:
    """Get recently detected transactions from followed wallets."""
    
    try:
        transactions = await get_detected_transactions(hours=hours, limit=limit)
        
        return {
            "status": "ok",
            "source": "database",
            "transactions": transactions,
            "count": len(transactions),
            "time_range_hours": hours
        }
        
    except Exception as e:
        logger.error(f"Failed to get detected transactions: {e}")
        raise HTTPException(500, f"Failed to retrieve transactions: {str(e)}") from e


@router.get("/database-status", summary="Check database status")
async def check_database_status() -> Dict[str, Any]:
    """Check if the database tables exist and are accessible."""
    
    return await check_database_tables()