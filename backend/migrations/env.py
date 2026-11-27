"""Async Alembic migration environment for the Aspirant AI Ecosystem."""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Ensure repository root is importable regardless of current working directory
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.config import get_settings  # noqa: E402
from backend.app.core.database import Base, DatabaseManager  # noqa: E402
import backend.app.infrastructure.db.models  # noqa: E402, F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _ensure_sqlite_parent_dir(url: str) -> None:
    if not url.startswith("sqlite"):
        return
    # Handle sqlite+aiosqlite:///relative/or/C:/abs/path.db cleanly
    if ":////" in url:
        raw_path = url.split(":////", 1)[1]
    elif ":///" in url:
        raw_path = url.split(":///", 1)[1]
    else:
        return
    raw_path = raw_path.split("?", 1)[0]
    if not raw_path or raw_path == ":memory:":
        return
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = REPO_ROOT / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)


def get_url() -> str:
    env_url = os.environ.get("DATABASE_URL")
    settings_url = get_settings().database_url
    override = config.get_main_option("sqlalchemy.url")
    raw = env_url or settings_url or override
    normalized = DatabaseManager._normalize_async_url(raw)
    _ensure_sqlite_parent_dir(normalized)
    return normalized


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
