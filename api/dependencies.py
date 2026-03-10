"""
api/dependencies.py — FastAPI dependency injection for DB and Redis.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.db.engine import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session, auto-closing on exit."""
    async with async_session_factory() as session:
        yield session


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Yield an async Redis connection."""
    client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()
