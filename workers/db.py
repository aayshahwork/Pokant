"""
workers/db.py — Synchronous SQLAlchemy engine for Celery workers.

Celery workers run synchronous code, so we need a sync engine (psycopg2)
rather than the async engine (asyncpg) used by the FastAPI application.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from workers.config import worker_settings

_sync_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def _get_engine() -> Engine:
    """Lazily create the sync engine (avoids import-time DB connection)."""
    global _sync_engine
    if _sync_engine is None:
        sync_url = worker_settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
        _sync_engine = create_engine(
            sync_url,
            pool_size=5,
            max_overflow=3,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
    return _sync_engine


def _get_session_factory() -> sessionmaker:
    """Lazily create the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=_get_engine(),
            class_=Session,
            expire_on_commit=False,
        )
    return _session_factory


def get_sync_session() -> Session:
    """Return a new synchronous DB session. Caller must close it."""
    return _get_session_factory()()
