"""SQLite-backed security and activity audit logger."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from aspirant.core.events import EventBus
from aspirant.memory.database import open_sqlite

_SENSITIVE_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"sk-[0-9A-Za-z\-_]{20,}"),
    re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),  # Aadhaar-like 12-digit sequences
    re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),  # PAN-like sequences
]


def scrub_sensitive_text(text: str) -> str:
    """Redact common API keys and national ID patterns before writing logs."""
    result = text
    for pattern in _SENSITIVE_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def _scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        return scrub_sensitive_text(value)
    if isinstance(value, dict):
        return {
            k: ("[REDACTED]" if any(s in k.lower() for s in ("key", "token", "secret", "password", "otp", "aadhaar", "pan")) else _scrub_value(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_scrub_value(item) for item in value]
    return value


class AuditLogger:
    """Append-only activity and security decision log stored in audit.db."""

    def __init__(self, audit_db_path: Path, event_bus: EventBus | None = None) -> None:
        self.audit_db_path = audit_db_path
        self.event_bus = event_bus

    def log(
        self,
        category: str,
        action: str,
        permission: str,
        decision: str,
        status: str = "ok",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record an audit entry and publish an event."""
        timestamp = datetime.now(timezone.utc).isoformat()
        safe_details = _scrub_value(details or {})
        details_json = json.dumps(safe_details, ensure_ascii=False)
        safe_action = scrub_sensitive_text(action)

        with open_sqlite(self.audit_db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_logs (timestamp, category, action, permission, decision, status, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (timestamp, category, safe_action, permission, decision, status, details_json),
            )
            entry_id = cursor.lastrowid

        entry = {
            "id": entry_id,
            "timestamp": timestamp,
            "category": category,
            "action": safe_action,
            "permission": permission,
            "decision": decision,
            "status": status,
            "details": safe_details,
        }
        if self.event_bus is not None:
            self.event_bus.publish("audit.logged", entry)
        return entry

    def recent(self, limit: int = 50, category: str | None = None) -> list[dict[str, Any]]:
        """Query the most recent audit records."""
        bounded_limit = max(1, min(limit, 500))
        with open_sqlite(self.audit_db_path) as conn:
            if category:
                rows = conn.execute(
                    """
                    SELECT id, timestamp, category, action, permission, decision, status, details_json
                    FROM audit_logs
                    WHERE category = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (category, bounded_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, timestamp, category, action, permission, decision, status, details_json
                    FROM audit_logs
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (bounded_limit,),
                ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            try:
                details = json.loads(row["details_json"])
            except json.JSONDecodeError:
                details = {}
            results.append(
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "category": row["category"],
                    "action": row["action"],
                    "permission": row["permission"],
                    "decision": row["decision"],
                    "status": row["status"],
                    "details": details,
                }
            )
        return results
