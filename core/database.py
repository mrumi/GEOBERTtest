# ============================================================
# core/database.py — PostgreSQL Connection (SQLAlchemy async)
# ============================================================
# This is the persistence
# layer for multi-user sessions/messages, decided on
# a multi-user tool needing private history per users.
# Async engine because FastAPI route handlers are async —
# using a sync SQLAlchemy engine would block the event loop
# on every DB call, hurting concurrency under multiple users.
# ============================================================

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import settings


class Base(DeclarativeBase):
    """Base class every ORM model (models/user.py etc.) inherits from."""
    pass


engine = create_async_engine(
    settings.DATABASE_URL,
    echo       = False,   # set True temporarily for SQL debug logging
    pool_size  = 10,
    max_overflow = 20,
)

AsyncSessionLocal = async_sessionmaker(
    bind          = engine,
    class_        = AsyncSession,
    expire_on_commit = False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a DB session per request,
    closes it automatically when the request finishes.

    Usage in a route:
        @router.get("/sessions")
        async def list_sessions(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """
    Create all tables if they don't exist yet.

    NOTE: this is a convenience for local development only.
    In production, use Alembic migrations (alembic/ folder)
    instead of this, so schema changes are tracked and
    reversible rather than silently auto-created.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)