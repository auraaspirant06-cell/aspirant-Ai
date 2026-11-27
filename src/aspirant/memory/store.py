"""SQLite + FTS5 local memory repository with automatic PII/secret redaction."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import uuid

from aspirant.memory.database import open_sqlite
from aspirant.security.redactor import contains_sensitive_secret, redact_sensitive_content

_BLOCKED_PREF_KEYS = ("password", "api_key", "secret", "token", "otp", "aadhaar", "pan")


class MemoryStore:
    """Manages conversations, FTS5-indexed messages, preferences, and project memory."""

    def __init__(self, memory_db_path: Path) -> None:
        self.memory_db_path = memory_db_path

    def create_conversation(
        self,
        title: str = "New Conversation",
        language: str = "auto",
        persona: str = "professional",
    ) -> dict[str, Any]:
        conv_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        safe_title = redact_sensitive_content(title).text[:120] or "New Conversation"
        with open_sqlite(self.memory_db_path) as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, title, language, persona, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conv_id, safe_title, language, persona, now, now),
            )
        return {
            "id": conv_id,
            "title": safe_title,
            "language": language,
            "persona": persona,
            "created_at": now,
            "updated_at": now,
        }

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        bounded = max(1, min(limit, 200))
        with open_sqlite(self.memory_db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, title, language, persona, created_at, updated_at
                FROM conversations
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (bounded,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with open_sqlite(self.memory_db_path) as conn:
            row = conn.execute(
                "SELECT id, title, language, persona, created_at, updated_at FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_conversation(
        self,
        conversation_id: str,
        title: str | None = None,
        language: str | None = None,
        persona: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        updates: list[str] = ["updated_at = ?"]
        params: list[Any] = [now]
        if title is not None:
            updates.append("title = ?")
            params.append(redact_sensitive_content(title).text[:120])
        if language is not None:
            updates.append("language = ?")
            params.append(language)
        if persona is not None:
            updates.append("persona = ?")
            params.append(persona)
        params.append(conversation_id)

        with open_sqlite(self.memory_db_path) as conn:
            conn.execute(
                f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?",
                params,
            )

    def delete_conversation(self, conversation_id: str) -> bool:
        with open_sqlite(self.memory_db_path) as conn:
            conn.execute(
                "DELETE FROM fts_messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            cur = conn.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conversation_id,),
            )
            return cur.rowcount > 0

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        language: str = "auto",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a conversation message after redacting sensitive IDs/OTPs/keys."""
        redaction = redact_sensitive_content(content)
        msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        meta = dict(metadata or {})
        if redaction.redacted_count:
            meta["redacted_categories"] = list(redaction.categories)
        meta_json = json.dumps(meta, ensure_ascii=False)

        with open_sqlite(self.memory_db_path) as conn:
            conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, language, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (msg_id, conversation_id, role, redaction.text, language, meta_json, now),
            )
            conn.execute(
                """
                INSERT INTO fts_messages (message_id, conversation_id, content)
                VALUES (?, ?, ?)
                """,
                (msg_id, conversation_id, redaction.text),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
        return {
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": redaction.text,
            "language": language,
            "metadata": meta,
            "created_at": now,
        }

    def get_messages(self, conversation_id: str, limit: int = 50) -> list[dict[str, Any]]:
        bounded = max(1, min(limit, 500))
        with open_sqlite(self.memory_db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, conversation_id, role, content, language, metadata_json, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (conversation_id, bounded),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["metadata"] = json.loads(item.pop("metadata_json"))
            except json.JSONDecodeError:
                item["metadata"] = {}
            items.append(item)
        return items

    def delete_message(self, message_id: str) -> bool:
        with open_sqlite(self.memory_db_path) as conn:
            conn.execute("DELETE FROM fts_messages WHERE message_id = ?", (message_id,))
            cur = conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            return cur.rowcount > 0

    def search_messages(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        """Full-text search across redacted local chat history."""
        clean = query.strip().replace('"', " ")
        if not clean:
            return []
        tokens = [f'"{tok}"' for tok in clean.split() if tok]
        fts_query = " ".join(tokens)
        bounded = max(1, min(limit, 100))
        with open_sqlite(self.memory_db_path) as conn:
            rows = conn.execute(
                """
                SELECT m.id, m.conversation_id, m.role, m.content, m.language, m.created_at
                FROM fts_messages f
                JOIN messages m ON m.id = f.message_id
                WHERE fts_messages MATCH ?
                ORDER BY m.created_at DESC
                LIMIT ?
                """,
                (fts_query, bounded),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_preference(
        self, key: str, value: Any, category: str = "general"
    ) -> dict[str, Any]:
        """Store a non-sensitive user preference; rejects secret/PII keys or values."""
        lower_key = key.strip().lower()
        if any(tok in lower_key for tok in _BLOCKED_PREF_KEYS):
            raise ValueError(f"Sensitive preference key {key!r} cannot be saved in conversational memory.")
        raw_val = json.dumps(value, ensure_ascii=False)
        if contains_sensitive_secret(raw_val):
            raise ValueError("Sensitive credential/national-ID pattern detected; refused to save in memory.")

        now = datetime.now(timezone.utc).isoformat()
        with open_sqlite(self.memory_db_path) as conn:
            conn.execute(
                """
                INSERT INTO preferences (key, value_json, category, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    category = excluded.category,
                    updated_at = excluded.updated_at
                """,
                (key.strip(), raw_val, category, now),
            )
        return {"key": key.strip(), "value": value, "category": category, "updated_at": now}

    def get_preference(self, key: str, default: Any = None) -> Any:
        with open_sqlite(self.memory_db_path) as conn:
            row = conn.execute(
                "SELECT value_json FROM preferences WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value_json"])
        except json.JSONDecodeError:
            return default

    def list_preferences(self) -> list[dict[str, Any]]:
        with open_sqlite(self.memory_db_path) as conn:
            rows = conn.execute(
                "SELECT key, value_json, category, updated_at FROM preferences ORDER BY category, key"
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            try:
                val = json.loads(row["value_json"])
            except json.JSONDecodeError:
                val = row["value_json"]
            items.append(
                {
                    "key": row["key"],
                    "value": val,
                    "category": row["category"],
                    "updated_at": row["updated_at"],
                }
            )
        return items

    def delete_preference(self, key: str) -> bool:
        with open_sqlite(self.memory_db_path) as conn:
            cur = conn.execute("DELETE FROM preferences WHERE key = ?", (key,))
            return cur.rowcount > 0
