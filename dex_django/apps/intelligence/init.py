"""
Advanced market intelligence system for DEX Sniper Pro.
"""

# Import all components
from .market_analyzer import market_intelligence
from .advanced_risk_detection import advanced_risk_detector
from .mempool_analyzer import mempool_intelligence
from .cross_chain_analyzer import cross_chain_analyzer
from ..strategy.risk_manager import risk_manager, TradingMode
from .strategy_engine import strategy_engine, StrategyType

# Enable advanced features
market_intelligence.advanced_features_enabled = True

__all__ = [
    'market_intelligence',
    'advanced_risk_detector',
    'mempool_intelligence',
    'cross_chain_analyzer',
    'risk_manager',
    'strategy_engine',
    'TradingMode',
    'StrategyType'
]