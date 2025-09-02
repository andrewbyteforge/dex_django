from __future__ import annotations

import os
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application
    DEBUG: bool = Field(default=True)
    LOG_LEVEL: str = Field(default="INFO")
    
    # API
    API_V1_PREFIX: str = Field(default="/api/v1")
    # CORS_ORIGINS should only list frontend URLs, not backend APIs
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:5173", "http://127.0.0.1:5173"])
    
    # Trading
    DEFAULT_SLIPPAGE_BPS: int = Field(default=300)  # 3%
    MAX_SLIPPAGE_BPS: int = Field(default=1000)     # 10%
    GAS_PRICE_MULTIPLIER: float = Field(default=1.2)
    
    # Risk Management
    MAX_TRADE_SIZE_ETH: float = Field(default=1.0)
    MAX_DAILY_TRADES: int = Field(default=50)
    MIN_LIQUIDITY_USD: float = Field(default=10000.0)
    
    # Paper Trading
    PAPER_TRADING_ENABLED: bool = Field(default=True)
    PAPER_STARTING_BALANCE: float = Field(default=1000.0)  # USD equivalent
    
    # Discovery
    DISCOVERY_ENABLED: bool = Field(default=True)
    DISCOVERY_INTERVAL_SEC: int = Field(default=5)
    NEW_PAIR_ALERT_THRESHOLD: float = Field(default=5000.0)  # USD liquidity
    
    # RPC Endpoints (fallbacks)
    ETH_RPC_URL: str = Field(default="https://rpc.ankr.com/eth")
    BSC_RPC_URL: str = Field(default="https://rpc.ankr.com/bsc")
    BASE_RPC_URL: str = Field(default="https://rpc.ankr.com/base")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()