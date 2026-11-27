"""Async SQLAlchemy 2.0 database engine and session factory supporting PostgreSQL and SQLite."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models and Alembic migrations."""


class DatabaseManager:
    """Manages async SQLAlchemy engine lifecycle and scoped sessions."""

    def __init__(self, database_url: str, *, echo: bool = False) -> None:
        normalized = self._normalize_async_url(database_url)
        connect_args = {"check_same_thread": False} if normalized.startswith("sqlite+") else {}
        self.database_url = normalized
        self.engine: AsyncEngine = create_async_engine(
            normalized,
            echo=echo,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @staticmethod
    def _normalize_async_url(url: str) -> str:
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("sqlite:///"):
            return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return url

    async def create_all(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
