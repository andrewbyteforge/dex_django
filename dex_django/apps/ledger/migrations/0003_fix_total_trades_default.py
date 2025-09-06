"""Migration to fix total_trades default value in ledger_followedtrader table."""
from __future__ import annotations

from decimal import Decimal
from django.db import migrations


def add_default_values(apps, schema_editor):
    """
    Add default values to existing NULL fields and set defaults at DB level.
    
    Args:
        apps: Django apps registry
        schema_editor: Database schema editor
    """
    # Update any existing NULL values to 0
    db_alias = schema_editor.connection.alias
    
    # For SQLite, we need to use raw SQL to modify the table
    if schema_editor.connection.vendor == 'sqlite':
        with schema_editor.connection.cursor() as cursor:
            # First, update any NULL values to defaults
            cursor.execute("""
                UPDATE ledger_followedtrader 
                SET total_trades = 0 
                WHERE total_trades IS NULL
            """)
            
            cursor.execute("""
                UPDATE ledger_followedtrader 
                SET total_pnl_usd = 0.00 
                WHERE total_pnl_usd IS NULL
            """)
            
            cursor.execute("""
                UPDATE ledger_followedtrader 
                SET win_rate_pct = 0.00 
                WHERE win_rate_pct IS NULL
            """)
            
            cursor.execute("""
                UPDATE ledger_followedtrader 
                SET avg_trade_size_usd = 0.00 
                WHERE avg_trade_size_usd IS NULL
            """)
            
            # SQLite doesn't support ALTER COLUMN SET DEFAULT directly
            # We need to recreate the table with proper defaults
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ledger_followedtrader_new (
                    id VARCHAR(32) PRIMARY KEY,
                    wallet_address VARCHAR(42) NOT NULL,
                    trader_name VARCHAR(100) NOT NULL,
                    description TEXT,
                    chain VARCHAR(20) NOT NULL,
                    copy_mode VARCHAR(20) NOT NULL,
                    copy_percentage DECIMAL(5,2) NOT NULL,
                    fixed_amount_usd DECIMAL(10,2),
                    max_position_usd DECIMAL(10,2) NOT NULL,
                    min_trade_value_usd DECIMAL(10,2) NOT NULL,
                    max_slippage_bps INTEGER NOT NULL,
                    allowed_chains TEXT NOT NULL,
                    copy_buy_only BOOLEAN NOT NULL,
                    copy_sell_only BOOLEAN NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    quality_score INTEGER,
                    total_pnl_usd DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                    win_rate_pct DECIMAL(5,2) NOT NULL DEFAULT 0.00,
                    total_trades INTEGER NOT NULL DEFAULT 0,
                    avg_trade_size_usd DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                    last_activity_at DATETIME,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    UNIQUE(wallet_address, chain)
                )
            """)
            
            # Copy data from old table to new table
            cursor.execute("""
                INSERT INTO ledger_followedtrader_new 
                SELECT 
                    id,
                    wallet_address,
                    trader_name,
                    description,
                    chain,
                    copy_mode,
                    copy_percentage,
                    fixed_amount_usd,
                    max_position_usd,
                    min_trade_value_usd,
                    max_slippage_bps,
                    allowed_chains,
                    copy_buy_only,
                    copy_sell_only,
                    status,
                    is_active,
                    quality_score,
                    COALESCE(total_pnl_usd, 0.00),
                    COALESCE(win_rate_pct, 0.00),
                    COALESCE(total_trades, 0),
                    COALESCE(avg_trade_size_usd, 0.00),
                    last_activity_at,
                    created_at,
                    updated_at
                FROM ledger_followedtrader
            """)
            
            # Drop old table and rename new one
            cursor.execute("DROP TABLE ledger_followedtrader")
            cursor.execute("ALTER TABLE ledger_followedtrader_new RENAME TO ledger_followedtrader")
            
            # Recreate indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS ledger_foll_wallet__5ed329_idx 
                ON ledger_followedtrader (wallet_address)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS ledger_foll_chain_5766d8_idx 
                ON ledger_followedtrader (chain, status)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS ledger_foll_is_acti_9afd61_idx 
                ON ledger_followedtrader (is_active, status)
            """)
            
            print("✅ Successfully fixed ledger_followedtrader table defaults")


def reverse_defaults(apps, schema_editor):
    """
    Reverse migration - remove defaults (not recommended).
    
    Args:
        apps: Django apps registry
        schema_editor: Database schema editor
    """
    # This is intentionally a no-op as we don't want to remove defaults
    pass


class Migration(migrations.Migration):
    """Fix total_trades and other default values in ledger_followedtrader."""
    
    dependencies = [
        ('ledger', '0002_discoveryrun_followedtrader_tradercandidate_and_more'),
    ]
    
    operations = [
        migrations.RunPython(
            add_default_values,
            reverse_defaults,
            elidable=False
        ),
    ]