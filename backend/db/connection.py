"""
Database connection and async session management for Multi-Agent Orchestrator.
Supports PostgreSQL (asyncpg) with automatic fallback to local SQLite (aiosqlite)
for rapid zero-config local development if PostgreSQL is not reachable.
"""
from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from db.models import Base

logger = logging.getLogger("db.connection")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    """
    Returns the configured database URL.
    Default preference is DATABASE_URL from .env or environment, targeting Docker PostgreSQL.
    If not specified, defaults to postgresql+asyncpg://postgres:postgres@localhost:5432/agents.
    """
    url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/agents")
    
    # Handle standard postgresql:// URLs by converting to asyncpg if needed
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        
    return url


def _is_sqlite_url(db_url: str) -> bool:
    return db_url.startswith("sqlite")


def _create_engine(db_url: str) -> AsyncEngine:
    """Creates an engine, applying the pragmas SQLite needs under concurrency.

    Parallel agent runs mean several transactions want to write at once. SQLite's
    defaults (rollback journal, 5s busy timeout) surface that as
    "database is locked" errors, so WAL plus a generous busy timeout is required
    for the local/SQLite fallback to behave like the Postgres deployment.
    """
    connect_args: dict = {}
    engine_kwargs: dict = {"echo": False, "future": True, "pool_pre_ping": True}

    if _is_sqlite_url(db_url):
        connect_args = {"check_same_thread": False, "timeout": 30}
        engine_kwargs["connect_args"] = connect_args

    engine = create_async_engine(db_url, **engine_kwargs)

    if _is_sqlite_url(db_url):
        from sqlalchemy import event

        @event.listens_for(engine.sync_engine, "connect")
        def _apply_sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver hook
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=30000")
            finally:
                cursor.close()

    return engine


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        db_url = get_database_url()

        try:
            _engine = _create_engine(db_url)
            logger.info(f"Database engine initialized with: {db_url.split('@')[-1] if '@' in db_url else db_url}")
        except Exception as e:
            logger.error(f"Failed to initialize engine for {db_url}: {e}. Falling back to SQLite.")
            _engine = _create_engine("sqlite+aiosqlite:///./data/agents.db")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an AsyncSession."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def async_session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for obtaining an AsyncSession outside of FastAPI request routes."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initializes tables if they do not exist. Automatically falls back to SQLite if PostgreSQL is unreachable."""
    global _engine, _session_factory
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created successfully in PostgreSQL.")
    except Exception as e:
        logger.warning(f"Could not connect to primary database ({e}). Falling back to local SQLite.")
        fallback_url = "sqlite+aiosqlite:///./data/agents.db"
        _engine = _create_engine(fallback_url)
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Local SQLite database initialized successfully.")
