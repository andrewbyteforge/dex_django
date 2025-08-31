from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Provider, Token, Pair, Trade, LedgerEntry,
    FollowedTrader, CopyTrade, CopyTradeFilter
)


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    """Admin interface for Provider model."""
    list_display = ("name", "kind", "mode", "enabled", "updated_at")
    list_filter = ("kind", "mode", "enabled")
    search_fields = ('name', 'url')
    ordering = ('-created_at',)


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    """Admin interface for Token model."""
    list_display = ("symbol", "chain", "address", "decimals", "fee_on_transfer")
    search_fields = ("symbol", "address", "name")
    list_filter = ("chain", "fee_on_transfer")
    ordering = ('chain', 'symbol')


@admin.register(Pair)
class PairAdmin(admin.ModelAdmin):
    """Admin interface for Pair model."""
    list_display = ("chain", "dex", "address", "base_token", "quote_token", "fee_bps")
    search_fields = ("address",)
    list_filter = ("chain", "dex")
    ordering = ('-discovered_at',)


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    """Admin interface for Trade model."""
    list_display = ("created_at", "chain", "dex", "pair", "side", "mode", "status")
    list_filter = ("chain", "dex", "side", "mode", "status")
    date_hierarchy = "created_at"
    search_fields = ('tx_hash', 'pair__base_token__symbol')
    ordering = ('-created_at',)


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    """Admin interface for LedgerEntry model."""
    list_display = ("timestamp", "event_type", "status", "tx_hash_short", "trace_id")
    list_filter = ("event_type", "status")
    search_fields = ("tx_hash", "trace_id", "notes")
    date_hierarchy = "timestamp"
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)
    
    def tx_hash_short(self, obj):
        """Display shortened tx hash."""
        if obj.tx_hash:
            return f"{obj.tx_hash[:10]}..."
        return "-"
    tx_hash_short.short_description = "Tx Hash"


