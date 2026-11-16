"""Asynchronous database engine and session management."""

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shortvideocli.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Create and cache the asynchronous database engine."""
    database_url = get_settings().database_url

    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
    )

    if database_url.startswith("sqlite+aiosqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def enable_sqlite_foreign_keys(
            dbapi_connection: object,
            connection_record: object,
        ) -> None:
            """Enable SQLite foreign-key enforcement for each connection."""
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the cached asynchronous session factory."""
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Yield an asynchronous database session and close it afterward."""
    async with get_session_factory()() as session:
        yield session


async def close_database() -> None:
    """Dispose of the database engine and clear cached database objects."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()

    get_session_factory.cache_clear()
    get_engine.cache_clear()
