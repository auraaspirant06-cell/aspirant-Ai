"""SQLite schema initialization and safe connection management."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator


MEMORY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'auto',
    persona TEXT NOT NULL DEFAULT 'professional',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'auto',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS fts_messages USING fts5(
    message_id UNINDEXED,
    conversation_id UNINDEXED,
    content
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL UNIQUE,
    primary_language TEXT NOT NULL DEFAULT 'python',
    notes TEXT NOT NULL DEFAULT '',
    last_opened_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    capability TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms REAL NOT NULL DEFAULT 0.0,
    estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'ok',
    created_at TEXT NOT NULL
);
"""

AUDIT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,
    action TEXT NOT NULL,
    permission TEXT NOT NULL,
    decision TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS permission_state (
    permission TEXT PRIMARY KEY,
    granted INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_flags (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@contextmanager
def open_sqlite(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Open a WAL-mode SQLite connection with foreign keys enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class DatabaseInitializer:
    """Initializes and validates Aspirant's local SQLite databases."""

    def __init__(self, memory_db_path: Path, audit_db_path: Path) -> None:
        self.memory_db_path = memory_db_path
        self.audit_db_path = audit_db_path

    def initialize(self) -> None:
        """Create schema tables if they do not yet exist."""
        with open_sqlite(self.memory_db_path) as conn:
            conn.executescript(MEMORY_SCHEMA_SQL)
        with open_sqlite(self.audit_db_path) as conn:
            conn.executescript(AUDIT_SCHEMA_SQL)