# COPY TRADING ADMIN CLASSES
@admin.register(FollowedTrader)
class FollowedTraderAdmin(admin.ModelAdmin):
    """Admin interface for FollowedTrader model."""
    
    list_display = (
        'trader_display', 'status', 'copy_mode', 'copy_percentage', 
        'total_copies', 'win_rate_display', 'total_pnl_display', 'last_activity_at'
    )
    list_filter = (
        'status', 'copy_mode', 'copy_buy_only', 'copy_sell_only', 
        'created_at', 'last_activity_at'
    )
    search_fields = ('wallet_address', 'trader_name', 'description')
    ordering = ('-created_at',)
    readonly_fields = (
        'id', 'total_copies', 'successful_copies', 'total_pnl_usd', 
        'win_rate_pct', 'short_address', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Trader Information', {
            'fields': (
                'id', 'wallet_address', 'trader_name', 'description', 'status'
            )
        }),
        ('Copy Settings', {
            'fields': (
                'copy_mode', 'copy_percentage', 'fixed_amount_usd',
                'copy_buy_only', 'copy_sell_only'
            )
        }),
        ('Risk Controls', {
            'fields': (
                'max_position_usd', 'max_slippage_bps', 'max_risk_score',
                'min_trade_usd', 'max_trade_usd'
            )
        }),
        ('Filters', {
            'fields': (
                'allowed_chains', 'blacklisted_tokens', 'whitelisted_tokens'
            ),
            'classes': ('collapse',)
        }),
        ('Performance Metrics', {
            'fields': (
                'total_copies', 'successful_copies', 'win_rate_pct',
                'total_pnl_usd'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_activity_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['activate_traders', 'pause_traders', 'blacklist_traders']
    
    def trader_display(self, obj):
        """Display trader name and shortened address."""
        name = obj.trader_name or "Unknown Trader"
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            name,
            obj.short_address
        )
    trader_display.short_description = "Trader"
    
    def win_rate_display(self, obj):
        """Display win rate with color coding."""
        rate = obj.win_rate_pct
        if rate >= 70:
            color = "green"
        elif rate >= 50:
            color = "orange"
        else:
            color = "red"
        
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color,
            rate
        )
    win_rate_display.short_description = "Win Rate"
    
    def total_pnl_display(self, obj):
        """Display PnL with color coding."""
        pnl = obj.total_pnl_usd
        color = "green" if pnl >= 0 else "red"
        sign = "+" if pnl > 0 else ""
        
        return format_html(
            '<span style="color: {};">{}{:.2f} USD</span>',
            color,
            sign,
            pnl
        )
    total_pnl_display.short_description = "Total PnL"
    
    def activate_traders(self, request, queryset):
        """Bulk action to activate traders."""
        count = queryset.update(status='active')
        self.message_user(request, f"{count} traders activated.")
    activate_traders.short_description = "Activate selected traders"
    
    def pause_traders(self, request, queryset):
        """Bulk action to pause traders."""
        count = queryset.update(status='paused')
        self.message_user(request, f"{count} traders paused.")
    pause_traders.short_description = "Pause selected traders"
    
    def blacklist_traders(self, request, queryset):
        """Bulk action to blacklist traders."""
        count = queryset.update(status='blacklisted')
        self.message_user(request, f"{count} traders blacklisted.")
    blacklist_traders.short_description = "Blacklist selected traders"


@admin.register(CopyTrade)
class CopyTradeAdmin(admin.ModelAdmin):
    """Admin interface for CopyTrade model."""
    
    list_display = (
        'trade_display', 'followed_trader', 'status_display', 
        'copy_amount_display', 'execution_delay_display', 
        'pnl_display', 'created_at'
    )
    list_filter = (
        'status', 'chain', 'dex_name', 'is_paper', 
        'is_profitable', 'created_at'
    )
    search_fields = (
        'original_tx_hash', 'copy_tx_hash', 'token_symbol', 
        'followed_trader__trader_name', 'followed_trader__wallet_address'
    )
    ordering = ('-created_at',)
    readonly_fields = (
        'id', 'original_timestamp', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Copy Trade Information', {
            'fields': (
                'id', 'followed_trader', 'status', 'is_paper'
            )
        }),
        ('Original Trade', {
            'fields': (
                'original_tx_hash', 'original_block_number', 'original_timestamp',
                'original_amount_in', 'original_amount_out', 'original_amount_usd'
            )
        }),
        ('Token & DEX Details', {
            'fields': (
                'chain', 'dex_name', 'token_address', 'token_symbol', 'pair_address'
            )
        }),
        ('Copy Execution', {
            'fields': (
                'copy_amount_usd', 'copy_amount_in', 'copy_amount_out',
                'copy_tx_hash', 'copy_block_number'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'execution_delay_seconds', 'realized_slippage_bps',
                'gas_used', 'gas_price_gwei', 'total_fees_usd',
                'pnl_usd', 'is_profitable'
            ),
            'classes': ('collapse',)
        }),
        ('Risk Assessment', {
            'fields': (
                'risk_score', 'risk_reason'
            ),
            'classes': ('collapse',)
        }),
        ('Relationships', {
            'fields': (
                'ledger_entry', 'trade'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'trace_id', 'notes', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    actions = ['mark_as_profitable', 'mark_as_unprofitable']
    
    def trade_display(self, obj):
        """Display trade summary."""
        paper_badge = " 📝" if obj.is_paper else ""
        return format_html(
            '<strong>{}</strong> {}<br><small>{} on {}</small>',
            obj.token_symbol or "Unknown",
            paper_badge,
            obj.dex_name,
            obj.chain
        )
    trade_display.short_description = "Trade"
    
    def status_display(self, obj):
        """Display status with icons."""
        status_icons = {
            'pending': '⏳',
            'executed': '✅',
            'failed': '❌',
            'skipped': '⏭️'
        }
        icon = status_icons.get(obj.status, '❓')
        return format_html(
            '{} {}',
            icon,
            obj.get_status_display()
        )
    status_display.short_description = "Status"
    
    def copy_amount_display(self, obj):
        """Display copy amount."""
        return format_html(
            '<strong>${:.2f}</strong>',
            obj.copy_amount_usd
        )
    copy_amount_display.short_description = "Copy Amount"
    
    def execution_delay_display(self, obj):
        """Display execution delay with color coding."""
        if not obj.execution_delay_seconds:
            return "-"
        
        delay = obj.execution_delay_seconds
        if delay <= 10:
            color = "green"
        elif delay <= 30:
            color = "orange" 
        else:
            color = "red"
        
        return format_html(
            '<span style="color: {};">{:.1f}s</span>',
            color,
            delay
        )
    execution_delay_display.short_description = "Delay"
    
    def pnl_display(self, obj):
        """Display PnL with color coding."""
        if obj.pnl_usd is None:
            return "-"
        
        pnl = obj.pnl_usd
        color = "green" if pnl >= 0 else "red"
        sign = "+" if pnl > 0 else ""
        
        return format_html(
            '<span style="color: {};">{}{:.2f}</span>',
            color,
            sign,
            pnl
        )
    pnl_display.short_description = "PnL"
    
    def mark_as_profitable(self, request, queryset):
        """Mark selected trades as profitable."""
        count = queryset.update(is_profitable=True)
        self.message_user(request, f"{count} trades marked as profitable.")
    mark_as_profitable.short_description = "Mark as profitable"
    
    def mark_as_unprofitable(self, request, queryset):
        """Mark selected trades as unprofitable."""
        count = queryset.update(is_profitable=False)
        self.message_user(request, f"{count} trades marked as unprofitable.")
    mark_as_unprofitable.short_description = "Mark as unprofitable"


@admin.register(CopyTradeFilter)
class CopyTradeFilterAdmin(admin.ModelAdmin):
    """Admin interface for CopyTradeFilter model."""
    
    list_display = (
        'name', 'is_active', 'priority', 'min_liquidity_display',
        'max_risk_score', 'min_trader_success_rate', 'created_at'
    )
    list_filter = ('is_active', 'require_verified_contract', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('priority', '-created_at')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Filter Information', {
            'fields': ('id', 'name', 'description', 'is_active', 'priority')
        }),
        ('Token Filters', {
            'fields': (
                'min_liquidity_usd', 'max_tax_percentage',
                'blacklisted_tokens', 'whitelisted_tokens', 'require_verified_contract'
            )
        }),
        ('Trade Size Filters', {
            'fields': ('min_trade_usd', 'max_trade_usd')
        }),
        ('Risk Filters', {
            'fields': ('max_risk_score', 'min_trader_success_rate')
        }),
        ('Chain & DEX Filters', {
            'fields': ('allowed_chains', 'allowed_dexes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['activate_filters', 'deactivate_filters']
    
    def min_liquidity_display(self, obj):
        """Display minimum liquidity with formatting."""
        return format_html(
            '${:,.0f}',
            obj.min_liquidity_usd
        )
    min_liquidity_display.short_description = "Min Liquidity"
    
    def activate_filters(self, request, queryset):
        """Bulk action to activate filters."""
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} filters activated.")
    activate_filters.short_description = "Activate selected filters"
    
    def deactivate_filters(self, request, queryset):
        """Bulk action to deactivate filters."""
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} filters deactivated.")
    deactivate_filters.short_description = "Deactivate selected filters"


# Custom Admin Site Configuration
admin.site.site_header = "DEX Sniper Pro Admin"
admin.site.site_title = "DEX Sniper Pro"
admin.site.index_title = "DEX Sniper Pro Administration"