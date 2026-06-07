from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Read replica for analytics (read-only queries) — User Story 1.2.2
_replica_url = settings.database_replica_url or settings.database_url
analytics_engine = create_async_engine(
    _replica_url,
    echo=False,
    pool_pre_ping=True,
)

AnalyticsSessionLocal = async_sessionmaker(
    analytics_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_analytics_db() -> AsyncGenerator[AsyncSession, None]:
    """Read-only analytics session (routes to replica when configured)."""
    async with AnalyticsSessionLocal() as session:
        yield session
