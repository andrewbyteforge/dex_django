from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import StaticPool

from .config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy setup
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=StaticPool,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    } if "sqlite" in settings.DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()


async def init_db() -> None:
    """Initialize database tables."""
    try:
        # Import all models to ensure they're registered
        from dex_django.models import trading, discovery  # noqa: F401
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        # Configure SQLite for WAL mode
        if "sqlite" in settings.DATABASE_URL:
            async with engine.begin() as conn:
                await conn.execute("PRAGMA journal_mode=WAL")
                await conn.execute("PRAGMA synchronous=NORMAL")
                await conn.execute("PRAGMA foreign_keys=ON")
                await conn.execute("PRAGMA cache_size=10000")
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)
        raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()